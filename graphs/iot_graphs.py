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
        in a fixed preferred order.
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

        param_map = {param: self._format_param_label(param) for param in params_set}
        desired_order = [
            "Temperature (°C)",
            "Humidity (%)",
            "Atmospheric Pressure (hPa)",
            "CO2 (ppm)",
            "PM1 Mass (µg/m³)",
            "PM2.5 Mass (µg/m³)",
            "PM10 Mass (µg/m³)"
        ]
        ordered_param_map = {}
        for desired in desired_order:
            for key, label in param_map.items():
                if label == desired:
                    ordered_param_map[key] = label
        for key, label in sorted(param_map.items(), key=lambda x: x[1]):
            if label not in ordered_param_map.values():
                ordered_param_map[key] = label

        return ordered_param_map

    def get_full_sensor_parameters(self, station_num):
        """
        Retrieve full sensor parameters mapping.
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
                            sensor_label = (
                                f"{self._format_param_label(param)} - "
                                f"{sensor_type.replace('_', ' ').title()} {i+1}"
                            )
                            full_params.setdefault(base_param, []).append((full_key, sensor_label))

        return full_params

    def fetch_station_data(self, station_num, date_range, selected_parameters, split_view):
        """
        Fetch station data in UTC+4 (GST) instead of UTC.
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
            selected_full = {
                bp: full_params[bp]
                for bp in selected_parameters
                if bp in full_params
            }
            projection = {"_id": 0, "datetime": 1, **{
                key.split('.')[0]: 1
                for lst in selected_full.values()
                for key, _ in lst
            }, "gps": 1}

            cursor = station_collection.find(query_filter, projection)
            data = []
            for record in cursor:
                entry = {"DateTime": record.get("datetime")}
                for base_param, sensor_list in selected_full.items():
                    for full_key, _ in sensor_list:
                        smk, ssk = full_key.split(".", 1)
                        sensor_data = record.get(smk, {})
                        if isinstance(sensor_data, dict) and ssk in sensor_data:
                            val = sensor_data[ssk]
                            if isinstance(val, (int, float)):
                                entry[full_key] = val
                gps = record.get("gps", {})
                if isinstance(gps, dict) and "position" in gps:
                    pos = gps["position"]
                    if isinstance(pos, list) and len(pos) >= 2:
                        entry["Longitude"], entry["Latitude"] = pos[0], pos[1]
                data.append(entry)

            df = pd.DataFrame(data)
            if not df.empty:
                df["DateTime"] = pd.to_datetime(df["DateTime"])
                # convert timestamps from UTC to UTC+4 (GST)
                df["DateTime"] = df["DateTime"].apply(
                    lambda dt: dt.replace(tzinfo=timezone.utc)
                                 .astimezone(timezone(timedelta(hours=4)))
                )
                df = df.sort_values(by="DateTime")
            return df

        else:
            full_params = self.get_full_sensor_parameters(station_num)
            selected_full = {
                bp: full_params[bp]
                for bp in selected_parameters
                if bp in full_params
            }
            projection = {"_id": 0, "datetime": 1, **{
                key.split('.')[0]: 1
                for lst in selected_full.values()
                for key, _ in lst
            }, "gps": 1}

            cursor = station_collection.find(query_filter, projection)
            data = []
            for record in cursor:
                entry = {"DateTime": record.get("datetime")}
                for base_param, sensor_list in selected_full.items():
                    for full_key, _ in sensor_list:
                        smk, ssk = full_key.split(".", 1)
                        sensor_data = record.get(smk, {})
                        if isinstance(sensor_data, dict) and ssk in sensor_data:
                            val = sensor_data[ssk]
                            if isinstance(val, (int, float)):
                                entry[full_key] = val
                gps = record.get("gps", {})
                if isinstance(gps, dict) and "position" in gps:
                    pos = gps["position"]
                    if isinstance(pos, list) and len(pos) >= 2:
                        entry["Longitude"], entry["Latitude"] = pos[0], pos[1]
                data.append(entry)

            df = pd.DataFrame(data)
            if not df.empty:
                df["DateTime"] = pd.to_datetime(df["DateTime"])
                # convert timestamps from UTC to UTC+4 (GST)
                df["DateTime"] = df["DateTime"].apply(
                    lambda dt: dt.replace(tzinfo=timezone.utc)
                                 .astimezone(timezone(timedelta(hours=4)))
                )
                df = df.sort_values(by="DateTime")

            return self.combine_sensors_for_parameters(df)

    def combine_sensors_for_parameters(self, df):
        """
        Combine sensor readings by averaging; preserves DateTime (UTC+4).
        """
        if df.empty:
            return df
        combined_df = pd.DataFrame()
        combined_df["DateTime"] = df["DateTime"]
        grouped = {}
        for col in df.columns:
            if col == "DateTime":
                continue
            parts = col.split('.')
            if len(parts) == 2:
                grouped.setdefault(parts[1], []).append(col)

        for param, cols in grouped.items():
            combined_df[param] = df[cols].mean(axis=1)

        for loc in ["Longitude", "Latitude"]:
            if loc in df.columns:
                combined_df[loc] = df[loc]

        return combined_df

    def aggregate_data(self, df, freq):
        """Aggregate data based on the selected frequency."""
        if df.empty or "DateTime" not in df.columns or freq == "None":
            return df
        df = df.set_index("DateTime")
        numeric = df.select_dtypes(include=['number']).columns
        df_agg = df[numeric].resample(freq).mean().ffill().reset_index()
        return df_agg

    def create_iotbox_figures(self, df, selected_parameters, param_mapping, split_view):
        """
        Generate Plotly figures showing DateTime in UTC+4 (GST).
        """
        figures = []
        if df.empty:
            return figures

        legend = dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)

        if split_view:
            base_to_keys = {}
            for col in df.columns:
                if col == "DateTime":
                    continue
                parts = col.split('.')
                if len(parts) == 2:
                    base_to_keys.setdefault(parts[1], []).append(col)

            palette = ["blue", "red", "green", "orange", "purple", "brown"]
            for bp in selected_parameters:
                fig = go.Figure()
                keys = base_to_keys.get(bp, [])
                for i, key in enumerate(keys):
                    fig.add_trace(go.Scatter(
                        x=df["DateTime"],
                        y=df[key],
                        mode="markers",
                        name=f"{param_mapping.get(bp, bp)} - Sensor {i+1}",
                        marker=dict(color=palette[i % len(palette)], size=3)
                    ))
                fig.update_layout(
                    title={'text': param_mapping.get(bp, bp), 'x': 0.5, 'y': 0.97, 'xanchor': 'center', 'yanchor': 'top'},
                    xaxis_title="UTC+04:00 (GST)",
                    yaxis_title=param_mapping.get(bp, bp),
                    margin={"l": 40, "r": 40, "t": 40, "b": 40},
                    template="plotly_white",
                    legend=legend
                )
                figures.append(fig)
        else:
            for bp in selected_parameters:
                if bp in df.columns:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df["DateTime"],
                        y=df[bp],
                        mode="markers",
                        name=param_mapping.get(bp, bp),
                        marker=dict(color="black", size=3)
                    ))
                    fig.update_layout(
                        title={'text': param_mapping.get(bp, bp), 'x': 0.5, 'y': 0.97, 'xanchor': 'center', 'yanchor': 'top'},
                        xaxis_title="UTC+04:00 (GST)",
                        yaxis_title=param_mapping.get(bp, bp),
                        margin={"l": 40, "r": 40, "t": 40, "b": 40},
                        template="plotly_white",
                        legend=legend
                    )
                    figures.append(fig)

        return figures
