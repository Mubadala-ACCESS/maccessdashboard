import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, callback
import pandas as pd
from station_map import StationMap
import configparser
import os

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), '../config', 'config.ini')
config.read(config_path)

# Retrieve MongoDB settings
MONGO_URI = config.get('mongodb', 'uri')
DB_NAME   = config.get('mongodb', 'database')

# Register this as the home page
dash.register_page(__name__, path="/", title="Station Monitoring Dashboard")


# Initialize StationMap
station_map = StationMap(mongo_uri=MONGO_URI, db_name=DB_NAME)

# Main layout (Navbar is in `app.py`)
layout = dbc.Container([
    dcc.Location(id="url", refresh=False),

    # Sidebar with filters and table
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Search", style={"font-weight": "bold"}),
                            dbc.InputGroup([
                                dcc.Input(
                                    id="search-input",
                                    type="text",
                                    placeholder="Search by station name or number",
                                    debounce=True,
                                    style={"flex": "1", "minWidth": "0"}
                                ),
                                dbc.Button("Search", id="search-button", n_clicks=0,
                                           style={"backgroundColor": "purple", "color": "white", "flex": "0 0 auto"})
                            ], style={"display": "flex", "width": "100%"})
                        ], width=12),
                        
                        dbc.Col([
                            html.Label("Privacy", style={"font-weight": "bold"}),
                            dcc.Dropdown(
                                id="privacy-dropdown",
                                options=[
                                    {"label": "All", "value": "all"},
                                    {"label": "Public", "value": True},
                                    {"label": "Private", "value": False},
                                ],
                                value="all",
                                placeholder="Privacy"
                            )
                        ], width=12),

                        dbc.Col([
                            html.Label("Station Type", style={"font-weight": "bold"}),
                            dcc.Dropdown(
                                id="type-dropdown",
                                options=[
                                    {"label": "All", "value": "all"},
                                    {"label": "IoT Box", "value": "IoTBox"},
                                    {"label": "Meteorological Station", "value": "Meteorological"},
                                    {"label": "Buoy", "value": "Buoy"},
                                    {"label": "Fidas Palas 200S", "value": "Fidas_Palas"},
                                    {"label": "SBN Transect", "value": "SBNTransect"},
                                    {"label": "Jaywun Cruise", "value": "JWCruise"},
                                    {"label": "Underwater Probes", "value": "underwater_probe"},
                                    {"label": "Coral Reef Monitoring", "value": "coral_reef"},
                                ],
                                placeholder="Select Type",
                                value="all"
                            )
                        ], width=12),

                        dbc.Col([
                            html.Label("Status", style={"font-weight": "bold"}),
                            dcc.Dropdown(
                                id="status-dropdown",
                                options=[
                                    {"label": "All", "value": "all"},
                                    {"label": "Online", "value": "Online"},
                                    {"label": "Offline", "value": "Offline"},
                                    {"label": "Maintenance", "value": "Maintenance"},
                                    {"label": "Faulty", "value": "Faulty"},
                                    {"label": "Decommissioned", "value": "Decommissioned"}
                                ],
                                value="all",
                                placeholder="Select Status"
                            )
                        ], width=12),

                        dbc.Col([
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Start Date", style={"font-weight": "bold"}),
                                    dcc.DatePickerSingle(
                                        id="start-date-picker",
                                        placeholder="Start Date",
                                        display_format="YYYY-MM-DD",
                                        style={"width": "100%"}
                                    )
                                ], width=12)
                            ], className="mb-2"),  

                            dbc.Row([
                                dbc.Col([
                                    html.Label("End Date", style={"font-weight": "bold"}),
                                    dcc.DatePickerSingle(
                                        id="end-date-picker",
                                        placeholder="End Date",
                                        display_format="YYYY-MM-DD",
                                        style={"width": "100%"}
                                    )
                                ], width=12)
                            ])
                        ], width=12),

                    ], className="gy-3"),

                ])
            ], className="mb-2",
                style={"border": "2px solid purple", "box-shadow": "2px 2px 5px lightgrey", "height": "100%",
                       "position": "relative"})
        ], width=3, style={"padding": "10px", "height": "100%"}),

        # Map section
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div(id="map-output", style={"height": "100%"}),  # The map container
                ])
            ], style={"height": "100%", "border": "2px solid purple", "box-shadow": "2px 2px 5px lightgrey"})
        ], width=9, style={"padding": "10px", "height": "100%"}),

    ], style={"height": "calc(100vh - 100px)", "align-items": "stretch"}, className="gy-3")
], fluid=True)

@callback(
    Output("map-output", "children"),
    Input("privacy-dropdown", "value"),
    Input("type-dropdown", "value"),
    Input("status-dropdown", "value"),
    Input("start-date-picker", "date"),  # Start Date
    Input("end-date-picker", "date"),    # End Date
    State("search-input", "value"),
    Input("search-button", "n_clicks"),
    prevent_initial_call=False  # Prevents unnecessary trigger on initial page load
)
def update_filters(privacy_filter, type_filter, status_filter, start_date, end_date, search_term, n_clicks):
    """
    Update the map based on selected filters and search term.
    Only displays stations that have at least one datapoint within the date range.
    """
    try:
        # Fetch all stations
        station_data = station_map.fetch_station_data()

        # Apply missing name logic for IoTBox stations
        for s in station_data:
            if s.get("Station Name") is None and s.get("Device Type") == "IoTBox":
                s["Station Name"] = f"Station {s.get('Station Num', 'X')}"

        # Apply filters for Type and Status
        if type_filter != "all":
            station_data = [s for s in station_data if s.get("Device Type") == type_filter]
        if status_filter != "all":
            station_data = [s for s in station_data if s.get("Status") == status_filter]
        if privacy_filter != "all":
            station_data = [s for s in station_data if s.get("Privacy") == privacy_filter]
        if search_term:
            search_term = search_term.lower()
            station_data = [
                s for s in station_data if
                search_term in s.get("Station Name", "").lower() or
                str(search_term) == str(s.get("Station Num", ""))
            ]

        # Ensure valid date formats before filtering
        start_date = pd.to_datetime(start_date, errors="coerce") if start_date else None
        end_date = pd.to_datetime(end_date, errors="coerce") if end_date else None

        # Apply Date Filters: Keep stations with at least one datapoint within the range
        if start_date or end_date:
            filtered_stations = []
            for s in station_data:
                station_num = s.get("Station Num")
                if not station_num:
                    continue  # Skip if station number is missing

                # Fetch available timestamps for the station
                df = station_map.get_station_time_series(station_num, start_date, end_date)
                if df.empty:
                    continue  # Skip if no data is available

                # Convert datetime column to actual timestamps
                df["DateTime"] = pd.to_datetime(df["DateTime"])

                # Filter data within the selected date range
                mask = (df["DateTime"] >= start_date) if start_date else True
                mask &= (df["DateTime"] <= end_date) if end_date else True
                filtered_df = df.loc[mask]

                # Keep the station if at least one data point is within the range
                if not filtered_df.empty:
                    filtered_stations.append(s)

            station_data = filtered_stations

        # Handle case where no stations match the filter
        if not station_data:
            return html.Div("No stations found")

        # Create the map with the filtered stations
        map_layout = station_map.create_map(station_data)
        return map_layout 

    except Exception as e:
        print(f"An error occurred while updating the map: {e}")
        return html.Div("Error loading map")
