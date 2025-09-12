# -*- coding: utf-8 -*-
# iot_graphs.py

from pymongo import MongoClient
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import re
import configparser
import os


# -----------------------------
# Load configuration
# -----------------------------
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), '../config', 'config.ini')
config.read(config_path)

# Retrieve MongoDB settings
MONGO_URI = config.get('mongodb', 'uri')
DB_NAME   = config.get('mongodb', 'database')
STATIONS_INFO = config.get('mongodb', 'stations_info_collection')


class IoTGraphs:
    """
    Helper for discovering available sensor parameters and building simple plots
    for IoT stations stored in MongoDB.

    What this version fixes:
      - Parameter discovery scans the most recent documents (sorted by datetime desc)
        over a short lookback window to avoid early null-only "seed" rows.
      - Discovery does NOT require numeric values; it excludes only meta fields AND
        all PM 'count' fields so counts never appear.
      - GPS is read from either gps.position OR date_time_position.{latitude, longitude}
        (with an alias dateTimePosition).
      - Projections include date_time_position/dateTimePosition when fetching.
      - Labels use Unicode escapes to avoid source-encoding issues.
    """

    # How many recent docs to scan per sensor key when discovering parameters
    LOOKBACK = 50

    # Keys that are not plotted signals and should be ignored during discovery
    EXCLUDE_DISCOVERY_KEYS = {"index", "sensor", "type", "sensor_T", "sensor_RH", "diagnostics"}

    # Regex to catch PM count parameters (pm1count, pm2.5count, pm2,5count, pm10count, etc.)
    _PM_COUNT_RE = re.compile(r'^pm(?:\d+(?:[.,]\d+)?)?count$', re.IGNORECASE)

    def __init__(self):
        """Initialize MongoDB connection"""
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]

    # -----------------------------
    # Label formatting
    # -----------------------------
    def _format_param_label(self, param: str) -> str:
        """
        Helper function to format sensor parameter labels with units.
        Uses Unicode escapes so the source file stays ASCII-safe.
        """
        low = param.lower()
        if low == "humidity":
            return "Humidity (%)"
        if low == "temperature":
            return "Temperature (\N{DEGREE SIGN}C)"
        if low == "pressure":
            return "Atmospheric Pressure (hPa)"
        if low == "co2":
            return "CO2 (ppm)"
        if "pm1mass" in low:
            return "PM1 Mass (\N{MICRO SIGN}g/m\N{SUPERSCRIPT THREE})"
        if "pm2,5mass" in low or "pm2.5mass" in low:
            return "PM2.5 Mass (\N{MICRO SIGN}g/m\N{SUPERSCRIPT THREE})"
        if "pm10mass" in low:
            return "PM10 Mass (\N{MICRO SIGN}g/m\N{SUPERSCRIPT THREE})"
        if "pm1count" in low:
            return "PM1 Count (particles per unit volume)"
        if "pm2,5count" in low or "pm2.5count" in low:
            return "PM2.5 Count (particles per unit volume)"
        if "pm10count" in low:
            return "PM10 Count (particles per unit volume)"
        # Default: convert underscores to spaces and title-case the string.
        return param.replace("_", " ").title()

    def _include_param(self, param: str) -> bool:
        """
        True if 'param' should be treated as a plottable signal.
        Excludes meta keys and all PM *count fields.
        """
        if param in self.EXCLUDE_DISCOVERY_KEYS:
            return False
        low = param.lower()
        # Exclude specific known count names AND any general pm*count pattern
        if low in ("pm1count", "pm10count", "pm2,5count", "pm2.5count"):
            return False
        if self._PM_COUNT_RE.match(low):
            return False
        return True

    # -----------------------------
    # Parameter discovery
    # -----------------------------
    def get_available_parameters(self, station_num: int) -> dict:
        """
        Retrieve unique base parameters available from sensors (across all sensors
        at the station), in a fixed preferred order. Discovery samples the most
        recent LOOKBACK documents per sensor key and excludes known meta keys and counts.
        """
        station_info = self.db[STATIONS_INFO].find_one(
            {"station_num": station_num}, {"sensors": 1}
        )
        if not station_info or "sensors" not in station_info:
            return {}

        params_set = set()
        station_coll = self.db[f"station{station_num}"]

        for sensor_type, count in station_info["sensors"].items():
            for i in range(count):
                sensor_key = f"{sensor_type}+{i}"
                projection = {"_id": 0, "datetime": 1, sensor_key: 1}
                cursor = (
                    station_coll.find({}, projection)
                    .sort("datetime", -1)
                    .limit(self.LOOKBACK)
                )

                found_for_this_sensor = False
                for doc in cursor:
                    if sensor_key not in doc:
                        continue
                    sensor_data = doc[sensor_key]
                    if not isinstance(sensor_data, dict):
                        continue
                    for param, _value in sensor_data.items():
                        if not self._include_param(param):
                            continue
                        # Add the parameter name even if the current value is null;
                        # later records will provide numeric values for plotting.
                        params_set.add(param)
                        found_for_this_sensor = True
                    if found_for_this_sensor:
                        break  # stop scanning older docs for this sensor

        # Build label mapping and order
        param_map = {param: self._format_param_label(param) for param in params_set}
        desired_order = [
            "Temperature (\N{DEGREE SIGN}C)",
            "Humidity (%)",
            "Atmospheric Pressure (hPa)",
            "CO2 (ppm)",
            "PM1 Mass (\N{MICRO SIGN}g/m\N{SUPERSCRIPT THREE})",
            "PM2.5 Mass (\N{MICRO SIGN}g/m\N{SUPERSCRIPT THREE})",
            "PM10 Mass (\N{MICRO SIGN}g/m\N{SUPERSCRIPT THREE})",
        ]
        ordered_param_map = {}
        # First, add in the preferred order if present
        for desired in desired_order:
            for key, label in param_map.items():
                if label == desired and key not in ordered_param_map:
                    ordered_param_map[key] = label
        # Then add any remaining labels alphabetically
        for key, label in sorted(param_map.items(), key=lambda x: x[1]):
            if label not in ordered_param_map.values():
                ordered_param_map[key] = label

        return ordered_param_map

    def get_full_sensor_parameters(self, station_num: int) -> dict:
        """
        Retrieve full sensor parameters mapping:
            { base_param: [(full_key, sensor_label), ...], ... }
        where full_key = "<sensor_type>+<index>.<param>", e.g., "air_sensor+0.temperature"

        Discovery samples the most recent LOOKBACK docs per sensor key and excludes
        meta keys and 'count' params so the map is populated only with plottable signals.
        """
        station_info = self.db[STATIONS_INFO].find_one(
            {"station_num": station_num}, {"sensors": 1}
        )
        full_params: dict[str, list[tuple[str, str]]] = {}
        if not station_info or "sensors" not in station_info:
            return full_params

        station_coll = self.db[f"station{station_num}"]

        for sensor_type, count in station_info["sensors"].items():
            for i in range(count):
                sensor_key = f"{sensor_type}+{i}"
                projection = {"_id": 0, "datetime": 1, sensor_key: 1}
                cursor = (
                    station_coll.find({}, projection)
                    .sort("datetime", -1)
                    .limit(self.LOOKBACK)
                )

                found_for_this_sensor = False
                for doc in cursor:
                    if sensor_key not in doc:
                        continue
                    sensor_data = doc[sensor_key]
                    if not isinstance(sensor_data, dict):
                        continue

                    for param, _value in sensor_data.items():
                        if not self._include_param(param):
                            continue
                        base_param = param
                        full_key = f"{sensor_key}.{param}"
                        sensor_label = (
                            f"{self._format_param_label(param)} - "
                            f"{sensor_type.replace('_', ' ').title()} {i+1}"
                        )
                        full_params.setdefault(base_param, []).append((full_key, sensor_label))
                        found_for_this_sensor = True

                    if found_for_this_sensor:
                        break  # stop scanning older docs for this sensor

        return full_params

    # -----------------------------
    # Data retrieval & assembly
    # -----------------------------
    def fetch_station_data(self, station_num: int, date_range: str,
                           selected_parameters: list[str], split_view: bool) -> pd.DataFrame:
        """
        Fetch station data in UTC+4 (GST) instead of UTC.

        - date_range: "6H","12H","1D","1W","1M","6M","1Y","All"
        - selected_parameters: list of base params (e.g., ["temperature","humidity"])
        - split_view:
            True  -> keep each sensor separate (columns like 'air_sensor+0.temperature')
            False -> average across sensors for each base param
        """
        now = datetime.now(timezone.utc)
        time_deltas = {
            "6H": timedelta(hours=6),
            "12H": timedelta(hours=12),
            "1D": timedelta(days=1),
            "1W": timedelta(weeks=1),
            "1M": timedelta(days=30),
            "6M": timedelta(days=180),
            "1Y": timedelta(days=365),
        }
        start_time = now - time_deltas.get(date_range, timedelta(days=1))
        station_collection = self.db[f"station{station_num}"]
        query_filter = {"datetime": {"$gte": start_time}} if date_range != "All" else {}

        full_params = self.get_full_sensor_parameters(station_num)
        selected_full = {
            bp: full_params[bp]
            for bp in selected_parameters
            if bp in full_params
        }

        # Build projection: include datetime, each needed sensor doc, and GPS sources
        projection = {
            "_id": 0,
            "datetime": 1,
            "gps": 1,
            "date_time_position": 1,   # fallback schema
            "dateTimePosition": 1,     # alias fallback
        }
        for lst in selected_full.values():
            for key, _ in lst:
                projection[key.split('.')[0]] = 1  # include the sensor doc

        cursor = station_collection.find(query_filter, projection)

        data = []
        for record in cursor:
            entry = {"DateTime": record.get("datetime")}

            # Extract selected numeric values
            for base_param, sensor_list in selected_full.items():
                for full_key, _label in sensor_list:
                    smk, ssk = full_key.split(".", 1)
                    sensor_data = record.get(smk, {})
                    if isinstance(sensor_data, dict) and ssk in sensor_data:
                        val = sensor_data[ssk]
                        if isinstance(val, (int, float)):
                            entry[full_key] = val

            # Attach GPS: prefer gps.position; otherwise date_time_position
            gps = record.get("gps", {})
            if isinstance(gps, dict) and "position" in gps \
               and isinstance(gps["position"], list) and len(gps["position"]) >= 2:
                entry["Longitude"], entry["Latitude"] = gps["position"][0], gps["position"][1]
            else:
                # Fallback schemas
                dtp = record.get("date_time_position") or record.get("dateTimePosition")
                if isinstance(dtp, dict):
                    lon = dtp.get("longitude")
                    lat = dtp.get("latitude")
                    if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
                        entry["Longitude"], entry["Latitude"] = lon, lat

            data.append(entry)

        # Assemble DataFrame & convert timestamps to UTC+4 (GST)
        df = pd.DataFrame(data)
        if not df.empty:
            df["DateTime"] = pd.to_datetime(df["DateTime"])
            df["DateTime"] = df["DateTime"].apply(
                lambda dt: dt.replace(tzinfo=timezone.utc)
                             .astimezone(timezone(timedelta(hours=4)))
            )
            df = df.sort_values(by="DateTime")

        if split_view:
            return df
        else:
            return self.combine_sensors_for_parameters(df)

    def combine_sensors_for_parameters(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Combine sensor readings by averaging across sensors sharing the same base
        parameter; preserves DateTime (UTC+4). Keeps Latitude/Longitude if present.
        """
        if df.empty:
            return df

        combined_df = pd.DataFrame()
        combined_df["DateTime"] = df["DateTime"]

        # Group columns by base parameter (the part after the first '.')
        grouped: dict[str, list[str]] = {}
        for col in df.columns:
            if col == "DateTime":
                continue
            parts = col.split('.')
            if len(parts) == 2:
                grouped.setdefault(parts[1], []).append(col)

        # Average across sensors for each base parameter
        for param, cols in grouped.items():
            # mean() will ignore NaNs by default
            combined_df[param] = df[cols].mean(axis=1)

        # Preserve location if present
        for loc in ["Longitude", "Latitude"]:
            if loc in df.columns:
                combined_df[loc] = df[loc]

        return combined_df

    # -----------------------------
    # Aggregation & plotting
    # -----------------------------
    def aggregate_data(self, df: pd.DataFrame, freq: str) -> pd.DataFrame:
        """Aggregate data based on the selected frequency (Pandas offset alias).
           freq examples: '15T', 'H', 'D', 'None'."""
        if df.empty or "DateTime" not in df.columns or freq == "None":
            return df
        df = df.set_index("DateTime")
        numeric = df.select_dtypes(include=['number']).columns
        df_agg = df[numeric].resample(freq).mean().ffill().reset_index()
        return df_agg

    def create_iotbox_figures(self, df: pd.DataFrame,
                              selected_parameters: list[str],
                              param_mapping: dict,
                              split_view: bool) -> list[go.Figure]:
        """
        Generate Plotly figures showing DateTime in UTC+4 (GST).
        If split_view=True, each base param shows traces per individual sensor.
        Otherwise, it plots the combined (averaged) param.
        """
        figures: list[go.Figure] = []
        if df.empty:
            return figures

        legend = dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)

        if split_view:
            # Build mapping: base_param -> list of full column keys
            base_to_keys: dict[str, list[str]] = {}
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
                    if key not in df.columns:
                        continue
                    fig.add_trace(go.Scatter(
                        x=df["DateTime"],
                        y=df[key],
                        mode="markers",
                        name=f"{param_mapping.get(bp, bp)} - Sensor {i+1}",
                        marker=dict(color=palette[i % len(palette)], size=3)
                    ))
                fig.update_layout(
                    title={'text': param_mapping.get(bp, bp), 'x': 0.5, 'y': 0.97,
                           'xanchor': 'center', 'yanchor': 'top'},
                    xaxis_title="UTC+04:00 (GST)",
                    yaxis_title=param_mapping.get(bp, bp),
                    margin={"l": 40, "r": 40, "t": 40, "b": 40},
                    template="plotly_white",
                    legend=legend
                )
                figures.append(fig)

        else:
            # Combined (averaged) view: columns are base params already
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
                        title={'text': param_mapping.get(bp, bp), 'x': 0.5, 'y': 0.97,
                               'xanchor': 'center', 'yanchor': 'top'},
                        xaxis_title="UTC+04:00 (GST)",
                        yaxis_title=param_mapping.get(bp, bp),
                        margin={"l": 40, "r": 40, "t": 40, "b": 40},
                        template="plotly_white",
                        legend=legend
                    )
                    figures.append(fig)

        return figures
