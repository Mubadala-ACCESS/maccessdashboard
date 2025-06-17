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

MONGO_URI = cfg.get('mongodb','uri')
DB_NAME   = cfg.get('mongodb','database')

dash.register_page(__name__, path="/", title="Station Monitoring Dashboard")

station_map = StationMap(mongo_uri=MONGO_URI, db_name=DB_NAME)

layout = dbc.Container([
    dcc.Location(id="url", refresh=False),

    dbc.Row([
        # Sidebar
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Search", style={"fontWeight":"bold"}),
                            dbc.InputGroup([
                                dcc.Input(id="search-input", type="text",
                                          placeholder="Search by station name or number",
                                          debounce=True, style={"flex":"1","minWidth":0}),
                                dbc.Button("Search", id="search-button", n_clicks=0,
                                           style={"backgroundColor":"purple","color":"white"})
                            ], style={"display":"flex","width":"100%"})
                        ], width=12),
                        dbc.Col([
                            html.Label("Privacy", style={"fontWeight":"bold"}),
                            dcc.Dropdown(id="privacy-dropdown",
                                         options=[
                                             {"label":"All","value":"all"},
                                             {"label":"Public","value":True},
                                             {"label":"Private","value":False},
                                         ], value="all")
                        ], width=12),
                        dbc.Col([
                            html.Label("Station Type", style={"fontWeight":"bold"}),
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
                                         ], value="all")
                        ], width=12),
                        dbc.Col([
                            html.Label("Status", style={"fontWeight":"bold"}),
                            dcc.Dropdown(id="status-dropdown",
                                         options=[
                                             {"label":"All","value":"all"},
                                             {"label":"Online","value":"Online"},
                                             {"label":"Offline","value":"Offline"},
                                             {"label":"Maintenance","value":"Maintenance"},
                                             {"label":"Faulty","value":"Faulty"},
                                             {"label":"Decommissioned","value":"Decommissioned"},
                                         ], value="all")
                        ], width=12),
                        dbc.Col([
                            html.Label("Start Date", style={"fontWeight":"bold"}),
                            dcc.DatePickerSingle(id="start-date-picker",
                                                 display_format="YYYY-MM-DD",
                                                 style={"width":"100%"})
                        ], width=12, className="mb-2"),
                        dbc.Col([
                            html.Label("End Date", style={"fontWeight":"bold"}),
                            dcc.DatePickerSingle(id="end-date-picker",
                                                 display_format="YYYY-MM-DD",
                                                 style={"width":"100%"})
                        ], width=12),
                    ], className="gy-3"),
                ])
            ], style={"height":"100%","border":"2px solid purple","boxShadow":"2px 2px 5px lightgrey"})
        ], width=3),

        # Map
        dbc.Col([
            dbc.Card([
                dbc.CardBody([html.Div(id="map-output", style={"height":"100%"})])
            ], style={"height":"100%","border":"2px solid purple","boxShadow":"2px 2px 5px lightgrey"})
        ], width=9),
    ], style={"height":"calc(100vh - 100px)","alignItems":"stretch"}, className="gy-3"),

    # Metadata Modal
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Station Metadata")),
        dbc.ModalBody(id="modal-body"),
        dbc.ModalFooter(dbc.Button("Close", id="close-modal", n_clicks=0, className="ms-auto"))
    ], id="metadata-modal", is_open=False, size="lg", backdrop=True),
], fluid=True)


@dash.callback(
    Output("map-output","children"),
    Input("privacy-dropdown","value"),
    Input("type-dropdown","value"),
    Input("status-dropdown","value"),
    Input("start-date-picker","date"),
    Input("end-date-picker","date"),
    State("search-input","value"),
    Input("search-button","n_clicks"),
    prevent_initial_call=False
)
def update_filters(privacy, dtype, status, start, end, search, n):
    data = station_map.fetch_station_data()
    # apply your existing filter logic here...
    if not data:
        return html.Div("No stations found")
    return station_map.create_map(data)


@dash.callback(
    Output("metadata-modal","is_open"),
    Output("modal-body","children"),
    Input({"type":"metadata-button","station":ALL,"device":ALL},"n_clicks"),
    Input("close-modal","n_clicks"),
    State("metadata-modal","is_open"),
)
def toggle_modal(meta_clicks, close_clicks, is_open):
    trig = callback_context.triggered
    if not trig:
        return is_open, no_update
    pid = trig[0]["prop_id"]
    if pid == "close-modal.n_clicks":
        return False, no_update

    raw = pid.split(".")[0]
    info = json.loads(raw)
    sid, dev = info["station"], info["device"]

    df = station_map.get_station_time_series(sid, None, None)
    if df.empty:
        e,l = "N/A","N/A"
    else:
        e = df["DateTime"].min().strftime("%Y-%m-%d %H:%M:%S")
        l = df["DateTime"].max().strftime("%Y-%m-%d %H:%M:%S")

    file_map = {"IoTBox":"iotbox.json","Meteorological":"meteostation.json","Fidas_Palas":"fidas.json"}
    fname = file_map.get(dev)
    items = []
    if fname:
        path = os.path.join(os.path.dirname(__file__),"..","metadata",fname)
        if os.path.exists(path):
            with open(path) as f:
                items = json.load(f)

    body = [html.P(f"Station ID: {sid}"),
            html.P(f"Earliest Data: {e}"),
            html.P(f"Latest Data: {l}"),
            html.Hr()]
    for it in items:
        body.append(html.Div([
            html.Strong(it["column_name"]),
            html.Span(f": {it['full_descriptor']} "),
            html.Em(f"({it['units']})"),
            html.P(it["definition"],style={"marginLeft":"1rem"})
        ],className="mb-2"))

    return True, body
