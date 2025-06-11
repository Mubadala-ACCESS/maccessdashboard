#!/usr/bin/env python3

import os
import math
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import gsw
import plotly.graph_objects as go

from pymongo import MongoClient
from dateutil.relativedelta import relativedelta
import configparser

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__),
                           '../config', 'config.ini')
config.read(config_path)

# Retrieve MongoDB settings
MONGO_URI          = config.get('mongodb', 'uri')
DB_NAME            = config.get('mongodb', 'database')
BUOY_01_COLLECTION = config.get('mongodb', 'buoy_01_collection')

# Offset for Gulf Standard Time
GST_OFFSET = timedelta(hours=4)

# Buoy coordinates for Absolute Salinity calculation
BUOY_LAT = 24.992
BUOY_LON = 54.350


class BuoyGraphs:
    def __init__(self,
                 mongo_uri: str = MONGO_URI,
                 db_name: str = DB_NAME,
                 collection_name: str = BUOY_01_COLLECTION):
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

        # Scalar vs. profile fields
        self.scalar_params  = [
            "wind_speed", "wind_direction",
            "air_temp", "barometric_pressure", "albedo"
        ]
        self.profile_params = [
            "CTD_tmp", "conductivity", "O2", "chlorophyll",
            "salinity_practical", "salinity_absolute", "density"
        ]

        # Labels & colours
        self.param_labels = {
            "wind_speed":          "Wind Speed (m/s)",
            "wind_direction":      "Wind Direction (°)",
            "air_temp":            "Air Temperature (°C)",
            "barometric_pressure": "Barometric Pressure (hPa)",
            "albedo":              "Albedo",
            "CTD_tmp":             "CTD Temperature (°C)",
            "conductivity":        "Conductivity (mmho/cm)",
            "O2":                  "Oxygen (µM/L)",
            "chlorophyll":         "Chlorophyll (µg/L)",
            "salinity_practical":  "Practical Salinity (PSU)",
            "salinity_absolute":   "Absolute Salinity (g/kg)",
            "density":             "Density (kg/m³)"
        }
        self.param_colors = {
            "CTD_tmp":             "blue",
            "conductivity":        "orange",
            "O2":                  "red",
            "chlorophyll":         "green",
            "salinity_practical":  "teal",
            "salinity_absolute":   "purple",
            "density":             "black"
        }

    def _utc_now(self) -> datetime:
        return datetime.utcnow()

    def fetch_time_series(self,
                          date_range: str,
                          selected_params: list[str],
                          agg=None) -> pd.DataFrame:
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
        df["datetime"] += GST_OFFSET
        for p in selected_params:
            df = df[df[p] != 0]
        return df

    def fetch_profiles(self,
                       date_range: str
                       ) -> tuple[list[datetime], list[dict]]:
        now    = self._utc_now()
        cutoff = now - self.deltas.get(date_range, relativedelta())

        # Single aggregation
        proj = {"_id": 0, "datetime": 1, "depth": 1}
        for p in ["CTD_tmp", "conductivity", "O2", "chlorophyll"]:
            proj[p] = 1

        pipeline = [
            {"$match":  {"datetime": {"$gte": cutoff}}},
            {"$sort":   {"datetime": 1}},
            {"$project": proj}
        ]
        raw = list(self.collection.aggregate(pipeline, allowDiskUse=True))

        # Filter out zero‐depth docs
        raw = [d for d in raw if d["depth"] and any(v != 0 for v in d["depth"])]
        if not raw:
            fb = self.collection.find_one(
                {}, projection=proj, sort=[("datetime",1)]
            )
            if fb and any(v!=0 for v in fb["depth"]):
                return [fb["datetime"]+GST_OFFSET], [fb]
            return [], []

        # Trim and compute new metrics
        processed = []
        for d in raw:
            mask = [depth>0 for depth in d["depth"]]
            trimmed = {
                "datetime": d["datetime"],
                "depth":    [dep for dep,m in zip(d["depth"], mask) if m]
            }
            # original profiles
            for p in ["CTD_tmp", "conductivity", "O2", "chlorophyll"]:
                trimmed[p] = [val for val,m in zip(d[p], mask) if m]

            # Compute salinity & density arrays
            depths = np.array(trimmed["depth"])
            conds  = np.array(trimmed["conductivity"])
            temps  = np.array(trimmed["CTD_tmp"])

            # Practical Salinity
            SP = gsw.SP_from_C(conds, temps, depths)

            # Absolute Salinity
            SA = gsw.SA_from_SP(SP, depths, lon=BUOY_LON, lat=BUOY_LAT)

            # Conservative Temperature
            CT = gsw.CT_from_t(SA, temps, depths)

            # In-situ density
            rho = gsw.rho(SA, CT, depths)

            trimmed["salinity_practical"] = SP.tolist()
            trimmed["salinity_absolute"]  = SA.tolist()
            trimmed["density"]            = rho.tolist()

            processed.append(trimmed)

        # Shift to GST
        times = [d["datetime"] + GST_OFFSET for d in processed]

        # Bin & average for longer ranges
        if date_range in ("1W","1M","3M","6M","1Y"):
            return self._aggregate_profiles_by_period(date_range, times, processed)

        return times, processed

    def _aggregate_profiles_by_period(self,
                                      date_range: str,
                                      times: list[datetime],
                                      docs: list[dict]
                                      ) -> tuple[list[datetime], list[dict]]:
        bin_hours = {"1W":3,"1M":6,"3M":12,"6M":24,"1Y":48}
        width = timedelta(hours=bin_hours[date_range])

        df = pd.DataFrame({"datetime": pd.to_datetime(times), "doc": docs})
        df["bin"] = df["datetime"].dt.floor(f"{bin_hours[date_range]}H")
        grouped = {b:list(g["doc"]) for b,g in df.groupby("bin")}

        start, end = min(grouped), max(grouped)
        all_bins, agg_docs = [], []
        t = start
        template_depth = docs[0]["depth"]
        n = len(template_depth)

        while t <= end:
            docs_in_bin = grouped.get(t, [])
            agg = {"datetime": t, "depth": template_depth.copy()}
            for param in self.profile_params:
                if docs_in_bin:
                    arrs = []
                    for gd in docs_in_bin:
                        vals = gd.get(param, [])
                        vals = (vals + [None]*n)[:n]
                        arrs.append([np.nan if v is None else float(v) for v in vals])
                    mat = np.vstack(arrs)
                    mat[mat==0] = np.nan
                    means = np.nanmean(mat, axis=0)
                    agg[param] = [None if math.isnan(v) else v for v in means]
                else:
                    agg[param] = [None]*n
            all_bins.append(t)
            agg_docs.append(agg)
            t += width

        return all_bins, agg_docs

    def create_time_series_figures(self,
                                   df: pd.DataFrame,
                                   selected_params: list[str]
                                   ) -> list[go.Figure]:
        figs = []
        for p in selected_params:
            if p in df.columns and not df[p].empty:
                dfi = df[df[p] != 0]
                if len(dfi) > 50000:
                    step = math.ceil(len(dfi)/50000)
                    dfi = dfi.iloc[::step]
                fig = go.Figure(go.Scattergl(
                    x=dfi["datetime"], y=dfi[p],
                    mode="markers",
                    marker=dict(size=6, color=self.param_colors.get(p)),
                    name=self.param_labels[p]
                ))
                fig.update_layout(
                    title=self.param_labels[p],
                    xaxis_title="Time (GST, UTC+04:00)",
                    yaxis_title=self.param_labels[p],
                    template="plotly_white",
                    margin={"l":40,"r":20,"t":40,"b":40},
                    autosize=True
                )
                figs.append(fig)
        return figs

    def create_profile_figure(self,
                              times: list[datetime],
                              docs: list[dict],
                              param: str
                              ) -> go.Figure:
        depths = docs[0]["depth"]
        z = [
            [
                None if i >= len(doc.get(param, [])) or doc[param][i] == 0
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
                "Time (GST): %{x|%Y-%m-%d %H:%M}<br>"
                "Depth: %{y:.2f} m<br>"
                f"{self.param_labels[param]}: %{{z:.2f}}<extra></extra>"
            )
        ))
        fig.update_layout(
            title=self.param_labels[param],
            xaxis_title="Time (GST, UTC+04:00)",
            yaxis=dict(autorange="reversed"),
            template="plotly_white",
            margin={"l":40,"r":20,"t":40,"b":40},
            autosize=True
        )
        return fig
