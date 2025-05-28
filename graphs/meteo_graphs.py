import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, callback, State
import dash_daq as daq
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
F1_METEO_COLLECTION = config.get('mongodb', 'f1_meteo_collection')


class meteostationGraphs:
    def __init__(self):
        from pymongo import MongoClient
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.collection = self.db[F1_METEO_COLLECTION]
        self.label_map = {
            "I3_VPOWER": "Voltage Power (V)",
            "I4_VOUT": "Voltage Output (V)",
            "S1_RAD": "Radiation (W/m²)",
            "S2_DP[C]": "Dew Point (°C)",
            "S2_PA": "Atmospheric Pressure (hPa)",
            "S2_PREC[MM]": "Precipitation (mm)",
            "S2_RH[%]": "Relative Humidity (%)",
            "S2_TA[C]": "Temperature (°C)",
            "S2_WD": "Wind Direction (°)",
            "S2_WS[M/S]": "Wind Speed (m/s)"
        }
    
    def _format_param_label(self, param):
        return self.label_map.get(param, param)
    
    def fetch_data(self, date_range="1D"):
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
        if date_range != "All":
            start_time = now - time_deltas.get(date_range, timedelta(days=1))
            query = {"Timestamp": {"$gte": start_time}}
        else:
            query = {}
        cursor = self.collection.find(query, {"_id": 0})
        data = list(cursor)
        df = pd.DataFrame(data)
        if not df.empty:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"])
            df = df.sort_values("Timestamp")
        return df

    def aggregate_data(self, df, freq):
        if df.empty or "Timestamp" not in df.columns:
            return df
        # Convert sensor columns to numeric
        for col in df.columns:
            if col != "Timestamp":
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # Ensure data is sorted by Timestamp
        df = df.sort_values("Timestamp")
        df.set_index("Timestamp", inplace=True)
        numeric_cols = df.select_dtypes(include=["number"]).columns
        df_agg = df[numeric_cols].resample(freq).mean().reset_index()
        df_agg.fillna(method="ffill", inplace=True)
        df_agg = df_agg.sort_values("Timestamp")
        return df_agg

    def create_figures(self, df, selected_parameters):
        figures = []
        if df.empty:
            return figures
        legend_settings = dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5
        )
        for param in selected_parameters:
            if param in df.columns:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df["Timestamp"],
                    y=df[param],
                    mode="markers",
                    name=self._format_param_label(param),
                    marker=dict(size=5)
                ))
                fig.update_layout(
                    title={
                        'text': self._format_param_label(param),
                        'x': 0.5,
                        'y': 0.97,
                        'xanchor': 'center',
                        'yanchor': 'top'
                    },
                    xaxis_title="Timestamp",
                    yaxis_title=self._format_param_label(param),
                    margin={"l": 40, "r": 40, "t": 40, "b": 40},
                    template="plotly_white",
                    legend=legend_settings
                )
                figures.append(fig)
        return figures

    def close_connection(self):
        self.client.close()