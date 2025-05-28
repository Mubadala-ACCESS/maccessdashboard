from dash import html, Dash
import dash_leaflet as dl
from pymongo import MongoClient
import pandas as pd
import numpy as np
import math
from typing import List, Dict, Tuple
import configparser
import os

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.ini')
config.read(config_path)

# Retrieve MongoDB settings
STATIONS_INFO = config.get('mongodb', 'stations_info_collection')

class StationMap:
    def __init__(self, mongo_uri: str, db_name: str):
        """Initialize connection to MongoDB and device type mapping."""
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        # Mapping of device type codes to friendly labels
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
        """Fetch station data from MongoDB, filtering out entries without coordinates."""
        collection = self.db[STATIONS_INFO]
        query = {"lat": {"$ne": None}, "long": {"$ne": None}}
        stations = collection.find(query)
        station_data = [
            {
                "Station Num": station.get("station_num"),
                "Station Name": station.get("name") if station.get("name")
                                else f"Station {station.get('station_num')}",
                "Latitude": station.get("lat"),
                "Longitude": station.get("long"),
                "Device Type": station.get("type", "Unknown"),
                "Status": station.get("status", "Unknown"),
                "Station ID": station.get("id"),
                "Privacy": station.get("public"),
            }
            for station in stations
        ]
        return station_data

    def get_station_time_series(self, station_num: str, start_date: str, end_date: str):
        """Fetch time-series data for a specific station within a date range."""
        station_collection = self.db[f"station{station_num}"]
        query_filter = {}
        if start_date or end_date:
            query_filter["datetime"] = {}
            if start_date:
                query_filter["datetime"]["$gte"] = pd.to_datetime(start_date)
            if end_date:
                query_filter["datetime"]["$lte"] = pd.to_datetime(end_date)
        projection = {"_id": 0, "datetime": 1}
        cursor = station_collection.find(query_filter, projection)
        data = [{"DateTime": record.get("datetime")} for record in cursor]
        df = pd.DataFrame(data)
        if not df.empty:
            df["DateTime"] = pd.to_datetime(df["DateTime"])
            df = df.sort_values(by="DateTime")
        return df

    def fetch_station_location_data(self) -> Tuple[float, float]:
        """Calculate the centroid of all station coordinates."""
        collection = self.db[STATIONS_INFO]
        query = {"lat": {"$ne": None}, "long": {"$ne": None}}
        stations = collection.find(query)
        latitudes = []
        longitudes = []
        for station in stations:
            latitudes.append(station.get("lat"))
            longitudes.append(station.get("long"))
        if not latitudes or not longitudes:
            return None  # No valid coordinates found.
        center_lat = np.mean(latitudes)
        center_long = np.mean(longitudes)
        return center_lat, center_long

    def create_map(self, station_data: List[Dict[str, str]]):
        """
        Generate a Dash Leaflet map with markers. If multiple stations share
        the exact same (lat, long), offset them slightly so they're individually clickable.
        """
        # Preserve the original coordinates in new keys (true_lat/true_lon)
        for station in station_data:
            station["true_lat"] = station.get("Latitude")
            station["true_lon"] = station.get("Longitude")

        # 1) Group stations by exact (true_lat, true_lon)
        coord_groups = {}
        for i, station in enumerate(station_data):
            true_lat = station.get("true_lat")
            true_lon = station.get("true_lon")
            if true_lat is None or true_lon is None:
                continue
            coord = (float(true_lat), float(true_lon))
            if coord not in coord_groups:
                coord_groups[coord] = []
            coord_groups[coord].append(i)

        # 2) For groups sharing the same coordinate, compute a separate display coordinate
        #    and store in new keys without modifying the true coordinates.
        for coord, indices in coord_groups.items():
            if len(indices) > 1:
                angle_step = 2 * math.pi / len(indices)
                radius = 0.0003  # Adjust for how far you want them spread
                for j, idx in enumerate(indices):
                    station_data[idx]["display_lat"] = coord[0] + radius * math.sin(j * angle_step)
                    station_data[idx]["display_lon"] = coord[1] + radius * math.cos(j * angle_step)
            else:
                idx = indices[0]
                station_data[idx]["display_lat"] = coord[0]
                station_data[idx]["display_lon"] = coord[1]

        # 3) Create markers
        markers = []
        active_coords = []

        # Map device types to icon filenames (files should exist in your assets folder)
        icon_mapping = {
            "IoTBox": "iotbox.png",
            "JWCruise": "cruise.png",
            "SBNTransect": "transect.png",
            "Buoy": "buoy.png",
            "Fidas_Palas": "fidas.png",
            "Meteorological": "meteostation.png",
            "underwater_probe": "underwater.png",
            "coral_reef": "coral.png",
        }

        for station in station_data:
            true_lat = station.get("true_lat")
            true_lon = station.get("true_lon")
            display_lat = station.get("display_lat", true_lat)
            display_lon = station.get("display_lon", true_lon)
            status = station.get("Status")
            if true_lat is None or true_lon is None:
                continue
            if status == "Offline":
                continue

            # IMPORTANT CHANGE #1: use display coords for bounding/zoom
            active_coords.append((float(display_lat), float(display_lon)))

            # Use the true coordinates in the popup text
            latitude_str = f"{float(true_lat):.3f}"
            longitude_str = f"{float(true_lon):.3f}"

            device_type = station.get("Device Type", "Unknown")
            # Use the dictionary to get a friendly label for the device type
            display_type = self.device_type_labels.get(device_type, device_type)

            # Choose icon based on device type; fallback to "buoy.png"
            icon_file = icon_mapping.get(device_type, "buoy.png")
            # IMPORTANT CHANGE #2: adjust icon anchors so you must click the icon itself
            custom_icon = dict(
                iconUrl=f"/assets/{icon_file}",
                iconSize=[60, 60],
                iconAnchor=[30, 30],
                popupAnchor=[0, -30]
            )

            # Popup logic: use display_type for the type label
            if device_type in ["SBNTransect", "JWCruise", "underwater_probe", "coral_reef"]:
                popup_content = html.Div([
                    html.P(f"Name: {station.get('Station Name', 'N/A')}"),
                    html.P(f"Type: {display_type}"),
                    html.P(f"Location: ({latitude_str}, {longitude_str})"),
                    html.A("View All Station Data", 
                           href=f"https://nyuadmaccess.org/login?next=/dashboard?open_station={station.get('Station ID')}", 
                           target="_self")
                ])
            elif device_type == "Fidas_Palas":
                # Link to internal IP in a new tab
                popup_content = html.Div([
                    html.P(f"Name: {station.get('Station Name', 'N/A')}"),
                    html.P(f"Type: {display_type}"),
                    html.P(f"Location: ({latitude_str}, {longitude_str})"),
                    html.P(html.A("View All Station Data",
                                  href="http://10.224.41.15",
                                  target="_blank"))
                ])
            else:
                # Default popup
                popup_content = html.Div([
                    html.P(f"Name: {station.get('Station Name', 'N/A')}"),
                    html.P(f"Type: {display_type}"),
                    html.P(f"Location: ({latitude_str}, {longitude_str})"),
                    html.P(html.A("View All Station Data",
                                  href=f"/stationdata/{device_type}/{station.get('Station Num')}",
                                  target="_self"))
                ])

            # IMPORTANT CHANGE #3: set bubblingMouseEvents=False to limit popup to direct clicks on icon
            markers.append(
                dl.Marker(
                    position=(display_lat, display_lon),
                    icon=custom_icon,
                    bubblingMouseEvents=False,
                    children=dl.Popup([popup_content])
                )
            )

        # 4) Determine map bounds/zoom from display coords
        if active_coords:
            if len(active_coords) > 1:
                min_lat = min(c[0] for c in active_coords)
                max_lat = max(c[0] for c in active_coords)
                min_lon = min(c[1] for c in active_coords)
                max_lon = max(c[1] for c in active_coords)
                bounds = [[min_lat, min_lon], [max_lat, max_lon]]
                map_args = {"bounds": bounds}
            else:
                # Only one marker
                center_coords = active_coords[0]
                map_args = {"center": center_coords, "zoom": 12}
        else:
            # Fallback if no markers
            map_args = {"center": [24.53, 54.43], "zoom": 8}

        # 5) Build the map
        return dl.Map(
            children=[
                dl.TileLayer(),
                dl.LayerGroup(markers)
            ],
            style={"height": "100%", "width": "100%"},
            **map_args
        )

    def close_connection(self):
        """Close the MongoDB connection."""
        self.client.close()

