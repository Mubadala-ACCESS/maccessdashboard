# iot_graphs.py
from pymongo import MongoClient
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

import configparser
import os

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), '../config', 'config.ini')
config.read(config_path)

# Retrieve MongoDB settings
MONGO_URI = config.get('mongodb', 'uri')
DB_NAME   = config.get('mongodb', 'database')
STATIONS_INFO = config.get('mongodb', 'stations_info_collection')



class IoTGraphs:
    def __init__(self):
        """Initialize MongoDB connection"""
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]

    def _format_param_label(self, param):
        """
        Helper function to format sensor parameter labels with units.
        It ensures that:
          - 'co2' becomes 'CO2 (ppm)'
          - 'humidity' becomes 'Humidity (%)'
          - 'temperature' becomes 'Temperature (°C)'
          - 'pressure' becomes 'Atmospheric Pressure (hPa)'
          - 'PM1mass' becomes 'PM1 Mass (µg/m³)'
          - 'PM2,5mass' (or PM2.5mass) becomes 'PM2.5 Mass (µg/m³)'
          - 'PM10mass' becomes 'PM10 Mass (µg/m³)'
          - 'PM1count' becomes 'PM1 Count (particles per unit volume)'
          - 'PM2,5count' (or PM2.5count) becomes 'PM2.5 Count (particles per unit volume)'
          - 'PM10count' becomes 'PM10 Count (particles per unit volume)'
        """
        low = param.lower()
        if low == "humidity":
            return "Humidity (%)"
        if low == "temperature":
            return "Temperature (°C)"
        if low == "pressure":
            return "Atmospheric Pressure (hPa)"
        if low == "co2":
            return "CO2 (ppm)"
        if "pm1mass" in low:
            return "PM1 Mass (µg/m³)"
        if "pm2,5mass" in low or "pm2.5mass" in low:
            return "PM2.5 Mass (µg/m³)"
        if "pm10mass" in low:
            return "PM10 Mass (µg/m³)"
        if "pm1count" in low:
            return "PM1 Count (particles per unit volume)"
        if "pm2,5count" in low or "pm2.5count" in low:
            return "PM2.5 Count (particles per unit volume)"
        if "pm10count" in low:
            return "PM10 Count (particles per unit volume)"
        # Default: convert underscores to spaces and title-case the string.
        return param.replace("_", " ").title()

    def get_available_parameters(self, station_num):
        """
        Retrieve unique base parameters available from sensors,
        excluding fields like "index", "sensor_T", and "sensor_RH".
        Returns a mapping of base parameter to its capitalized label with units,
        ordered in the following fixed order (if available):

          1. Temperature (°C)
          2. Humidity (%)
          3. Atmospheric Pressure (hPa)
          4. CO2 (ppm)
          5. PM1 Mass (µg/m³)
          6. PM2.5 Mass (µg/m³)
          7. PM10 Mass (µg/m³)
        """
        station_info = self.db[STATIONS_INFO].find_one(
            {"station_num": station_num}, {"sensors": 1}
        )
        if not station_info or "sensors" not in station_info:
            return {}
        params_set = set()
        exclude_params = {"PM1count", "PM2,5count", "PM10count"}
        for sensor_type, count in station_info["sensors"].items():
            for i in range(count):
                sensor_key = f"{sensor_type}+{i}"
                document = self.db[f"station{station_num}"].find_one(
                    {}, {"_id": 0, "datetime": 1, sensor_key: 1}
                )
                if not document or sensor_key not in document:
                    continue
                sensor_data = document[sensor_key]
                if isinstance(sensor_data, dict):
                    for param, value in sensor_data.items():
                        if (
                            isinstance(value, (int, float))
                            and param not in ["index", "sensor_T", "sensor_RH"]
                            and param not in exclude_params
                        ):
                            params_set.add(param)
        # Build the mapping using the helper function
        param_map = {param: self._format_param_label(param) for param in params_set}
        
        # Define the fixed order (by label)
        desired_order = [
            "Temperature (°C)",
            "Humidity (%)",
            "Atmospheric Pressure (hPa)",
            "CO2 (ppm)",
            "PM1 Mass (µg/m³)",
            "PM2.5 Mass (µg/m³)",
            "PM10 Mass (µg/m³)"
        ]
        # Build an ordered mapping: add parameters in the desired order first if available
        ordered_param_map = {}
        for desired in desired_order:
            for key, label in param_map.items():
                if label == desired:
                    ordered_param_map[key] = label
        # Append any additional parameters not in the desired list (sorted alphabetically by label)
        for key, label in sorted(param_map.items(), key=lambda x: x[1]):
            if label not in ordered_param_map.values():
                ordered_param_map[key] = label
        return ordered_param_map

    def get_full_sensor_parameters(self, station_num):
        """
        Retrieve full sensor parameters mapping.
        Returns a dictionary mapping base parameter to a list of tuples:
        (full_key, sensor_label)
        where full_key is in the format "sensorType+{i}.param" and
        sensor_label is like "Param (unit) - SensorType {i+1}".
        """
        station_info = self.db[STATIONS_INFO].find_one(
            {"station_num": station_num}, {"sensors": 1}
        )
        full_params = {}
        if not station_info or "sensors" not in station_info:
            return full_params

        for sensor_type, count in station_info["sensors"].items():
            for i in range(count):
                sensor_key = f"{sensor_type}+{i}"
                document = self.db[f"station{station_num}"].find_one(
                    {}, {"_id": 0, "datetime": 1, sensor_key: 1}
                )
                if not document or sensor_key not in document:
                    continue
                sensor_data = document[sensor_key]
                if isinstance(sensor_data, dict):
                    for param, value in sensor_data.items():
                        if (
                            isinstance(value, (int, float))
                            and param not in ["index", "sensor_T", "sensor_RH"]
                        ):
                            base_param = param
                            full_key = f"{sensor_key}.{param}"
                            # Use the helper to format the parameter label with units.
                            sensor_label = f"{self._format_param_label(param)} - {sensor_type.replace('_', ' ').title()} {i+1}"
                            full_params.setdefault(base_param, []).append((full_key, sensor_label))
        return full_params

    def fetch_station_data(self, station_num, date_range, selected_parameters, split_view):
        """
        Fetch station data based on the selected time range and parameters.
        If split_view is True, fetch individual sensor readings;
        if False, combine sensor readings by averaging.
        selected_parameters is a list of base parameters.
        Also includes location (Longitude and Latitude) from the GPS sensor.
        """
        now = datetime.now(timezone.utc)
        time_deltas = {
            "6H": timedelta(hours=6),
            "12H": timedelta(hours=12),
            "1D": timedelta(days=1),
            "1W": timedelta(weeks=1),
            "1M": timedelta(days=30),
            "6M": timedelta(days=180),
            "1Y": timedelta(days=365)
        }
        start_time = now - time_deltas.get(date_range, timedelta(days=1))
        station_collection = self.db[f"station{station_num}"]
        query_filter = {"datetime": {"$gte": start_time}} if date_range != "All" else {}

        if split_view:
            full_params = self.get_full_sensor_parameters(station_num)
            selected_full = {}
            for base_param in selected_parameters:
                if base_param in full_params:
                    selected_full[base_param] = full_params[base_param]
            projection = {"_id": 0, "datetime": 1}
            for sensor_list in selected_full.values():
                for full_key, _ in sensor_list:
                    sensor_main_key = full_key.split('.')[0]
                    projection[sensor_main_key] = 1
            # Include GPS data
            projection["gps"] = 1
            cursor = station_collection.find(query_filter, projection)
            data = []
            for record in cursor:
                entry = {"DateTime": record.get("datetime")}
                for base_param, sensor_list in selected_full.items():
                    for full_key, _ in sensor_list:
                        sensor_main_key, sensor_sub_key = full_key.split(".", 1)
                        sensor_data = record.get(sensor_main_key, {})
                        if isinstance(sensor_data, dict) and sensor_sub_key in sensor_data:
                            value = sensor_data[sensor_sub_key]
                            if isinstance(value, (int, float)):
                                entry[full_key] = value
                # Extract GPS location
                gps_data = record.get("gps", {})
                if isinstance(gps_data, dict) and "position" in gps_data:
                    pos = gps_data["position"]
                    if isinstance(pos, list) and len(pos) >= 2:
                        entry["Longitude"] = pos[0]
                        entry["Latitude"] = pos[1]
                data.append(entry)
            df = pd.DataFrame(data)
            if not df.empty:
                df["DateTime"] = pd.to_datetime(df["DateTime"])
                df = df.sort_values(by="DateTime")
            return df
        else:
            full_params = self.get_full_sensor_parameters(station_num)
            selected_full = {}
            for base_param in selected_parameters:
                if base_param in full_params:
                    selected_full[base_param] = full_params[base_param]
            projection = {"_id": 0, "datetime": 1}
            for sensor_list in selected_full.values():
                for full_key, _ in sensor_list:
                    sensor_main_key = full_key.split('.')[0]
                    projection[sensor_main_key] = 1
            # Include GPS data
            projection["gps"] = 1
            cursor = station_collection.find(query_filter, projection)
            data = []
            for record in cursor:
                entry = {"DateTime": record.get("datetime")}
                for base_param, sensor_list in selected_full.items():
                    for full_key, _ in sensor_list:
                        sensor_main_key, sensor_sub_key = full_key.split(".", 1)
                        sensor_data = record.get(sensor_main_key, {})
                        if isinstance(sensor_data, dict) and sensor_sub_key in sensor_data:
                            value = sensor_data[sensor_sub_key]
                            if isinstance(value, (int, float)):
                                entry[full_key] = value
                # Extract GPS location
                gps_data = record.get("gps", {})
                if isinstance(gps_data, dict) and "position" in gps_data:
                    pos = gps_data["position"]
                    if isinstance(pos, list) and len(pos) >= 2:
                        entry["Longitude"] = pos[0]
                        entry["Latitude"] = pos[1]
                data.append(entry)
            df = pd.DataFrame(data)
            if not df.empty:
                df["DateTime"] = pd.to_datetime(df["DateTime"])
                df = df.sort_values(by="DateTime")
            return self.combine_sensors_for_parameters(df)

    def combine_sensors_for_parameters(self, df):
        """
        Combine individual sensor columns into a single column by averaging,
        grouping by the base parameter (the part after the period in the column name).
        Also preserves location columns (Longitude and Latitude) if they exist.
        """
        if df.empty:
            return df
        combined_df = pd.DataFrame()
        combined_df["DateTime"] = df["DateTime"]
        grouped_params = {}
        for col in df.columns:
            if col == "DateTime":
                continue
            parts = col.split('.')
            if len(parts) == 2:
                base_param = parts[1]
                grouped_params.setdefault(base_param, []).append(col)
        for param, cols in grouped_params.items():
            combined_df[param] = df[cols].mean(axis=1)
        # Preserve location columns if they exist
        for col in ["Longitude", "Latitude"]:
            if col in df.columns:
                combined_df[col] = df[col]
        return combined_df

    def aggregate_data(self, df, freq):
        """Aggregate data based on the selected frequency."""
        if df.empty or "DateTime" not in df.columns:
            return df
        if freq == "None":
            return df
        df.set_index("DateTime", inplace=True)
        numeric_cols = df.select_dtypes(include=['number']).columns
        df_agg = df[numeric_cols].resample(freq).mean().reset_index()
        df_agg.fillna(method="ffill", inplace=True)
        return df_agg

    def create_iotbox_figures(self, df, selected_parameters, param_mapping, split_view):
        """
        Generate figures for the selected parameters.
        In split_view (toggle on), each base parameter is plotted with separate traces (different colors)
        for each sensor reading.
        In non-split view (toggle off), a single averaged trace is plotted in black.
        """
        figures = []
        if df.empty:
            return figures

        # Legend settings: horizontal, below the plot, center aligned.
        legend_settings = dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5
        )

        if split_view:
            base_to_keys = {}
            for col in df.columns:
                if col == "DateTime":
                    continue
                parts = col.split('.')
                if len(parts) == 2:
                    base_param = parts[1]
                    base_to_keys.setdefault(base_param, []).append(col)
            color_palette = ["blue", "red", "green", "orange", "purple", "brown"]
            for base_param in selected_parameters:
                fig = go.Figure()
                if base_param in base_to_keys:
                    keys = base_to_keys[base_param]
                    for i, key in enumerate(keys):
                        color = color_palette[i % len(color_palette)]
                        fig.add_trace(go.Scatter(
                            x=df["DateTime"],
                            y=df[key],
                            mode="markers",
                            name=f"{param_mapping.get(base_param, base_param)} - Sensor {i+1}",
                            marker=dict(color=color, size=3)
                        ))
                fig.update_layout(
                    title={
                        'text': f"{param_mapping.get(base_param, base_param)}", 
                        'x': 0.5,                   # x position (0.5 centers the title horizontally)
                        'y': 0.97,                  # y position (adjust this value as needed)
                        'xanchor': 'center',
                        'yanchor': 'top'
                    },
                    xaxis_title="DateTime",
                    yaxis_title=param_mapping.get(base_param, base_param),
                    margin={"l": 40, "r": 40, "t": 40, "b": 40},
                    template="plotly_white",
                    legend=legend_settings
                )
                figures.append(fig)
        else:
            for base_param in selected_parameters:
                if base_param in df.columns:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df["DateTime"],
                        y=df[base_param],
                        mode="markers",
                        name=param_mapping.get(base_param, base_param),
                        marker=dict(color="black", size=3)
                    ))
                    fig.update_layout(
                        title={
                        'text': f"{param_mapping.get(base_param, base_param)}", 
                        'x': 0.5,                   # x position (0.5 centers the title horizontally)
                        'y': 0.97,                  # y position (adjust this value as needed)
                        'xanchor': 'center',
                        'yanchor': 'top'
                    },
                        xaxis_title="DateTime",
                        yaxis_title=param_mapping.get(base_param, base_param),
                        margin={"l": 40, "r": 40, "t": 40, "b": 40},
                        template="plotly_white",
                        legend=legend_settings
                    )
                    figures.append(fig)
        return figures
