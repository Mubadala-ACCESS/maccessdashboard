# map_view.py

import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback_context, no_update
from dash.dependencies import Input, Output, State, ALL

import json
import os
import configparser

from pymongo import MongoClient
from station_map import StationMap
import pandas as pd

# ------------------------------------------------------------------------------
# Load configuration
# ------------------------------------------------------------------------------
cfg = configparser.ConfigParser()
cfg_path = os.path.join(os.path.dirname(__file__), '../config/config.ini')
cfg.read(cfg_path)

MONGO_URI          = cfg.get('mongodb', 'uri')
DB_NAME            = cfg.get('mongodb', 'database')
BUOY_COLL          = cfg.get('mongodb', 'buoy_01_collection')
METEO_COLL         = cfg.get('mongodb', 'f1_meteo_collection')

# ------------------------------------------------------------------------------
# Human-readable display names for metadata files
# ------------------------------------------------------------------------------
DISPLAY_NAMES = {
    "iotbox_metadata.json":        "IoT Box",
    "meteostation_metadata.json":  "Meteorological Station",
    "buoy_metadata.json":          "Buoy",
    "fidas_metadata.json":         "Fidas Palas 200S",
    "exo_metadata.json":           "EXO Sonde 2",
    "idronaut_metadata.json":      "Idronaut",
    "ead_ctd_metadata.json":       "EAD CTD",
    "coral_reef_metadata.json":    "Coral Reef Monitoring"
}

# ------------------------------------------------------------------------------
# Register page & initialize StationMap
# ------------------------------------------------------------------------------
dash.register_page(__name__, path="/", title="Station Monitoring Dashboard")
station_map = StationMap(mongo_uri=MONGO_URI, db_name=DB_NAME)

# ------------------------------------------------------------------------------
# Layout
# ------------------------------------------------------------------------------
layout = dbc.Container(
    [
        dcc.Location(id="url", refresh=False),

        dbc.Row(
            [
                # Sidebar filters
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.Label("Search", style={"fontWeight": "bold"}),
                                dbc.InputGroup(
                                    [
                                        dcc.Input(
                                            id="search-input",
                                            type="text",
                                            placeholder="Search by station name or number",
                                            debounce=True,
                                            style={"flex": "1", "minWidth": 0}
                                        ),
                                        dbc.Button(
                                            "Search",
                                            id="search-button",
                                            n_clicks=0,
                                            style={"backgroundColor": "purple", "color": "white"}
                                        ),
                                    ],
                                    style={"display": "flex", "width": "100%"},
                                ),
                                html.Br(),
                                html.Label("Privacy", style={"fontWeight": "bold"}),
                                dcc.Dropdown(
                                    id="privacy-dropdown",
                                    options=[
                                        {"label": "All", "value": "all"},
                                        {"label": "Public", "value": True},
                                        {"label": "Private", "value": False},
                                    ],
                                    value="all",
                                ),
                                html.Br(),
                                html.Label("Station Type", style={"fontWeight": "bold"}),
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
                                    value="all",
                                ),
                                html.Br(),
                                html.Label("Status", style={"fontWeight": "bold"}),
                                dcc.Dropdown(
                                    id="status-dropdown",
                                    options=[
                                        {"label": "All", "value": "all"},
                                        {"label": "Online", "value": "Online"},
                                        {"label": "Offline", "value": "Offline"},
                                        {"label": "Maintenance", "value": "Maintenance"},
                                        {"label": "Faulty", "value": "Faulty"},
                                        {"label": "Decommissioned", "value": "Decommissioned"},
                                    ],
                                    value="all",
                                ),
                            ]
                        ),
                        style={"height": "100%", "border": "2px solid purple", "boxShadow": "2px 2px 5px lightgrey"},
                    ),
                    width=3,
                ),

                # Map output
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            html.Div(id="map-output", style={"height": "100%"})
                        ),
                        style={"height": "100%", "border": "2px solid purple", "boxShadow": "2px 2px 5px lightgrey"},
                    ),
                    width=9,
                ),
            ],
            style={"height": "calc(100vh - 100px)", "alignItems": "stretch"},
            className="gy-3",
        ),

        # Metadata modal (wider, scrollable, tabbed)
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Station Metadata")),
                dbc.ModalBody(id="modal-body", style={"maxHeight": "60vh", "overflowY": "auto"}),
                dbc.ModalFooter(
                    dbc.Button("Close", id="close-modal", n_clicks=0, className="ms-auto")
                ),
            ],
            id="metadata-modal",
            is_open=False,
            size="xl",
            backdrop=True,
            scrollable=True,
        ),
    ],
    fluid=True,
)

# ------------------------------------------------------------------------------
# Callbacks
# ------------------------------------------------------------------------------
@dash.callback(
    Output("map-output", "children"),
    Input("search-button", "n_clicks"),
    State("search-input", "value"),
    Input("privacy-dropdown", "value"),
    Input("type-dropdown", "value"),
    Input("status-dropdown", "value"),
    prevent_initial_call=False,
)
def update_filters(n_clicks, search_term, privacy_filter, type_filter, status_filter):
    data = station_map.fetch_station_data()

    # Name fallback for IoTBox
    for s in data:
        if not s.get("Station Name") and s["Device Type"] == "IoTBox":
            s["Station Name"] = f"Station {s['Station Num']}"

    # Apply search filter
    if search_term:
        term = search_term.lower()
        data = [
            s for s in data
            if term in s.get("Station Name", "").lower()
            or term == str(s.get("Station Num", ""))
        ]

    # Apply privacy filter
    if privacy_filter != "all":
        data = [s for s in data if s["Privacy"] == privacy_filter]

    # Apply type filter
    if type_filter != "all":
        data = [s for s in data if s["Device Type"] == type_filter]

    # Apply status filter
    if status_filter != "all":
        data = [s for s in data if s["Status"] == status_filter]

    if not data:
        return html.Div("No stations found")

    return station_map.create_map(data)


@dash.callback(
    Output("metadata-modal", "is_open"),
    Output("modal-body", "children"),
    Input({"type": "metadata-button", "station": ALL, "device": ALL}, "n_clicks"),
    Input("close-modal", "n_clicks"),
    State("metadata-modal", "is_open"),
)
def toggle_metadata_modal(meta_clicks, close_clicks, is_open):
    # Prevent auto-open on page load
    if (not meta_clicks or sum(meta_clicks) == 0) and close_clicks == 0:
        return False, no_update

    trigger = callback_context.triggered[0]["prop_id"]
    if trigger == "close-modal.n_clicks":
        return False, no_update

    # Parse which metadata button was clicked
    raw = trigger.split(".")[0]
    info = json.loads(raw)
    sid, dev = info["station"], info["device"]

    # Fetch station list & lookup by Station ID
    all_stations = station_map.fetch_station_data()
    entry = next((s for s in all_stations if s["Station ID"] == sid), None)
    station_name = entry["Station Name"] if entry else "Unknown"
    station_num  = entry["Station Num"]  if entry else None

    # Determine earliest & latest timestamps
    special = {"SBNTransect", "JWCruise", "underwater_probe", "coral_reef"}
    if dev not in special:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]

        # select correct collection
        if dev == "IoTBox":
            coll_name = f"station{station_num}"
        elif dev == "Buoy":
            coll_name = BUOY_COLL
        elif dev == "Meteorological":
            coll_name = METEO_COLL
        elif dev == "Fidas_Palas":
            coll_name = "fidas_nyuad"
        else:
            coll_name = None

        # pick correct time field
        time_field = "Timestamp" if dev == "Meteorological" else "datetime"

        if coll_name and coll_name in db.list_collection_names():
            coll = db[coll_name]
            # only match docs that have the field
            first = coll.find_one({time_field: {"$exists": True}}, sort=[(time_field, 1)])
            last  = coll.find_one({time_field: {"$exists": True}}, sort=[(time_field, -1)])

            def fmt(doc):
                if not doc or time_field not in doc:
                    return "N/A"
                return pd.to_datetime(doc[time_field]).strftime("%Y-%m-%d %H:%M:%S")

            earliest = fmt(first)
            latest   = fmt(last)
        else:
            earliest = latest = "N/A"

    else:
        df = station_map.get_station_time_series(sid, None, None)
        if df.empty:
            earliest = latest = "N/A"
        else:
            earliest = df["DateTime"].min().strftime("%Y-%m-%d %H:%M:%S")
            latest   = df["DateTime"].max().strftime("%Y-%m-%d %H:%M:%S")

    # Build summary section
    summary_section = html.Div(
        [
            html.H5("Summary"),
            html.P(f"Station Name: {station_name}"),
            html.P(f"Earliest Data: {earliest}"),
            html.P(f"Latest Data: {latest}"),
            html.Hr(),
        ]
    )

    # Load appropriate metadata JSON files
    metadata_map = {
        "IoTBox":         ["iotbox_metadata.json"],
        "Meteorological": ["meteostation_metadata.json"],
        "Buoy":           ["buoy_metadata.json"],
        "Fidas_Palas":    ["fidas_metadata.json"],
        "SBNTransect":    ["exo_metadata.json", "idronaut_metadata.json"],
        "JWCruise":       ["exo_metadata.json", "idronaut_metadata.json", "ead_ctd_metadata.json"],
        "underwater_probe": ["exo_metadata.json"],
        "coral_reef":     ["coral_reef_metadata.json"]
    }
    meta_dir = os.path.join(os.path.dirname(__file__), "..", "metadata")

    tabs = []
    for fname in metadata_map.get(dev, []):
        path = os.path.join(meta_dir, fname)
        if not os.path.exists(path):
            continue

        # safely load JSON
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = f.read().strip()
                if not raw:
                    continue
                items = json.loads(raw)
        except (json.JSONDecodeError, OSError):
            continue

        table = html.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Column"),
                    html.Th("Descriptor"),
                    html.Th("Units"),
                    html.Th("Definition")
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(x["column_name"]),
                        html.Td(x["full_descriptor"]),
                        html.Td(x["units"]),
                        html.Td(x["definition"])
                    ]) for x in items
                ])
            ],
            style={"width": "100%", "marginBottom": "1rem"}
        )

        label = DISPLAY_NAMES.get(
            fname,
            fname.replace("_metadata.json", "").replace("_", " ").title()
        )

        tabs.append(dbc.Tab(label=label, tab_id=f"tab-{fname}", children=[table]))

    instruments_heading = html.H5("Instrument(s)", style={"marginTop": "1rem", "marginBottom": "0.5rem"})
    tabs_component = dbc.Tabs(
        tabs,
        id="metadata-tabs",
        active_tab=(tabs[0].tab_id if tabs else None)
    )

    modal_children = [
        summary_section,
        instruments_heading,
        tabs_component
    ]

    return True, modal_children
