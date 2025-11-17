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
    html.Div(id="station-name-header", style={"marginBottom": "0.5rem", "marginTop": "0"}),
    html.Div(id="station-status-alert", style={"marginBottom": "0.5rem"}),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Label("Display Period", className="maccess-panel-title mb-2"),
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
                        value="1W",
                        className="maccess-dropdown",
                    ),
                    html.Hr(className="maccess-divider"),
                    html.Label("Aggregation", className="fw-semibold text-uppercase text-muted small"),
                    dcc.Dropdown(
                        id="aggregation-dropdown",
                        options=[
                            {"label": "No Aggregation", "value": "None"},
                            {"label": "Hourly", "value": "H"},
                            {"label": "Daily", "value": "D"},
                            {"label": "Weekly", "value": "W"},
                            {"label": "Monthly", "value": "M"}
                        ],
                        value="None",
                        className="maccess-dropdown",
                    ),
                    html.Hr(className="maccess-divider"),
                    html.Label("Select Parameters", className="fw-semibold text-uppercase text-muted small"),
                    dcc.Checklist(
                        id="parameter-checklist",
                        inline=False,
                        className="maccess-scrollable list-unstyled",
                        style={"maxHeight": "24vh"}
                    ),
                    html.Hr(className="maccess-divider"),
                    dbc.Button(
                        "Download Data",
                        id="open-download-modal",
                        color="primary",
                        className="mt-2 d-block w-100 rounded-md",
                    ),
                    html.Hr(className="maccess-divider"),
                    html.Div([
                        html.Label("Individual Sensor Readings", className="fw-semibold text-uppercase text-muted small"),
                        daq.BooleanSwitch(id="split-toggle", on=False, label="OFF", labelPosition="top"),
                    ], id="sensor-readings-container"),
                ], style={"height": "100%", "overflowY": "auto", "position": "relative"}, className="dashboard-sidebar-section")
            ], className="maccess-card maccess-scrollable dashboard-sidebar-scroll", style={
                "height": "100%",
            })
        ], width=3, className="dashboard-sidebar"),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Loading(
                        children=html.Div(
                            id="graph-output",
                            className="maccess-scrollable dashboard-graph-stack",
                            style={
                                "height": "100%",
                                "padding": "0",
                                "backgroundColor": "rgba(255, 255, 255, 0.92)",
                                "overflowY": "auto",
                            },
                        ),
                        type="default",
                        className="w-100 h-100"
                    )
                ], style={"padding": "0"})
            ], className="maccess-card", style={
                "height": "100%",
                "overflow": "hidden",
            })
        ], width=9, className="dashboard-main")
    ], class_name="dashboard-layout-row", align="stretch", justify="start"),
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
], fluid=True, className="dashboard-shell", style={"marginTop": "-50px"})

@callback(
    Output("station-name-header", "children"),
    Input("url", "pathname")
)
def update_station_name(pathname):
    """Display the station name at the top of the page"""
    if not pathname:
        return ""
    
    parts = pathname.strip("/").split("/")
    if len(parts) < 3:
        return ""
    
    device_type = parts[1].lower()
    station_num = parts[2]
    
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[STATIONS_INFO]
        
        if device_type in ["meteostation", "meteorological"]:
            doc = collection.find_one({"type": "Meteorological"})
            station_name = doc.get("name", "Meteorological Station") if doc else "Meteorological Station"
            station_status = doc.get("status", "Unknown") if doc else "Unknown"
        else:
            if station_num.isdigit():
                doc = collection.find_one({"station_num": int(station_num)})
                station_name = doc.get("name", f"Station {station_num}") if doc else f"Station {station_num}"
                station_status = doc.get("status", "Unknown") if doc else "Unknown"
            else:
                station_name = "Unknown Station"
                station_status = "Unknown"
        
        client.close()
        
        # Create status badge if station is under maintenance or other non-operational status
        status_badge = None
        if station_status in ["Maintenance", "Faulty", "Offline", "Decommissioned"]:
            status_colors = {
                "Maintenance": "#f7a046",  # warning orange
                "Faulty": "#e65252",       # danger red
                "Offline": "#8f90a0",      # gray
                "Decommissioned": "#8f90a0"  # gray
            }
            status_badge = html.Span(
                station_status.upper(),
                style={
                    "backgroundColor": status_colors.get(station_status, "#f7a046"),
                    "color": "white",
                    "padding": "0.35rem 0.75rem",
                    "borderRadius": "4px",
                    "fontSize": "0.85rem",
                    "fontWeight": "700",
                    "letterSpacing": "0.05em",
                    "marginLeft": "1rem",
                    "verticalAlign": "middle"
                }
            )
        
        return html.Div([
            html.H3(
                [station_name, status_badge] if status_badge else station_name,
                className="maccess-panel-title",
                style={
                    "fontSize": "1.75rem",
                    "marginTop": "0",
                    "marginBottom": "0.25rem",
                    "color": "var(--color-nyu-violet-dark)",
                    "fontFamily": "var(--font-serif)"
                }
            )
        ])
    except Exception as e:
        print(f"Error fetching station name: {e}")
        return ""


@callback(
    Output("station-status-alert", "children"),
    Input("url", "pathname")
)
def update_station_status_alert(pathname):
    """Display a prominent alert banner if station has no recent data or has status issues"""
    if not pathname:
        return None
    
    parts = pathname.strip("/").split("/")
    if len(parts) < 3:
        return None
    
    device_type = parts[1].lower()
    station_num = parts[2]
    
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        stations_collection = db[STATIONS_INFO]
        
        # Get station info and manual status
        if device_type in ["meteostation", "meteorological"]:
            doc = stations_collection.find_one({"type": "Meteorological"})
            data_collection = db[config.get('mongodb', 'f1_meteo_collection')]
            time_field = "Timestamp"
        else:
            if station_num.isdigit():
                doc = stations_collection.find_one({"station_num": int(station_num)})
                data_collection = db[f"station{station_num}"]
                time_field = "datetime"
            else:
                client.close()
                return None
        
        manual_status = doc.get("status", "Unknown") if doc else "Unknown"
        
        # Check for recent data (within last 24 hours)
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        twenty_four_hours_ago = now - timedelta(hours=24)
        
        # Query for the most recent data point
        try:
            recent_data = data_collection.find_one(
                {time_field: {"$gte": twenty_four_hours_ago}},
                sort=[(time_field, -1)]
            )
            has_recent_data = recent_data is not None
        except Exception:
            has_recent_data = False
        
        client.close()
        
        # Determine status: prioritize lack of recent data, then manual status
        if not has_recent_data:
            # No data in last 24 hours - station is likely offline or faulty
            if manual_status == "Maintenance":
                return dbc.Alert([
                    html.I(className="fas fa-tools me-2"),
                    html.Strong("Station Under Maintenance:"),
                    html.Span("This station is currently undergoing maintenance. No data received in the last 24 hours.", className="ms-2")
                ], color="warning", className="mb-3")
            elif manual_status == "Decommissioned":
                return dbc.Alert([
                    html.I(className="fas fa-archive me-2"),
                    html.Strong("Station Decommissioned:"),
                    html.Span(" This station has been decommissioned. Only historical data is available.", className="ms-2")
                ], color="secondary", className="mb-3")
            else:
                # No manual status, but no recent data
                return dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    html.Strong("No Recent Data:"),
                    html.Span(" This station has not transmitted data in the last 24 hours. It may be offline or experiencing technical issues.", className="ms-2")
                ], color="warning", className="mb-3")
        
        # Has recent data, check manual status only
        if manual_status == "Maintenance":
            return dbc.Alert([
                html.I(className="fas fa-tools me-2"),
                html.Strong("Station Under Maintenance:"),
                html.Span(" — This station is currently undergoing maintenance. Data may be limited.", className="ms-2")
            ], color="warning", className="mb-3")
        elif manual_status == "Faulty":
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                html.Strong("Station Reporting Issues:"),
                html.Span("This station is experiencing technical issues. Data may be unreliable.", className="ms-2")
            ], color="danger", className="mb-3")
        
        # Station is operational with recent data
        return None
        
    except Exception as e:
        print(f"Error checking station status: {e}")
        return None


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
    
    # Reverse parameters so newest selections appear on top
    if selected_parameters:
        selected_parameters = list(reversed(selected_parameters))
    
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
        [
            dbc.Card(
                dbc.CardBody(
                    dcc.Graph(figure=fig, config={"displaylogo": False})
                , style={"padding": "0"}),
                className="maccess-card dashboard-graph-card",
                style={"scrollSnapAlign": "start", "margin": "0", "border": "none"},
            )
            for fig in figures
        ],
        style={
            "display": "flex",
            "flexDirection": "column",
            "gap": "0",
            "overflow": "visible",
        },
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


@callback(Output("split-toggle", "label"), Input("split-toggle", "on"))
def _update_split_label(is_on):
    return "ON" if is_on else "OFF"
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

