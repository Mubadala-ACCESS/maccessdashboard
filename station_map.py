# station_map.py
from dash import html
import dash_leaflet as dl
from pymongo import MongoClient
import pandas as pd
import numpy as np
import math
from typing import List, Dict, Tuple
import configparser
import os

config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.ini')
config.read(config_path)

STATIONS_INFO = config.get('mongodb', 'stations_info_collection')

class StationMap:
    def __init__(self, mongo_uri: str, db_name: str):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.device_type_labels = {
            "IoTBox": "IoT Box",
            "Meteorological": "Meteorological Station",
            "Buoy": "Buoy",
            "Fidas_Palas": "Fidas Palas 200S",
            "SBNTransect": "Sir Abu Nu'Ayr Transect",
            "JWCruise": "Jaywun Cruise",
            "underwater_probe": "Underwater Probes",
            "coral_reef": "Coral Reef Monitoring"
        }

    def fetch_station_data(self) -> List[Dict[str, str]]:
        collection = self.db[STATIONS_INFO]
        stations = collection.find({"lat": {"$ne": None}, "long": {"$ne": None}})
        return [
            {
                "Station Num": s.get("station_num"),
                "Station Name": s.get("name") or f"Station {s.get('station_num')}",
                "Latitude": s.get("lat"),
                "Longitude": s.get("long"),
                "Device Type": s.get("type", "Unknown"),
                "Status": s.get("status", "Unknown"),
                "Station ID": s.get("id"),
                "Privacy": s.get("public"),
            }
            for s in stations
        ]

    def get_station_time_series(self, station_num: str, start_date: str, end_date: str):
        collection = self.db[f"station{station_num}"]
        query = {}
        if start_date or end_date:
            query["datetime"] = {}
            if start_date:
                query["datetime"]["$gte"] = pd.to_datetime(start_date)
            if end_date:
                query["datetime"]["$lte"] = pd.to_datetime(end_date)
        cursor = collection.find(query, {"_id": 0, "datetime": 1})
        df = pd.DataFrame([{"DateTime": r["datetime"]} for r in cursor])
        if not df.empty:
            df["DateTime"] = pd.to_datetime(df["DateTime"])
            df = df.sort_values("DateTime")
        return df

    def fetch_station_location_data(self) -> Tuple[float, float]:
        collection = self.db[STATIONS_INFO]
        stations = collection.find({"lat": {"$ne": None}, "long": {"$ne": None}})
        lats = [s["lat"] for s in stations]
        longs = [s["long"] for s in stations]
        if not lats:
            return None
        return float(np.mean(lats)), float(np.mean(longs))

    def create_map(self, station_data: List[Dict[str, str]]):
        for s in station_data:
            s["true_lat"] = s["Latitude"]
            s["true_lon"] = s["Longitude"]

        coord_groups: Dict[Tuple[float, float], List[int]] = {}
        for i, s in enumerate(station_data):
            try:
                lat = float(s["true_lat"])
                lon = float(s["true_lon"])
            except (TypeError, ValueError):
                continue
            coord_groups.setdefault((lat, lon), []).append(i)

        for (lat, lon), idxs in coord_groups.items():
            if len(idxs) > 1:
                step = 2 * math.pi / len(idxs)
                r = 0.0003
                for j, idx in enumerate(idxs):
                    station_data[idx]["display_lat"] = lat + r * math.sin(j * step)
                    station_data[idx]["display_lon"] = lon + r * math.cos(j * step)
            else:
                station_data[idxs[0]]["display_lat"] = lat
                station_data[idxs[0]]["display_lon"] = lon

        markers = []
        active = []
        icon_map = {
            "IoTBox": "iotbox.png",
            "Meteorological": "meteostation.png",
            "Buoy": "buoy.png",
            "Fidas_Palas": "fidas.png",
            "SBNTransect": "transect.png",
            "JWCruise": "cruise.png",
            "underwater_probe": "underwater.png",
            "coral_reef": "coral.png"
        }

        for s in station_data:
            if s.get("Status") == "Offline":
                continue
            try:
                lat0 = float(s["true_lat"])
                lon0 = float(s["true_lon"])
                dlat = float(s["display_lat"])
                dlon = float(s["display_lon"])
            except (TypeError, ValueError):
                continue

            active.append((dlat, dlon))
            dt = s.get("Device Type", "Unknown")
            label = self.device_type_labels.get(dt, dt)
            icon = dict(
                iconUrl=f"/assets/{icon_map.get(dt, 'buoy.png')}",
                iconSize=[60, 60],
                iconAnchor=[30, 30],
                popupAnchor=[0, -30]
            )

            # both links now use btn-link styling
            if dt in ["SBNTransect", "JWCruise", "underwater_probe", "coral_reef"]:
                base = html.A(
                    "Station Data",
                    href=f"https://nyuadmaccess.org/login?next=/dashboard?open_station={s['Station ID']}",
                    target="_self",
                    className="btn btn-link",
                    style={"padding": 0, "color": "blue"}
                )
            elif dt == "Fidas_Palas":
                base = html.A(
                    "Station Data",
                    href="http://10.224.41.15",
                    target="_blank",
                    className="btn btn-link",
                    style={"padding": 0, "color": "blue"}
                )
            else:
                base = html.A(
                    "View All Station Data",
                    href=f"/stationdata/{dt}/{s['Station Num']}",
                    target="_self",
                    className="btn btn-link",
                    style={"padding": 0, "color": "blue"}
                )

            meta_btn = html.Button(
                "Station Metadata",
                id={
                    "type": "metadata-button",
                    "station": s["Station ID"],
                    "device": dt
                },
                n_clicks=0,
                className="btn btn-link",
                style={"marginLeft": "10px", "padding": 0,"color": "blue" }
            )

            popup = html.Div([
                html.P(f"Name: {s['Station Name']}"),
                html.P(f"Type: {label}"),
                html.P(f"Location: ({lat0:.3f}, {lon0:.3f})"),
                html.Div([base, meta_btn], style={"display": "flex", "alignItems": "center"})
            ])

            markers.append(dl.Marker(
                position=(dlat, dlon),
                icon=icon,
                bubblingMouseEvents=False,
                children=dl.Popup([popup])
            ))

        if active:
            if len(active) > 1:
                lats = [c[0] for c in active]
                lons = [c[1] for c in active]
                map_args = {"bounds": [[min(lats), min(lons)], [max(lats), max(lons)]]}
            else:
                map_args = {"center": active[0], "zoom": 12}
        else:
            map_args = {"center": [24.53, 54.43], "zoom": 8}

        return dl.Map(
            children=[dl.TileLayer(), dl.LayerGroup(markers)],
            style={"height": "100%", "width": "100%"},
            **map_args
        )

    def close_connection(self):
        self.client.close()
