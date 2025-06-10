# graphs/buoy_graphs.py

from pymongo import MongoClient
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import configparser
import os
import math

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), '../config', 'config.ini')
config.read(config_path)

# Retrieve MongoDB settings
MONGO_URI          = config.get('mongodb', 'uri')
DB_NAME            = config.get('mongodb', 'database')
BUOY_01_COLLECTION = config.get('mongodb', 'buoy_01_collection')


class BuoyGraphs:
    def __init__(
        self,
        mongo_uri: str = MONGO_URI,
        db_name: str = DB_NAME,
        collection_name: str = BUOY_01_COLLECTION
    ):
        self.client     = MongoClient(mongo_uri)
        self.db         = self.client[db_name]
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

        # Time-series (scalar) fields
        self.scalar_params = [
            "wind_speed", "wind_direction",
            "air_temp", "barometric_pressure", "albedo"
        ]

        # Profile (vertical) fields
        self.profile_params = ["CTD_tmp", "conductivity", "O2", "chlorophyll"]

        # Labels & colours
        self.param_labels = {
            "wind_speed":          "Wind Speed (m/s)",
            "wind_direction":      "Wind Direction (°)",
            "air_temp":            "Air Temperature (°C)",
            "barometric_pressure": "Barometric Pressure (hPa)",
            "albedo":              "Albedo",
            "CTD_tmp":             "CTD Temperature (°C)",
            "conductivity":        "Conductivity (mmho/cm)",
            "O2":                  "Oxygen (μM/L)",
            "chlorophyll":         "Chlorophyll (µg/L)"
        }
        self.param_colors = {
            "CTD_tmp":     "blue",
            "conductivity":"orange",
            "O2":          "red",
            "chlorophyll": "green"
        }

    def _utc_now(self) -> datetime:
        return datetime.utcnow()

    def fetch_time_series(
        self,
        date_range: str,
        selected_params: list[str],
        agg=None
    ) -> pd.DataFrame:
        now = self._utc_now()
        pipeline = []
        if date_range in self.deltas:
            cutoff = now - self.deltas[date_range]
            pipeline.append({"$match": {"datetime": {"$gte": cutoff}}})
        pipeline.append({"$sort": {"datetime": 1}})
        docs = list(self.collection.aggregate(pipeline, allowDiskUse=True))
        if not docs:
            return pd.DataFrame()
        df = pd.DataFrame(docs)[["datetime"] + selected_params]
        for p in selected_params:
            df = df[df[p] != 0]
        return df

    def fetch_profiles(self, date_range: str) -> tuple[list[datetime], list[dict]]:
        now    = self._utc_now()
        cutoff = now - self.deltas.get(date_range, relativedelta())

        # Single aggregation for all periods
        proj = {"_id": 0, "datetime": 1, "depth": 1}
        for p in self.profile_params:
            proj[p] = 1

        pipeline = [
            {"$match": {"datetime": {"$gte": cutoff}}},
            {"$sort":  {"datetime": 1}},
            {"$project": proj},
        ]
        docs = list(self.collection.aggregate(pipeline, allowDiskUse=True))
        docs = [d for d in docs if d["depth"] and any(v != 0 for v in d["depth"])]
        if not docs:
            fb = self.collection.find_one({}, projection=proj, sort=[("datetime",1)])
            if fb and fb["depth"] and any(v!=0 for v in fb["depth"]):
                return [fb["datetime"]], [fb]
            return [], []

        times = [d["datetime"] for d in docs]

        # bin & average for monthly+ ranges
        if date_range in ("1M","3M","6M","1Y"):
            return self._aggregate_profiles_by_period(date_range, times, docs)

        return times, docs

    def _aggregate_profiles_by_period(
        self,
        date_range: str,
        times: list[datetime],
        docs: list[dict]
    ) -> tuple[list[datetime], list[dict]]:
        bin_hours = {"1M": 3, "3M": 6, "6M": 12, "1Y": 24}
        df = pd.DataFrame({"datetime": pd.to_datetime(times), "doc": docs})
        freq = f"{bin_hours[date_range]}H"
        df["bin"] = df["datetime"].dt.floor(freq)

        agg_times, agg_docs = [], []
        for bin_time, group in df.groupby("bin"):
            group_docs   = list(group["doc"])
            depth_length = len(group_docs[0]["depth"])
            agg = {"datetime": bin_time.to_pydatetime(),
                   "depth":    group_docs[0]["depth"]}

            for param in self.profile_params:
                arrays = []
                for gd in group_docs:
                    vals = gd.get(param, [])
                    # pad with None rather than 0 for missing
                    if len(vals) < depth_length:
                        vals = vals + [None] * (depth_length - len(vals))
                    else:
                        vals = vals[:depth_length]
                    # convert None→nan, keep real zeros masked
                    arr = [np.nan if v is None or v == 0 else float(v) for v in vals]
                    arrays.append(arr)

                arr2d = np.vstack(arrays)
                # compute mean ignoring nan
                means = np.nanmean(arr2d, axis=0)
                # map nan→None so heatmap shows gaps
                agg[param] = [None if math.isnan(v) else v for v in means.tolist()]

            agg_times.append(bin_time.to_pydatetime())
            agg_docs.append(agg)

        return agg_times, agg_docs

    def create_time_series_figures(
        self,
        df: pd.DataFrame,
        selected_params: list[str]
    ) -> list[go.Figure]:
        figs = []
        for p in selected_params:
            if p in df.columns and not df[p].empty:
                dfi = df[df[p] != 0]
                max_pts = 50000
                if len(dfi) > max_pts:
                    step = math.ceil(len(dfi) / max_pts)
                    dfi = dfi.iloc[::step]
                fig = go.Figure(go.Scattergl(
                    x=dfi["datetime"], y=dfi[p],
                    mode="markers", marker=dict(size=6),
                    name=self.param_labels[p]
                ))
                fig.update_layout(
                    title=self.param_labels[p],
                    xaxis_title="DateTime (UTC)",
                    yaxis_title=self.param_labels[p],
                    template="plotly_white",
                    margin={"l":40,"r":20,"t":40,"b":40},
                    autosize=True
                )
                figs.append(fig)
        return figs

    def create_profile_figure(
        self,
        times: list[datetime],
        docs: list[dict],
        param: str
    ) -> go.Figure:
        depths = docs[0]["depth"]
        z = [
            [
                None if (i >= len(doc.get(param, [])) or doc[param][i] == 0)
                else doc[param][i]
                for doc in docs
            ]
            for i in range(len(depths))
        ]
        flat = [v for row in z for v in row if v is not None]
        zmin, zmax = (min(flat), max(flat)) if flat else (0, 1)

        fig = go.Figure(go.Heatmap(
            x=times, y=depths, z=z,
            colorscale="Viridis", zmin=zmin, zmax=zmax,
            xgap=1, ygap=1, showscale=True,
            hovertemplate=(
                "Time: %{x|%Y-%m-%d %H:%M UTC}<br>"
                "Depth: %{y:.2f} m<br>"
                f"{self.param_labels[param]}: %{{z:.2f}}<extra></extra>"
            )
        ))
        fig.update_layout(
            title=self.param_labels[param],
            yaxis=dict(autorange="reversed"),
            template="plotly_white",
            margin={"l":40,"r":20,"t":40,"b":40},
            autosize=True
        )
        return fig
