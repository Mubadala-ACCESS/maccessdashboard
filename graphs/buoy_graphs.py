# buoy_graphs.py

from pymongo import MongoClient
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
import pandas as pd
import plotly.graph_objects as go
import configparser
import os

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), '../config', 'config.ini')
config.read(config_path)

# Retrieve MongoDB settings
MONGO_URI = config.get('mongodb', 'uri')
DB_NAME   = config.get('mongodb', 'database')
BUOY_01_COLLECTION = config.get('mongodb', 'buoy_01_collection')


class BuoyGraphs:
    def __init__(
        self,
        mongo_uri: str = MONGO_URI,
        db_name: str = DB_NAME,
        collection_name: str = BUOY_01_COLLECTION
    ):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

        # Ranges for filtering
        self.deltas = {
            "6H":  relativedelta(hours=6),
            "12H": relativedelta(hours=12),
            "1D":  relativedelta(days=1),
            "1W":  relativedelta(weeks=1),
            "1M":  relativedelta(months=1),
            "3M":  relativedelta(months=3),
            "6M":  relativedelta(months=6),
            "1Y":  relativedelta(years=1),
        }

        # Time-series fields
        self.scalar_params = [
            "wind_speed", "wind_direction",
            "air_temp", "barometric_pressure", "albedo"
        ]
        # Profile fields
        self.profile_params = ["CTD_tmp", "conductivity", "O2", "chlorophyll"]

        # Labels & colours
        self.param_labels = {
            "wind_speed": "Wind Speed (m/s)",
            "wind_direction": "Wind Direction (°)",
            "air_temp": "Air Temperature (°C)",
            "barometric_pressure": "Barometric Pressure (hPa)",
            "albedo": "Albedo",
            "CTD_tmp": "CTD Temperature (°C)",
            "conductivity": "Conductivity (mmho/cm)",
            "O2": "Oxygen (μM/L)",
            "chlorophyll": "Chlorophyll (µg/L)"
        }
        self.param_colors = {
            "CTD_tmp": "blue",
            "conductivity": "orange",
            "O2": "red",
            "chlorophyll": "green"
        }

    def _utc_now(self):
        return datetime.now(timezone.utc)

    def list_datetimes(self, date_range: str):
        """
        Return sorted list of UTC datetimes in the given range.
        'All' returns everything.
        """
        now = self._utc_now()
        filt = {}
        if date_range in self.deltas:
            filt = {"datetime": {"$gte": now - self.deltas[date_range]}}
        cursor = (
            self.collection
                .find(filt, {"_id": 0, "datetime": 1})
                .sort("datetime", 1)
        )
        datetimes = []
        for doc in cursor:
            dt = doc["datetime"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            datetimes.append(dt)
        return datetimes

    def fetch_time_series(self, date_range, selected_params, agg) -> pd.DataFrame:
        """
        Returns DataFrame of datetime + selected_params, filtered to non-zero values.
        """
        now = self._utc_now()
        pipeline = []
        if date_range in self.deltas:
            pipeline.append({"$match": {"datetime": {"$gte": now - self.deltas[date_range]}}})
        pipeline.append({"$sort": {"datetime": 1}})
        docs = list(self.collection.aggregate(pipeline, allowDiskUse=True))
        if not docs:
            return pd.DataFrame()

        df = pd.DataFrame(docs)
        df = df[["datetime"] + selected_params]
        # drop zeros
        for p in selected_params:
            df = df[df[p] != 0]
        return df

    def fetch_profiles(self, date_range: str):
        """
        Returns list of (datetime, profile_doc) tuples within the requested range.
        Uses the same deltas-based filtering for EVERY range.
        Zeros are left in-place so gaps show up per-parameter.
        """
        # use identical logic to time-series
        times = self.list_datetimes(date_range)

        profiles = []
        for t in times:
            doc = self.collection.find_one(
                {"datetime": t},
                {"_id": 0, "depth": 1, **{p: 1 for p in self.profile_params}}
            )
            if doc and doc.get("depth"):
                profiles.append((t, doc))

        return profiles

    def create_time_series_figures(self, df: pd.DataFrame, selected_params: list):
        figs = []
        for p in selected_params:
            if p in df.columns and not df[p].empty:
                dfi = df[df[p] != 0]
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dfi["datetime"],
                    y=dfi[p],
                    mode="markers",
                    marker=dict(size=8),
                    name=self.param_labels[p]
                ))
                fig.update_layout(
                    title=self.param_labels[p],
                    xaxis_title="DateTime (UTC)",
                    yaxis_title=self.param_labels[p],
                    template="plotly_white",
                    margin={"l": 40, "r": 20, "t": 40, "b": 40}
                )
                figs.append(fig)
        return figs

    def create_profile_figure(self, times, docs, param):
        """
        Build a heatmap for a single profile param across times & depths.
        Convert zeros to None so Plotly shows a gap.
        """
        depths = docs[0]["depth"]
        z = []
        for i in range(len(depths)):
            row = []
            for _, doc in zip(times, docs):
                vals = doc.get(param, [])
                v = vals[i] if i < len(vals) else None
                row.append(None if v == 0 or v is None else v)
            z.append(row)

        flat = [v for row in z for v in row if v is not None]
        zmin, zmax = (min(flat), max(flat)) if flat else (0, 1)

        fig = go.Figure(go.Heatmap(
            x=times,
            y=depths,
            z=z,
            colorscale="Viridis",
            zmin=zmin,
            zmax=zmax,
            xgap=1,
            ygap=1,
            showscale=True,
            hovertemplate=(
                "Time: %{x|%Y-%m-%d %H:%M UTC}<br>"
                "Depth: %{y:.2f} m<br>"
                f"{self.param_labels[param]}: %{{z:.2f}}<extra></extra>"
            )
        ))
        fig.update_layout(
            title=self.param_labels[param],
            title_x = 0.5,
            xaxis_title="Time (UTC)",
            yaxis_title="Depth (m)",
            yaxis=dict(autorange="reversed"),
            template="plotly_white",
            margin={"l":40,"r":20,"t":40,"b":40},
        )
        return fig
