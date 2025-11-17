import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, callback_context
from graphs.buoy_graphs import BuoyGraphs
from pymongo import MongoClient
import configparser
import os

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), '../config', 'config.ini')
config.read(config_path)

MONGO_URI = config.get('mongodb', 'uri')
DB_NAME = config.get('mongodb', 'database')
STATIONS_INFO = config.get('mongodb', 'stations_info_collection')

# Register Dash page
dash.register_page(
    __name__,
    path_template="/stationdata/Buoy/<station_num>",
    title="Station Monitoring Dashboard"
)

buoy = BuoyGraphs()

DATE_RANGE_OPTIONS = [
    {"label": "Past 6 Hours",  "value": "6H"},
    {"label": "Past 12 Hours", "value": "12H"},
    {"label": "Past 1 Day",    "value": "1D"},
    {"label": "Past 1 Week",   "value": "1W"},
    {"label": "Past 1 Month",  "value": "1M"},
    {"label": "Past 3 Months", "value": "3M"},
    {"label": "Past 6 Months", "value": "6M"},
    {"label": "Past 1 Year",   "value": "1Y"},
]

layout = dbc.Container([
    dcc.Location(id="url", refresh=False),
    html.Div(id="buoy-station-name-header", style={"marginBottom": "0.5rem", "marginTop": "0"}),
    html.Div(id="buoy-status-alert", style={"marginBottom": "0.5rem"}),

    dbc.Row([
        # Controls Column
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.Div(id="buoy-controls-timeseries", children=[
                    html.Label("Display Period", className="maccess-panel-title mb-2"),
                    dcc.Dropdown(
                        id="buoy-date-range",
                        options=DATE_RANGE_OPTIONS,
                        value="1D",
                        className="maccess-dropdown",
                    ),
                    html.Hr(className="maccess-divider"),
                    html.Label("Select Parameters", className="fw-semibold text-uppercase text-muted small mb-2"),
                    dcc.Checklist(
                        id="buoy-param-checklist",
                        className="maccess-scrollable list-unstyled",
                        options=[{"label": buoy.param_labels[p], "value": p} for p in buoy.scalar_params],
                        value=buoy.scalar_params,
                    ),
                ]),
                html.Div(id="buoy-controls-profile", style={"display": "none"}, children=[
                    html.Label("Display Period", className="maccess-panel-title mb-2"),
                    dcc.Dropdown(
                        id="buoy-profile-date-range",
                        options=DATE_RANGE_OPTIONS,
                        value="1D",
                        className="maccess-dropdown",
                    ),
                    html.Hr(className="maccess-divider"),
                    html.Label("Select Parameters", className="fw-semibold text-uppercase text-muted small mb-2"),
                    dcc.Checklist(
                        id="buoy-profile-param-checklist",
                        className="maccess-scrollable list-unstyled",
                        options=[{"label": buoy.param_labels[p], "value": p} for p in buoy.profile_params],
                        value=buoy.profile_params,
                    ),
                ]),
                html.Hr(className="maccess-divider"),
                dbc.Button(
                    "Download Data",
                    id="buoy-download-open",
                    color="primary",
                    className="w-100 rounded-md",
                ),
            ])
            ], className="mb-2 maccess-card maccess-scrollable",
            style={
                "height": "85vh",
            }), width=3, style={"padding": "5px"}),

        # Graphs Column
        dbc.Col(dbc.Card([
            dbc.CardBody([
                dcc.Tabs(id="buoy-tabs", value="tab-timeseries", children=[
                    dcc.Tab(label="Atmospheric Parameters", value="tab-timeseries"),
                    dcc.Tab(label="Vertical Profiles",       value="tab-profile"),
                ]),
                dcc.Loading(
                    children=html.Div(
                        id="buoy-tab-content",
                        className="maccess-scrollable",
                        style={
                            "height": "92vh",
                            "padding": "0",
                            "scrollSnapType": "y mandatory"
                        }
                    ),
                    type="default",
                    className="w-100 h-100"
                )
            ], style={"padding": "0"})
        ], className="mb-2 maccess-card",
            style={
                "height": "92vh",
                "overflow": "hidden"
            }), width=9, style={"padding": "5px"}),
    ], class_name="mb-3", align="center"),

    # Download Modal
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Download Buoy Data")),
        dbc.ModalBody([
            html.Label("Select Date Range:", style={"font-weight": "bold"}),
            dcc.Dropdown(
                id="buoy-download-range",
                options=DATE_RANGE_OPTIONS,
                value="1D"
            ),
            html.Br(),
            html.Label("Select Parameters:", style={"font-weight": "bold"}),
            dcc.Checklist(
                id="buoy-download-params",
                style={"height": "20vh", "overflow-y": "auto"},
                options=[{"label": buoy.param_labels[p], "value": p} for p in buoy.scalar_params],
                value=buoy.scalar_params
            )
        ]),
        dbc.ModalFooter([
            dbc.Button("Download CSV", id="buoy-download-confirm", className="me-2"),
            dbc.Button("Close",            id="buoy-download-close")
        ])
    ], id="buoy-download-modal", is_open=False),
    dcc.Download(id="buoy-download-data")
], fluid=True, style={"marginTop": "-50px"})


# Callbacks

@dash.callback(
    Output("buoy-station-name-header", "children"),
    Input("url", "pathname")
)
def update_buoy_station_name(pathname):
    """Display the station name at the top of the page"""
    if not pathname:
        return ""
    
    parts = pathname.strip("/").split("/")
    if len(parts) < 3:
        return ""
    
    station_num = parts[2]
    
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[STATIONS_INFO]
        
        doc = collection.find_one({"type": "Buoy"})
        station_name = doc.get("name", "Buoy Station") if doc else "Buoy Station"
        station_status = doc.get("status", "Unknown") if doc else "Unknown"
        
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


@dash.callback(
    Output("buoy-status-alert", "children"),
    Input("url", "pathname")
)
def update_buoy_status_alert(pathname):
    """Display a prominent alert banner if station has no recent data or has status issues"""
    if not pathname:
        return None
    
    try:
        from datetime import datetime, timedelta, timezone
        
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        stations_collection = db[STATIONS_INFO]
        
        # Get station info and manual status
        doc = stations_collection.find_one({"type": "Buoy"})
        manual_status = doc.get("status", "Unknown") if doc else "Unknown"
        
        # Check for recent data (within last 24 hours)
        buoy_collection = db[config.get('mongodb', 'buoy_01_collection')]
        now = datetime.now(timezone.utc)
        twenty_four_hours_ago = now - timedelta(hours=24)
        
        try:
            recent_data = buoy_collection.find_one(
                {"datetime": {"$gte": twenty_four_hours_ago}},
                sort=[("datetime", -1)]
            )
            has_recent_data = recent_data is not None
        except Exception:
            has_recent_data = False
        
        client.close()
        
        # Determine status: prioritize lack of recent data, then manual status
        if not has_recent_data:
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
                    html.Span("This station has been decommissioned. Only historical data is available.", className="ms-2")
                ], color="secondary", className="mb-3")
            else:
                return dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    html.Strong("No Recent Data"),
                    html.Span("This station has not transmitted data in the last 24 hours. It may be offline or experiencing technical issues.", className="ms-2")
                ], color="warning", className="mb-3")
        
        # Has recent data, check manual status only
        if manual_status == "Maintenance":
            return dbc.Alert([
                html.I(className="fas fa-tools me-2"),
                html.Strong("Station Under Maintenance:"),
                html.Span("This station is currently undergoing maintenance. Data may be limited.", className="ms-2")
            ], color="warning", className="mb-3")
        elif manual_status == "Faulty":
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                html.Strong("Station Reporting Issues:"),
                html.Span("This station is experiencing technical issues. Data may be unreliable.", className="ms-2")
            ], color="danger", className="mb-3")
        
        return None
        
    except Exception as e:
        print(f"Error checking station status: {e}")
        return None


@dash.callback(
    [Output("buoy-controls-timeseries", "style"), Output("buoy-controls-profile", "style")],
    Input("buoy-tabs", "value")
)
def _toggle_controls(tab):
    if tab == "tab-timeseries":
        return {"display": "block"}, {"display": "none"}
    return {"display": "none"}, {"display": "block"}


@dash.callback(
    Output("buoy-tab-content", "children"),
    [
        Input("buoy-tabs", "value"),
        Input("buoy-date-range", "value"),
        Input("buoy-param-checklist", "value"),
        Input("buoy-profile-date-range", "value"),
        Input("buoy-profile-param-checklist", "value")
    ]
)
def _render_tab(tab, dr_ts, params_ts, dr_pf, params_pf):
    if tab == "tab-timeseries":
        # Reverse parameters so newest selections appear on top
        if params_ts:
            params_ts = list(reversed(params_ts))
        df = buoy.fetch_time_series(dr_ts, params_ts, agg="None")
        if df.empty:
            return html.Div("No data available.", style={"color": "gray"})
        figs = buoy.create_time_series_figures(df, params_ts)
        return html.Div([
            dcc.Graph(
                figure=fig,
                style={"border": "none", "padding": "0", "height": "92vh", "scrollSnapAlign": "start"}
            )
            for fig in figs
        ], style={"display": "flex", "flexDirection": "column", "gap": "0"})

    # Vertical Profiles: unpack fetch_profiles() directly
    # Reverse parameters so newest selections appear on top
    if params_pf:
        params_pf = list(reversed(params_pf))
    times, docs = buoy.fetch_profiles(dr_pf)
    if not times or not docs:
        return html.Div("No profile data.", style={"color": "gray"})

    graphs = []
    for p in params_pf:
        fig = buoy.create_profile_figure(times, docs, p)
        graphs.append(dcc.Graph(
            figure=fig,
            style={"border": "none", "padding": "0", "height": "92vh", "scrollSnapAlign": "start"}
        ))
    return html.Div(graphs, style={"display": "flex", "flexDirection": "column", "gap": "0"})


@dash.callback(
    Output("buoy-download-modal", "is_open"),
    [Input("buoy-download-open", "n_clicks"), Input("buoy-download-close", "n_clicks")],
    State("buoy-download-modal", "is_open")
)
def _toggle_modal(o, c, is_open):
    ctx = callback_context.triggered
    return (not is_open) if ctx else is_open


@dash.callback(
    Output("buoy-download-data", "data"),
    Input("buoy-download-confirm", "n_clicks"),
    State("buoy-download-range", "value"),
    State("buoy-download-params", "value"),
    prevent_initial_call=True
)
def _dl_csv(n, dr, params):
    df = buoy.fetch_time_series(dr, params, "None")
    return dcc.send_data_frame(df.to_csv, "buoy01_data.csv", index=False)
