# map_view.py
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback_context, no_update
from dash.dependencies import Input, Output, State, ALL
import pandas as pd
import json
import os
import configparser

from station_map import StationMap

# Load configuration
cfg = configparser.ConfigParser()
cfg_path = os.path.join(os.path.dirname(__file__), '../config/config.ini')
cfg.read(cfg_path)

MONGO_URI = cfg.get('mongodb', 'uri')
DB_NAME   = cfg.get('mongodb', 'database')

dash.register_page(__name__, path="/", title="Station Monitoring Dashboard")

station_map = StationMap(mongo_uri=MONGO_URI, db_name=DB_NAME)

layout = dbc.Container([
    dcc.Location(id="url", refresh=False),

    dbc.Row([
        # Sidebar filters
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Label("Search", style={"fontWeight": "bold"}),
                    dbc.InputGroup([
                        dcc.Input(id="search-input", type="text",
                                  placeholder="Search by station name or number",
                                  debounce=True, style={"flex":"1","minWidth":0}),
                        dbc.Button("Search", id="search-button", n_clicks=0,
                                   style={"backgroundColor":"purple","color":"white"})
                    ], style={"display":"flex","width":"100%"}),
                    html.Br(),
                    html.Label("Privacy", style={"fontWeight": "bold"}),
                    dcc.Dropdown(id="privacy-dropdown",
                                 options=[
                                     {"label":"All","value":"all"},
                                     {"label":"Public","value":True},
                                     {"label":"Private","value":False}
                                 ], value="all"),
                    html.Br(),
                    html.Label("Station Type", style={"fontWeight": "bold"}),
                    dcc.Dropdown(id="type-dropdown",
                                 options=[
                                     {"label":"All","value":"all"},
                                     {"label":"IoT Box","value":"IoTBox"},
                                     {"label":"Meteorological Station","value":"Meteorological"},
                                     {"label":"Buoy","value":"Buoy"},
                                     {"label":"Fidas Palas 200S","value":"Fidas_Palas"},
                                     {"label":"SBN Transect","value":"SBNTransect"},
                                     {"label":"Jaywun Cruise","value":"JWCruise"},
                                     {"label":"Underwater Probes","value":"underwater_probe"},
                                     {"label":"Coral Reef Monitoring","value":"coral_reef"},
                                 ], value="all"),
                    html.Br(),
                    html.Label("Status", style={"fontWeight": "bold"}),
                    dcc.Dropdown(id="status-dropdown",
                                 options=[
                                     {"label":"All","value":"all"},
                                     {"label":"Online","value":"Online"},
                                     {"label":"Offline","value":"Offline"},
                                     {"label":"Maintenance","value":"Maintenance"},
                                     {"label":"Faulty","value":"Faulty"},
                                     {"label":"Decommissioned","value":"Decommissioned"},
                                 ], value="all"),
                ])
            ], style={"height":"100%","border":"2px solid purple","boxShadow":"2px 2px 5px lightgrey"})
        ], width=3),

        # Map output
        dbc.Col([
            dbc.Card([
                dbc.CardBody([html.Div(id="map-output", style={"height":"100%"})])
            ], style={"height":"100%","border":"2px solid purple","boxShadow":"2px 2px 5px lightgrey"})
        ], width=9),
    ], style={"height":"calc(100vh - 100px)","alignItems":"stretch"}, className="gy-3"),

    # Metadata modal
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Station Metadata")),
        dbc.ModalBody(id="modal-body"),
        dbc.ModalFooter(dbc.Button("Close", id="close-modal", n_clicks=0, className="ms-auto"))
    ], id="metadata-modal", is_open=False, size="lg", backdrop=True)
], fluid=True)


@dash.callback(
    Output("map-output", "children"),
    Input("search-button", "n_clicks"),
    State("search-input", "value"),
    Input("privacy-dropdown", "value"),
    Input("type-dropdown", "value"),
    Input("status-dropdown", "value"),
    prevent_initial_call=False
)
def update_filters(n_clicks, search_term, privacy_filter, type_filter, status_filter):
    data = station_map.fetch_station_data()

    # name fallback
    for s in data:
        if not s.get("Station Name") and s["Device Type"]=="IoTBox":
            s["Station Name"] = f"Station {s['Station Num']}"

    # apply filters
    if search_term:
        term = search_term.lower()
        data = [s for s in data
                if term in s.get("Station Name","").lower()
                or term == str(s.get("Station Num",""))]
    if privacy_filter!="all":
        data = [s for s in data if s["Privacy"]==privacy_filter]
    if type_filter!="all":
        data = [s for s in data if s["Device Type"]==type_filter]
    if status_filter!="all":
        data = [s for s in data if s["Status"]==status_filter]

    if not data:
        return html.Div("No stations found")
    return station_map.create_map(data)


@dash.callback(
    Output("metadata-modal", "is_open"),
    Output("modal-body", "children"),
    Input({"type":"metadata-button","station":ALL,"device":ALL}, "n_clicks"),
    Input("close-modal", "n_clicks"),
    State("metadata-modal", "is_open")
)
def toggle_metadata_modal(meta_clicks, close_clicks, is_open):
    triggered = callback_context.triggered
    if not triggered:
        return is_open, no_update

    prop = triggered[0]["prop_id"]
    if prop=="close-modal.n_clicks":
        return False, no_update

    raw = prop.split(".")[0]
    info = json.loads(raw)
    sid, dev = info["station"], info["device"]

    df = station_map.get_station_time_series(sid, None, None)
    if df.empty:
        earliest = latest = "N/A"
    else:
        earliest = df["DateTime"].min().strftime("%Y-%m-%d %H:%M:%S")
        latest   = df["DateTime"].max().strftime("%Y-%m-%d %H:%M:%S")

    metadata_map = {
        "IoTBox": ["iotbox_metadata.json"],
        "Meteorological": ["meteostation_metadata.json"],
        "Buoy": ["buoy_metadata.json"],
        "Fidas_Palas": ["fidas_metadata.json"],
        "SBNTransect": ["exo_metadata.json", "idronaut_metadata.json"],
        "JWCruise": ["exo_metadata.json", "idronaut_metadata.json", "ead_ctd_metadata.json"],
        "underwater_probe": ["exo_metadata.json"],
        "coral_reef": ["coral_reef_metadata.json"]
    }

    body = [
        html.P(f"Station ID: {sid}"),
        html.P(f"Earliest Data: {earliest}"),
        html.P(f"Latest Data: {latest}"),
        html.Hr()
    ]

    files = metadata_map.get(dev, [])
    meta_dir = os.path.join(os.path.dirname(__file__), "..", "metadata")
    for fname in files:
        path = os.path.join(meta_dir, fname)
        if not os.path.exists(path):
            continue
        with open(path, 'r',encoding='utf-8') as f:
            items = json.load(f)
        title = fname.replace("_metadata.json","").replace("_"," ").title()
        body.append(html.H5(title))
        table = html.Table([
            html.Thead(html.Tr([html.Th("Column"), html.Th("Descriptor"), html.Th("Units"), html.Th("Definition")])),
            html.Tbody([
                html.Tr([
                    html.Td(x["column_name"]),
                    html.Td(x["full_descriptor"]),
                    html.Td(x["units"]),
                    html.Td(x["definition"])
                ]) for x in items
            ])
        ], style={"width":"100%","marginBottom":"1rem"})
        body.append(table)

    return True, body
