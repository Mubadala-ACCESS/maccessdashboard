import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, callback_context
from graphs.buoy_graphs import BuoyGraphs
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
import configparser
import os
import pandas as pd

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), '../config', 'config.ini')
config.read(config_path)

# Retrieve MongoDB settings
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
    
    # Station Status Alert
    html.Div(id="buoy-station-status-alert", style={"marginBottom": "0.5rem"}),

    dbc.Row([
        # Controls Column
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.Div(id="buoy-controls-timeseries", children=[
                    html.Label("Display Period", style={"font-weight": "bold"}),
                    dcc.Dropdown(
                        id="buoy-date-range",
                        options=DATE_RANGE_OPTIONS,
                        value="1D"
                    ),
                    html.Hr(style={"border-top": "2px solid purple"}),
                    html.Label("Select Parameters", style={"font-weight": "bold"}),
                    dcc.Checklist(
                        id="buoy-param-checklist",
                        style={"height": "20vh", "overflow-y": "auto"},
                        options=[{"label": buoy.param_labels[p], "value": p} for p in buoy.scalar_params],
                        value=buoy.scalar_params
                    ),
                ]),
                html.Div(id="buoy-controls-profile", style={"display": "none"}, children=[
                    html.Label("Display Period", style={"font-weight": "bold"}),
                    dcc.Dropdown(
                        id="buoy-profile-date-range",
                        options=DATE_RANGE_OPTIONS,
                        value="1D"
                    ),
                    html.Hr(style={"border-top": "2px solid purple"}),
                    html.Label("Select Parameters", style={"font-weight": "bold"}),
                    dcc.Checklist(
                        id="buoy-profile-param-checklist",
                        style={"height": "20vh", "overflow-y": "auto"},
                        options=[{"label": buoy.param_labels[p], "value": p} for p in buoy.profile_params],
                        value=buoy.profile_params
                    ),
                ]),
                html.Hr(style={"border-top": "2px solid purple"}),
                dbc.Button("Download Data", id="buoy-download-open", color="primary", className="w-100"),
            ])
        ], className="mb-2",
            style={
                "border": "3px solid purple",
                "box-shadow": "2px 2px 5px lightgrey",
                "height": "85vh",
                "overflow-y": "auto"
            }), width=3, style={"padding": "10px"}),

        # Graphs Column
        dbc.Col(dbc.Card([
            dbc.CardBody([
                dcc.Tabs(id="buoy-tabs", value="tab-timeseries", children=[
                    dcc.Tab(label="Atmospheric Parameters", value="tab-timeseries"),
                    dcc.Tab(label="Vertical Profiles",       value="tab-profile"),
                ]),
                html.Div(id="buoy-tab-content", style={
                    "height": "75vh", "overflow-y": "auto", "padding": "10px"
                })
            ])
        ], className="mb-2",
            style={
                "border": "3px solid purple",
                "box-shadow": "2px 2px 5px lightgrey",
                "height": "85vh",
                "overflow": "hidden"
            }), width=9, style={"padding": "10px"}),
    ], class_name="mb-3", align="center"),

    # Download Modal
    dbc.Modal([
        dbc.ModalHeader("Download Buoy Data"),
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
    dcc.Download(id="buoy-download-data"),
    
    # Maintenance / No Data Modal
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Station Status")),
            dbc.ModalBody(
                [
                    html.Div(
                        [
                            html.I(className="fas fa-tools fa-3x mb-3", style={"color": "#f7a046"}),
                            html.H4("Device Under Maintenance", className="mb-3"),
                            html.P(
                                id="buoy-maintenance-modal-text",
                                children="This station's CTD is currently under maintenance."
                            ),
                            html.P(
                                "You can still view historical data by selecting a different time range.",
                                className="text-muted small",
                            ),
                        ],
                        className="text-center",
                    )
                ]
            ),
            dbc.ModalFooter(
                dbc.Button(
                    "View Historical Data", id="buoy-maintenance-modal-close", className="ms-auto", n_clicks=0
                )
            ),
        ],
        id="buoy-maintenance-modal",
        is_open=False,
        centered=True,
        backdrop="static",
        keyboard=False,
        contentClassName="border border-secondary shadow-lg",
    ),
], fluid=True)


# Callbacks

@dash.callback(
    Output("buoy-station-status-alert", "children"),
    [Input("url", "pathname"), Input("buoy-tabs", "value")]
)
def update_buoy_status_alert(pathname, active_tab):
    """Display a prominent alert banner based on current tab and data availability"""
    if not pathname:
        return None
    
    parts = pathname.strip("/").split("/")
    if len(parts) < 3:
        return None
    
    station_num = parts[2]
    
    # Default to timeseries if active_tab is None
    if active_tab is None:
        active_tab = "tab-timeseries"
    
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        stations_collection = db[STATIONS_INFO]
        
        # Get buoy info from stations_info collection
        doc = stations_collection.find_one({"type": "Buoy"})
        manual_status = doc.get("status", "Unknown") if doc else "Unknown"
        client.close()
        
        # Calculate 6 hours ago threshold
        now = datetime.now(timezone.utc)
        six_hours_ago = now - timedelta(hours=6)
        
        # Check data availability based on active tab
        if active_tab == "tab-timeseries":
            # Check atmospheric data
            try:
                test_df = buoy.fetch_time_series("6H", buoy.scalar_params[:1], agg="None")
                
                if not test_df.empty and 'datetime' in test_df.columns:
                    # Get the most recent timestamp
                    max_time = pd.to_datetime(test_df['datetime']).max()
                    # Make sure it's timezone aware
                    if max_time.tzinfo is None:
                        max_time = max_time.tz_localize('UTC')
                    
                    has_recent_data = max_time >= six_hours_ago
                else:
                    has_recent_data = False
                
                data_type = "atmospheric"
            except Exception as e:
                print(f"Error fetching atmospheric data: {e}")
                import traceback
                traceback.print_exc()
                has_recent_data = False
                data_type = "atmospheric"
        else:
            # Check profile data
            try:
                times, docs = buoy.fetch_profiles("6H")
                
                if times and len(times) > 0:
                    # Convert times to datetime and find most recent
                    max_time = max(times)
                    # Make sure it's timezone aware
                    if max_time.tzinfo is None:
                        max_time = max_time.replace(tzinfo=timezone.utc)
                    
                    has_recent_data = max_time >= six_hours_ago
                else:
                    has_recent_data = False
                
                data_type = "profile"
            except Exception as e:
                print(f"Error fetching profile data: {e}")
                import traceback
                traceback.print_exc()
                has_recent_data = False
                data_type = "profile"
        
        # Determine status: prioritize lack of recent data, then manual status
        if not has_recent_data:
            data_label = "atmospheric data" if data_type == "atmospheric" else "vertical profile data"
            
            # No data in last 6 hours
            if manual_status == "Maintenance":
                return dbc.Alert([
                    html.I(className="fas fa-tools me-2"),
                    html.Strong("Buoy Under Maintenance:"),
                    html.Span(f" This buoy station is currently undergoing maintenance. No {data_label} received in the last 6 hours.", className="ms-2")
                ], color="warning", className="mb-3")
            elif manual_status == "Decommissioned":
                return dbc.Alert([
                    html.I(className="fas fa-archive me-2"),
                    html.Strong("Buoy Decommissioned:"),
                    html.Span(f" This buoy station has been decommissioned. Only historical {data_label} is available.", className="ms-2")
                ], color="secondary", className="mb-3")
            else:
                # No manual status, but no recent data
                return dbc.Alert([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    html.Strong("No Recent Data:"),
                    html.Span(f" This station is has not transmitted {data_label} in the last 6 hours. It is currently under maintenance.", className="ms-2")
                ], color="warning", className="mb-3")
        
        # Has recent data, check manual status only
        if manual_status == "Maintenance":
            return dbc.Alert([
                html.I(className="fas fa-tools me-2"),
                html.Strong("Buoy Under Maintenance:"),
                html.Span(" This buoy station is currently undergoing maintenance. Data may be limited.", className="ms-2")
            ], color="warning", className="mb-3")
        elif manual_status == "Faulty":
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                html.Strong("Buoy Reporting Issues:"),
                html.Span(" This buoy is experiencing technical issues. Data may be unreliable.", className="ms-2")
            ], color="danger", className="mb-3")
        
        # Buoy is operational with recent data
        return None
        
    except Exception as e:
        print(f"Error checking buoy status: {e}")
        import traceback
        traceback.print_exc()
        return None


@dash.callback(
    Output("buoy-maintenance-modal", "is_open"),
    [Input("url", "pathname"), Input("buoy-maintenance-modal-close", "n_clicks"), Input("buoy-tabs", "value")],
    State("buoy-maintenance-modal", "is_open")
)
def manage_buoy_maintenance_modal(pathname, close_clicks, active_tab, is_open):
    """
    Show maintenance modal if no data in past 6 hours based on current tab.
    """
    ctx = dash.callback_context
    if not ctx.triggered:
        trigger_id = "url.pathname" if pathname else None
    else:
        trigger_id = ctx.triggered[0]["prop_id"]
    
    # close button clicked
    if trigger_id == "buoy-maintenance-modal-close.n_clicks":
        return False
    
    # Default to timeseries if active_tab is None
    if active_tab is None:
        active_tab = "tab-timeseries"
        
    # URL changed or Tab changed / Page Load
    if trigger_id in ["url.pathname", "buoy-tabs.value"] or (pathname and not is_open and close_clicks == 0):
        parts = pathname.strip("/").split("/")
        if len(parts) < 3:
            return is_open
        
        station_num = parts[2]
        
        try:
            # Calculate 6 hours ago threshold
            now = datetime.now(timezone.utc)
            six_hours_ago = now - timedelta(hours=6)
            
            # Check data availability based on active tab
            if active_tab == "tab-timeseries":
                # Check atmospheric data timestamp
                test_df = buoy.fetch_time_series("6H", buoy.scalar_params[:1], agg="None")
                
                if not test_df.empty and 'datetime' in test_df.columns:
                    max_time = pd.to_datetime(test_df['datetime']).max()
                    if max_time.tzinfo is None:
                        max_time = max_time.tz_localize('UTC')
                    has_recent_data = max_time >= six_hours_ago
                else:
                    has_recent_data = False
            else:
                # Check profile data timestamp
                times, docs = buoy.fetch_profiles("6H")
                
                if times and len(times) > 0:
                    max_time = max(times)
                    if max_time.tzinfo is None:
                        max_time = max_time.replace(tzinfo=timezone.utc)
                    has_recent_data = max_time >= six_hours_ago
                else:
                    has_recent_data = False
            
            print(f"DEBUG Modal: Tab={active_tab}, has_recent_data={has_recent_data}")
            
            if not has_recent_data:
                return True
                
        except Exception as e:
            print(f"Error checking recent buoy data for modal: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    return is_open


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
        df = buoy.fetch_time_series(dr_ts, params_ts, agg="None")
        if df.empty:
            return html.Div("No data available.", style={"color": "gray"})
        figs = buoy.create_time_series_figures(df, params_ts)
        return html.Div([
            dcc.Graph(
                figure=fig,
                style={"border": "2px solid lightgray", "padding": "5px", "height": "40vh"}
            )
            for fig in figs
        ], style={"display": "flex", "flexDirection": "column", "gap": "10px"})

    # Vertical Profiles: unpack fetch_profiles() directly
    times, docs = buoy.fetch_profiles(dr_pf)
    if not times or not docs:
        return html.Div("No profile data.", style={"color": "gray"})

    graphs = []
    for p in params_pf:
        fig = buoy.create_profile_figure(times, docs, p)
        graphs.append(dcc.Graph(
            figure=fig,
            style={"border": "2px solid lightgray", "padding": "5px", "height": "40vh"}
        ))
    return html.Div(graphs, style={"display": "flex", "flexDirection": "column", "gap": "10px"})


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
