# fidas_graphs.py

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
FIDAS_COLLECTION = config.get('mongodb', 'fidas_collection')

class FidasGraphs:
    def __init__(
        self,
        mongo_uri: str = MONGO_URI,
        db_name: str = DB_NAME,
        collection_name: str = FIDAS_COLLECTION
    ):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

        # All scalar fields
        self.scalar_params = [
            "PM1","PM2.5","PM4","PM10","PMtot","Cn","rH","dewT","T",
            "p","Wspeed","Wdir","Wq","prec","ptype","flowrate","velocity",
            "coincidence","po","IADS_T","cd","LED_T","errors","mode",
            "PM1a","PM2.5a","PM4a","PM10a","PMtota","PM1c","PM2.5c",
            "PM4c","PM10c","PMtotc","PMth","PMal","PMre","pT","feelLike",
            "hIdx_nws","wbgt"
        ]
        # Human‐readable labels
        self.param_labels = {
            "PM1": "PM1 (µg/m³)",        "PM2.5": "PM2.5 (µg/m³)",
            "PM4": "PM4 (µg/m³)",        "PM10": "PM10 (µg/m³)",
            "PMtot": "Total PM (µg/m³)", "Cn": "Count Number (particles/cm³)",
            "rH": "Relative Humidity (%)","dewT":"Dew Point (°C)",
            "T":"Temperature (°C)",      "p":"Pressure (hPa)",
            "Wspeed":"Wind Speed (km/h)","Wdir":"Wind Direction (°)",
            "Wq":"Wind Quality (%)",     "prec":"Precipitation Intensity (l/m²/h)",
            "ptype":"Precipitation Type","flowrate":"Flowrate (l/min)",
            "velocity":"Velocity (m/s)", "coincidence":"Coincidence (%)",
            "po":"Pump Output (%)",      "IADS_T":"IADS Temperature (°C)",
            "cd":"Channel Deviation",    "LED_T":"LED Temperature (°C)",
            "errors":"Error Flags",      "mode":"Operation Mode",
            "PM1a":"PM1 Ambient (µg/m³)","PM2.5a":"PM2.5 Ambient (µg/m³)",
            "PM4a":"PM4 Ambient (µg/m³)","PM10a":"PM10 Ambient (µg/m³)",
            "PMtota":"Total PM Ambient (µg/m³)",
            "PM1c":"PM1 Classic (µg/m³)","PM2.5c":"PM2.5 Classic (µg/m³)",
            "PM4c":"PM4 Classic (µg/m³)","PM10c":"PM10 Classic (µg/m³)",
            "PMtotc":"Total PM Classic (µg/m³)",
            "PMth":"Thoracic PM (µg/m³)","PMal":"Alveolar PM (µg/m³)",
            "PMre":"Respirable PM (µg/m³)",
            "pT":"Perceived Temperature (°C)",
            "feelLike":"Feels Like (°C)",
            "hIdx_nws":"Heat Index (°C)","wbgt":"WBGT (°C)"
        }

    def list_datetimes(self, date_range: str):
        now = datetime.now(timezone.utc)
        deltas = {
            "6H":  relativedelta(hours=6),
            "12H": relativedelta(hours=12),
            "1D":  relativedelta(days=1),
            "1W":  relativedelta(weeks=1),
            "1M":  relativedelta(months=1),
            "3M":  relativedelta(months=3),
            "6M":  relativedelta(months=6),
            "1Y":  relativedelta(years=1),
        }
        filt = {}
        if date_range in deltas:
            filt = {"datetime": {"$gte": now - deltas[date_range]}}
        cursor = (
            self.collection
                .find(filt, {"_id":0,"datetime":1})
                .sort("datetime", 1)
        )
        return [doc["datetime"] for doc in cursor]

    def fetch_time_series(
        self,
        date_range: str,
        selected_params: list,
        agg: str
    ) -> pd.DataFrame:
        now = datetime.now(timezone.utc)
        deltas = {
            "6H":  relativedelta(hours=6),
            "12H": relativedelta(hours=12),
            "1D":  relativedelta(days=1),
            "1W":  relativedelta(weeks=1),
            "1M":  relativedelta(months=1),
            "3M":  relativedelta(months=3),
            "6M":  relativedelta(months=6),
            "1Y":  relativedelta(years=1),
        }
        match_stage = {}
        if date_range in deltas:
            match_stage = {"$match": {"datetime": {"$gte": now - deltas[date_range]}}}

        # sanitize field names (no dots!)
        mapping = {p: p.replace(".", "_") for p in selected_params}

        # choose bin unit
        unit_map = {"H":"hour","D":"day","W":"week","M":"month"}
        if agg in unit_map:
            unit = unit_map[agg]
        else:
            span = deltas.get(date_range, relativedelta(days=1))
            if span.years >= 1:    unit = "month"
            elif span.months >= 3:  unit = "week"
            elif span.days >= 30:   unit = "day"
            else:                   unit = "hour"

        group_stage = {"$group": {"_id": {
            "$dateTrunc": {"date": "$datetime", "unit": unit, "binSize": 1}
        }}}
        # add sanitized avg fields
        for orig, safe in mapping.items():
            group_stage["$group"][safe] = {"$avg": f"${orig}"}

        pipeline = []
        if match_stage:
            pipeline.append(match_stage)
        pipeline += [group_stage, {"$sort": {"_id": 1}}]

        result = list(self.collection.aggregate(pipeline, allowDiskUse=True))
        if not result:
            return pd.DataFrame()

        df = pd.DataFrame(result)
        # rename _id to datetime, safe -> orig
        df = df.rename(columns={"_id": "datetime", **{s: o for o,s in mapping.items()}})
        return df

    def fetch_spectrum_doc(self, dt: datetime):
        return self.collection.find_one(
            {"datetime": dt},
            {"_id":0,"sizes":1,"spectra":1}
        )

    def create_time_series_figures(self, df: pd.DataFrame, selected_params: list):
        figs = []
        for p in selected_params:
            if p in df.columns:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df["datetime"], y=df[p],
                    mode="markers",
                    name=self.param_labels[p]
                ))
                fig.update_layout(
                    title=self.param_labels[p],
                    xaxis_title="DateTime",
                    yaxis_title=self.param_labels[p],
                    template="plotly_white",
                    margin={"l":40,"r":20,"t":40,"b":40}
                )
                figs.append(fig)
        return figs

    def create_spectrum_figure(self, sizes, spectra):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sizes, y=spectra, mode="lines+markers"))
        fig.update_layout(
            xaxis_type="log", yaxis_type="log",
            xaxis_title="Size (µm)",
            yaxis_title="Particle Count (particles/cm³)",
            template="plotly_white",
            margin={"l":40,"r":20,"t":40,"b":40}
        )
        return fig
