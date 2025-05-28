import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, callback, State
import dash_daq as daq
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
from graphs.iot_graphs import IoTGraphs
from graphs.meteo_graphs import meteostationGraphs
from pymongo import MongoClient
import configparser
import os

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), '../config', 'config.ini')
config.read(config_path)

# Retrieve MongoDB settings
MONGO_URI = config.get('mongodb', 'uri')
DB_NAME   = config.get('mongodb', 'database')
STATIONS_INFO = config.get('mongodb', 'stations_info_collection')


dash.register_page(__name__, path_template="/stationdata/<device_type>/<station_num>", title="Station Monitoring Dashboard")

iot_graphs = IoTGraphs()
meteo_graphs = meteostationGraphs()

def add_location_info(df, station_num):
    """
    Given a DataFrame and a station number, query the stations_info collection
    to retrieve location information (long and lat) and add them as "Longitude" and "Latitude" columns.
    """
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[STATIONS_INFO]
        # Query for the document with the given station_num (converted to int)
        doc = collection.find_one({"station_num": int(station_num)})
        client.close()
        if doc and "long" in doc and "lat" in doc:
            df["Longitude"] = doc["long"]
            df["Latitude"] = doc["lat"]
    except Exception as e:
        print(f"Error retrieving location info: {e}")
    return df

layout = dbc.Container([
    dcc.Location(id="url", refresh=False),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Label("Display Period", style={"font-weight": "bold"}),
                    dcc.Dropdown(
                        id="date-range-dropdown",
                        options=[
                            {"label": "Past 6 Hours", "value": "6H"},
                            {"label": "Past 12 Hours", "value": "12H"},
                            {"label": "Past 1 Day", "value": "1D"},
                            {"label": "Past 1 Week", "value": "1W"},
                            {"label": "Past 1 Month", "value": "1M"},
                            {"label": "Past 6 Months", "value": "6M"},
                            {"label": "Past 1 Year", "value": "1Y"},
                            {"label": "All Data", "value": "All"}
                        ],
                        value="1W"
                    ),
                    html.Hr(style={"border-top": "2px solid purple"}),
                    html.Label("Aggregation", style={"font-weight": "bold"}),
                    dcc.Dropdown(
                        id="aggregation-dropdown",
                        options=[
                            {"label": "No Aggregation", "value": "None"},
                            {"label": "Hourly", "value": "H"},
                            {"label": "Daily", "value": "D"},
                            {"label": "Weekly", "value": "W"},
                            {"label": "Monthly", "value": "M"}
                        ],
                        value="None"
                    ),
                    html.Hr(style={"border-top": "2px solid purple"}),
                    html.Label("Select Parameters", style={"font-weight": "bold"}),
                    dcc.Checklist(
                        id="parameter-checklist",
                        inline=False,
                        style={"height": "24vh", "overflow-y": "auto"}
                    ),
                    html.Hr(style={"border-top": "2px solid purple"}),
                    dbc.Button("Download Data", id="open-download-modal", color="primary", className="mt-2 d-block w-100"),
                    html.Hr(style={"border-top": "2px solid purple"}),
                    html.Div([
                        html.Label("Individual Sensor Readings", style={"font-weight": "bold"}),
                        daq.BooleanSwitch(id="split-toggle", on=False, label="OFF/ON", labelPosition="top"),
                    ], id="sensor-readings-container"),
                ])
            ], className="mb-2", style={
                "border": "3px solid purple",
                "box-shadow": "2px 2px 5px lightgrey",
                "height": "85vh",
                "overflow-y": "auto"
            })
        ], width=3, style={"padding": "10px"}),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div(id="graph-output", style={
                        "height": "80vh",
                        "overflow-y": "auto",
                        "border": "3px solid purple",
                        "padding": "10px",
                        "background-color": "white"
                    })
                ])
            ], style={
                "border": "3px solid purple",
                "box-shadow": "2px 2px 5px lightgrey",
                "height": "85vh",
                "overflow": "hidden"
            })
        ], width=9, style={"padding": "10px"})
    ], class_name="mb-3", align="center"),
    dbc.Modal([
        dbc.ModalHeader("Download Data"),
        dbc.ModalBody([
            html.Label("Select Download Type:"),
            dcc.RadioItems(
                id="download-type-radio",
                options=[
                    {"label": "All Parameters", "value": "all"},
                    {"label": "Select Parameters", "value": "select"}
                ],
                value="all",
                labelStyle={'display': 'block'}
            ),
            html.Br(),
            dbc.Collapse(
                dcc.Checklist(
                    id="download-parameter-checklist",
                    inline=False,
                    style={"height": "15vh", "overflow-y": "auto"}
                ),
                id="download-parameter-checklist-collapse",
                is_open=False
            ),
            html.Br(),
            html.Label("Select Date Range:"),
            dcc.Dropdown(
                id="download-date-range-dropdown",
                options=[
                    {"label": "Past 6 Hours", "value": "6H"},
                    {"label": "Past 12 Hours", "value": "12H"},
                    {"label": "Past 1 Day", "value": "1D"},
                    {"label": "Past 1 Week", "value": "1W"},
                    {"label": "Past 1 Month", "value": "1M"},
                    {"label": "Past 6 Months", "value": "6M"},
                    {"label": "Past 1 Year", "value": "1Y"},
                    {"label": "All Data", "value": "All"}
                ],
                value="1W"
            ),
        ]),
        dbc.ModalFooter([
            dbc.Button("Download CSV", id="confirm-download-button", color="primary", className="me-2"),
            dbc.Button("Close", id="close-download-modal", color="secondary")
        ])
    ], id="download-modal", is_open=False),
    dcc.Download(id="download-data")
], fluid=True)

@callback(
    [Output("parameter-checklist", "options"),
     Output("parameter-checklist", "value")],
    Input("url", "pathname")
)
def load_parameters(pathname):
    parts = pathname.strip("/").split("/")
    if len(parts) < 3:
        return [], []
    device_type = parts[1].lower()
    station_num = parts[2]
    if device_type in ["meteostation", "meteorological"]:
        parameters = {k: v for k, v in meteo_graphs.label_map.items() if k not in ["I3_VPOWER", "I4_VOUT"]}
        default_selection = ["S2_TA[C]"] if "S2_TA[C]" in parameters else list(parameters.keys())
    else:
        if not station_num.isdigit():
            return [], []
        parameters = iot_graphs.get_available_parameters(int(station_num))
        default_selection = [key for key in parameters.keys() if "PM2,5" in key]
        if not default_selection:
            default_selection = list(parameters.keys())
    options = [{"label": label, "value": key} for key, label in parameters.items()]
    return options, default_selection

@callback(
    Output("graph-output", "children"),
    [Input("url", "pathname"),
     Input("date-range-dropdown", "value"),
     Input("aggregation-dropdown", "value"),
     Input("parameter-checklist", "value"),
     Input("split-toggle", "on")]
)
def update_visualization(pathname, date_range, aggregation, selected_parameters, split_view):
    parts = pathname.strip("/").split("/")
    if len(parts) < 3:
        return html.Div("Invalid URL.", style={"color": "red"})
    device_type = parts[1].lower()
    station_num = parts[2]
    if device_type in ["meteostation", "meteorological"]:
        df = meteo_graphs.fetch_data(date_range)
        if not df.empty and "Timestamp" in df.columns:
            if selected_parameters:
                cols = ["Timestamp"] + [param for param in selected_parameters if param in df.columns]
                df = df[cols]
            for col in df.columns:
                if col != "Timestamp":
                    df[col] = pd.to_numeric(df[col], errors="coerce")
        if df.empty or "Timestamp" not in df.columns:
            return html.Div("No data available for the selected period.", style={"color": "gray"})
        df_aggregated = meteo_graphs.aggregate_data(df, aggregation) if aggregation != "None" else df
        figures = meteo_graphs.create_figures(df_aggregated, selected_parameters)
    else:
        if not station_num.isdigit():
            return html.Div("Invalid station selected.", style={"color": "red"})
        station_num_int = int(station_num)
        if not selected_parameters:
            return html.Div("Please select parameters to display.", style={"color": "gray"})
        df = iot_graphs.fetch_station_data(station_num_int, date_range, selected_parameters, split_view)
        if df.empty:
            return html.Div("No data available for the selected period.", style={"color": "gray"})
        df_aggregated = iot_graphs.aggregate_data(df, aggregation)
        figures = iot_graphs.create_iotbox_figures(
            df_aggregated,
            selected_parameters,
            iot_graphs.get_available_parameters(station_num_int),
            split_view
        )
    return html.Div(
        [dcc.Graph(figure=fig, style={"border": "2px solid lightgray", "padding": "5px"}) for fig in figures],
        style={"display": "flex", "flex-direction": "column", "gap": "10px"}
    )

@callback(
    [Output("download-parameter-checklist", "options"),
     Output("download-parameter-checklist", "value")],
    Input("url", "pathname")
)
def load_download_parameters(pathname):
    parts = pathname.strip("/").split("/")
    if len(parts) < 3:
        return [], []
    device_type = parts[1].lower()
    station_num = parts[2]
    if device_type in ["meteostation", "meteorological"]:
        parameters = {k: v for k, v in meteo_graphs.label_map.items() if k not in ["I3_VPOWER", "I4_VOUT"]}
        default_selection = ["S2_TA[C]"] if "S2_TA[C]" in parameters else list(parameters.keys())
    else:
        if not station_num.isdigit():
            return [], []
        parameters = iot_graphs.get_available_parameters(int(station_num))
        default_selection = [key for key in parameters.keys() if "PM2,5" in key]
        if not default_selection:
            default_selection = list(parameters.keys())
    options = [{"label": label, "value": key} for key, label in parameters.items()]
    return options, default_selection

@callback(
    Output("download-parameter-checklist-collapse", "is_open"),
    Input("download-type-radio", "value")
)
def toggle_download_checklist(download_type):
    return download_type == "select"

@callback(
    Output("download-modal", "is_open"),
    [Input("open-download-modal", "n_clicks"),
     Input("close-download-modal", "n_clicks"),
     Input("confirm-download-button", "n_clicks")],
    State("download-modal", "is_open")
)
def toggle_download_modal(open_click, close_click, confirm_click, is_open):
    ctx = dash.callback_context
    if not ctx.triggered:
        return is_open
    return not is_open

@callback(
    Output("download-data", "data"),
    Input("confirm-download-button", "n_clicks"),
    State("download-type-radio", "value"),
    State("download-parameter-checklist", "value"),
    State("download-date-range-dropdown", "value"),
    State("aggregation-dropdown", "value"),
    State("url", "pathname"),
    prevent_initial_call=True
)
def generate_csv(n_clicks, download_type, download_params, download_date_range, aggregation, pathname):
    parts = pathname.strip("/").split("/")
    if len(parts) < 3:
        return
    device_type = parts[1].lower()
    station_num = parts[2]
    if device_type in ["meteostation", "meteorological"]:
        df = meteo_graphs.fetch_data(download_date_range)
        if not df.empty and "Timestamp" in df.columns:
            if download_type == "all":
                # Include all sensor parameters (exclude Voltage fields) plus location columns.
                all_params = [p for p in meteo_graphs.label_map.keys() if p not in ["I3_VPOWER", "I4_VOUT"]]
                cols = ["Timestamp"] + all_params
                df = df[cols]
            else:
                if download_params:
                    cols = ["Timestamp"] + [param for param in download_params if param in df.columns]
                    df = df[cols]
            for col in df.columns:
                if col != "Timestamp":
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            # Always add location info from stations_info collection
            df = add_location_info(df, station_num)
        if df.empty or "Timestamp" not in df.columns:
            return dcc.send_data_frame(lambda: "", filename="meteostation.csv")
        df_aggregated = meteo_graphs.aggregate_data(df, aggregation) if aggregation != "None" else df
        filename = "meteostation.csv"
    else:
        if not station_num.isdigit():
            return
        station_num_int = int(station_num)
        if download_type == "all":
            full_params = iot_graphs.get_full_sensor_parameters(station_num_int)
            parameters = list(full_params.keys())
            df = iot_graphs.fetch_station_data(station_num_int, download_date_range, parameters, True)
        else:
            df = iot_graphs.fetch_station_data(station_num_int, download_date_range, download_params, True)
        if df.empty:
            return dcc.send_data_frame(lambda: "", filename=f"station{station_num}.csv")
        df_aggregated = iot_graphs.aggregate_data(df, aggregation)
        filename = f"station{station_num}.csv"
    return dcc.send_data_frame(df_aggregated.to_csv, filename=filename, index=False)

@callback(
    Output("sensor-readings-container", "style"),
    Input("url", "pathname")
)
def toggle_sensor_readings_container(pathname):
    parts = pathname.strip("/").split("/")
    if len(parts) < 3:
        return {}
    device_type = parts[1].lower()
    if device_type in ["meteostation", "meteorological"]:
        return {"display": "none"}
    return {}

def add_location_info(df, station_num):
    """
    Given a DataFrame and a station number, query the stations_info collection to
    retrieve location information (long and lat) and add them as "Longitude" and "Latitude" columns.
    """
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client["all_stations_db"]
        collection = db["stations_info"]
        doc = collection.find_one({"station_num": int(station_num)})
        client.close()
        if doc and "long" in doc and "lat" in doc:
            df["Longitude"] = doc["long"]
            df["Latitude"] = doc["lat"]
    except Exception as e:
        print(f"Error retrieving location info: {e}")
    return df
