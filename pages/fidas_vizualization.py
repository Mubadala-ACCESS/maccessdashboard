# stationdata_fidas.py

import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, callback_context, no_update
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from graphs.fidas_graphs import FidasGraphs
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

dash.register_page(
    __name__,
    path_template="/stationdata/Fidas_Palas/<station_num>",
    title="Station Monitoring Dashboard"
)

fidas = FidasGraphs()

layout = dbc.Container([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="fidas-current-dt"),
    html.Div(id="fidas-station-name-header", style={"marginBottom": "0.5rem", "marginTop": "0"}),
    html.Div(id="fidas-status-alert", style={"marginBottom": "0.5rem"}),

    dbc.Row([
      # Controls
      dbc.Col(dbc.Card([
        dbc.CardBody([
          html.Label("Display Period", className="maccess-panel-title mb-2"),
          dcc.Dropdown(id="fidas-date-range", options=[
            {"label":"Past 6 Hours","value":"6H"},
            {"label":"Past 12 Hours","value":"12H"},
            {"label":"Past 1 Day","value":"1D"},
            {"label":"Past 1 Week","value":"1W"},
            {"label":"Past 1 Month","value":"1M"},
            {"label":"Past 3 Months","value":"3M"},
            {"label":"Past 6 Months","value":"6M"},
            {"label":"Past 1 Year","value":"1Y"},
            {"label":"All Data","value":"All"},
          ], value="1D", className="maccess-dropdown", style={"marginBottom":"12px"}),

          html.Div([
            html.Hr(className="maccess-divider"),
            html.Label("Aggregation", className="fw-semibold text-uppercase text-muted small"),
            dcc.Dropdown(id="fidas-aggregation", options=[
              {"label":"None","value":"None"},
              {"label":"Hourly","value":"H"},
              {"label":"Daily","value":"D"},
              {"label":"Weekly","value":"W"},
              {"label":"Monthly","value":"M"},
            ], value="None", className="maccess-dropdown"),
            html.Hr(className="maccess-divider"),
          ], id="fidas-aggregation-controls", className="dashboard-sidebar-section"),

          html.Div([
            html.Label("Select Parameters", className="fw-semibold text-uppercase text-muted small"),
            dcc.Checklist(id="fidas-param-checklist",
              className="fidas-param-checklist list-unstyled",
              options=[{"label":fidas.param_labels[p],"value":p}
                       for p in fidas.scalar_params],
              value=["PM2.5","PMtot"]
            ),
            html.Hr(className="maccess-divider"),
          ], id="fidas-params-controls", className="dashboard-sidebar-section"),

          html.Div([
            # Date Input
            html.Div([
              dbc.Input(
                id="fidas-date-picker",
                type="date",
                value=datetime.now().strftime("%Y-%m-%d"),
                className="fidas-date-input",
                size="sm"
              ),
            ], style={"display":"flex", "justifyContent":"center", "marginBottom":"8px"}),

            # Day Navigation
            html.Div([
              dbc.Button("< 1d", id="fidas-prev-day", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("1d >", id="fidas-next-day", size="sm", color="light", className="fidas-nav-button"),
            ], style={"display":"flex", "gap":"6px", "justifyContent":"center", "marginBottom":"12px"}),

            # Time Input
            html.Div([
              dbc.Input(
                id="fidas-time-input",
                type="time",
                value=datetime.now().strftime("%H:%M"),
                className="fidas-time-input",
                size="sm"
              ),
            ], style={"display":"flex", "justifyContent":"center", "marginBottom":"8px"}),

            # Hour/Minute Navigation
            html.Div([
              dbc.Button("< 1hr", id="fidas-prev-hour", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("< 1min", id="fidas-prev-minute", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("1min >", id="fidas-next-minute", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("1hr >", id="fidas-next-hour", size="sm", color="light", className="fidas-nav-button"),
            ], style={"display":"flex", "gap":"6px", "justifyContent":"center"}),
          ], id="step-controls",
             style={"display":"block"}, className="dashboard-sidebar-section"),

          html.Hr(className="maccess-divider"),
          dbc.Button("Download Data", id="fidas-download-open", color="primary", className="w-100 rounded-md")
        ], style={"overflowY": "auto", "height": "100%", "position": "relative"})
      ],
      className="maccess-card dashboard-sidebar-scroll",
      style={
        "height":"100%", "overflowX": "visible", "overflowY": "hidden"
      }), width=4, className="dashboard-sidebar"),

      # Graphs
      dbc.Col(dbc.Card([
        dbc.CardBody([
          dcc.Tabs(id="fidas-tabs", value="tab-timeseries", children=[
            dcc.Tab(label="Time Series", value="tab-timeseries"),
            dcc.Tab(label="Spectra",     value="tab-spectra"),
          ]),
          dcc.Loading(
            children=html.Div(
              id="fidas-tab-content",
              className="dashboard-graph-stack",
              style={
                "height": "100%",
                "overflow-y": "auto",
                "overflow-x": "hidden",
                "padding": "20px"
              }
            ),
            type="default",
            className="w-100 h-100"
          )
        ], style={"padding":"0"})
      ],
      className="maccess-card",
      style={
        "height":"100%","overflow":"hidden"
      }), width=8, className="dashboard-main")
    ], class_name="dashboard-layout-row", align="stretch", justify="start"),

    # Download Modal
    dbc.Modal([
      dbc.ModalHeader(dbc.ModalTitle("Download Fidas Data")),
      dbc.ModalBody([
        html.Label("Select Date Range:", style={"fontWeight":"bold"}),
        dcc.Dropdown(id="fidas-download-range", options=[
          {"label":"Past 6 Hours","value":"6H"},
          {"label":"Past 12 Hours","value":"12H"},
          {"label":"Past 1 Day","value":"1D"},
          {"label":"Past 1 Week","value":"1W"},
          {"label":"Past 1 Month","value":"1M"},
          {"label":"Past 3 Months","value":"3M"},
          {"label":"Past 6 Months","value":"6M"},
          {"label":"Past 1 Year","value":"1Y"},
          {"label":"All Data","value":"All"},
        ], value="1D"),
        html.Br(),
        html.Label("Select Parameters:", style={"fontWeight":"bold"}),
        dcc.Checklist(id="fidas-download-params",
          style={"height":"20vh","overflowY":"auto"},
          options=[{"label":fidas.param_labels[p],"value":p}
                   for p in fidas.scalar_params],
          value=["PM2.5","PMtot"]
        )
      ]),
      dbc.ModalFooter([
        dbc.Button("Download CSV", id="fidas-download-confirm", className="me-2"),
        dbc.Button("Close",           id="fidas-download-close")
      ])
    ],
    id="fidas-download-modal", is_open=False),

    dcc.Download(id="fidas-download-data")
], fluid=True, className="dashboard-shell", style={"marginTop": "-50px"})


# ─── CALLBACKS ─────────────────────────────────────────────────────

@dash.callback(
    Output("fidas-station-name-header", "children"),
    Input("url", "pathname")
)
def update_fidas_station_name(pathname):
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
        
        doc = collection.find_one({"type": "Fidas_Palas"})
        station_name = doc.get("name", "Fidas Palas 200S") if doc else "Fidas Palas 200S"
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
    Output("fidas-status-alert", "children"),
    Input("url", "pathname")
)
def update_fidas_status_alert(pathname):
    """Display a prominent alert banner if station has no recent data or has status issues"""
    if not pathname:
        return None
    
    try:
        from datetime import datetime, timedelta, timezone
        
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        stations_collection = db[STATIONS_INFO]
        
        # Get station info and manual status
        doc = stations_collection.find_one({"type": "Fidas_Palas"})
        manual_status = doc.get("status", "Unknown") if doc else "Unknown"
        
        # Check for recent data (within last 24 hours)
        fidas_collection = db["fidas_nyuad"]
        now = datetime.now(timezone.utc)
        twenty_four_hours_ago = now - timedelta(hours=24)
        
        try:
            recent_data = fidas_collection.find_one(
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
                    html.Strong("No Recent Data:"),
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


# show step‐controls only on Spectra tab
@dash.callback(
    Output("step-controls","style"),
    Output("fidas-aggregation-controls","style"),
    Output("fidas-params-controls","style"),
    Input("fidas-tabs","value")
)
def _toggle_controls(tab):
    is_spectra = tab == "tab-spectra"
    step_style = {"display":"block"} if is_spectra else {"display":"none"}
    visible_style = {"display":"block"}
    hidden_style = {"display":"none"}
    agg_style = hidden_style if is_spectra else visible_style
    params_style = hidden_style if is_spectra else visible_style
    return step_style, agg_style, params_style


# Callback to update date picker value when navigation buttons are clicked
@dash.callback(
    Output("fidas-date-picker", "value"),
    [Input("fidas-prev-day", "n_clicks"),
     Input("fidas-next-day", "n_clicks")],
    State("fidas-date-picker", "value"),
    prevent_initial_call=True,
    suppress_callback_exceptions=True
)
def _update_date_picker(prev_day, next_day, current_date):
    from datetime import datetime as dt, timedelta
    
    trig = callback_context.triggered_id
    if not trig or not current_date:
        return no_update
    
    try:
        current = dt.strptime(current_date, "%Y-%m-%d")
        
        # Map button IDs to time deltas
        delta_map = {
            "fidas-prev-day": timedelta(days=-1),
            "fidas-next-day": timedelta(days=1),
        }
        
        if trig in delta_map:
            new_date = current + delta_map[trig]
            return new_date.strftime("%Y-%m-%d")
        
        return no_update
    except:
        return no_update


# Callback to update time input value when hour navigation buttons are clicked
@dash.callback(
    Output("fidas-time-input", "value"),
    [Input("fidas-prev-hour", "n_clicks"),
     Input("fidas-next-hour", "n_clicks"),
     Input("fidas-prev-minute", "n_clicks"),
     Input("fidas-next-minute", "n_clicks")],
    State("fidas-time-input", "value"),
    prevent_initial_call=True,
    suppress_callback_exceptions=True
)
def _update_time_picker(prev_hr, next_hr, prev_min, next_min, current_time):
    from datetime import datetime as dt, timedelta
    
    trig = callback_context.triggered_id
    if not trig or not current_time:
        return no_update
    
    try:
        # Parse current time (HH:MM format)
        current = dt.strptime(current_time, "%H:%M")
        
        # Map button IDs to time deltas
        delta_map = {
            "fidas-prev-hour": timedelta(hours=-1),
            "fidas-next-hour": timedelta(hours=1),
            "fidas-prev-minute": timedelta(minutes=-1),
            "fidas-next-minute": timedelta(minutes=1),
        }
        
        if trig in delta_map:
            new_time = current + delta_map[trig]
            return new_time.strftime("%H:%M")
        
        return no_update
    except:
        return no_update


# single callback for both init & date-picking of fidas-current-dt
@dash.callback(
    Output("fidas-current-dt","data"),
    [
      Input("fidas-date-range","value"),
      Input("fidas-param-checklist","value"),
      Input("fidas-date-picker","value"),
      Input("fidas-time-input","value"),
      Input("fidas-prev-day","n_clicks"),
      Input("fidas-next-day","n_clicks"),
      Input("fidas-prev-hour","n_clicks"),
      Input("fidas-next-hour","n_clicks"),
      Input("fidas-prev-minute","n_clicks"),
      Input("fidas-next-minute","n_clicks")
    ],
    State("fidas-current-dt","data"),
    prevent_initial_call=False
)
def _update_current_dt(
    dr, params,
    picked_date,
    picked_time,
    prev_day, next_day,
    prev_hr, next_hr,
    prev_min, next_min,
    cur_iso
):
    trig = callback_context.triggered_id

    # initialize when period or params first fire
    if trig in ("fidas-date-range","fidas-param-checklist") and cur_iso is None:
        times = fidas.list_datetimes(dr)
        return times[-1].isoformat() if times else None
    
    # Handle navigation buttons (date and time)
    nav_buttons = (
        "fidas-prev-day", "fidas-next-day",
        "fidas-prev-hour", "fidas-next-hour",
        "fidas-prev-minute", "fidas-next-minute"
    )
    
    if trig in nav_buttons and cur_iso:
        from bisect import bisect_left, bisect_right
        from datetime import timedelta
        from datetime import datetime as dt
        
        current_dt = dt.fromisoformat(cur_iso)
        
        # Map button IDs to time deltas
        delta_map = {
            "fidas-prev-day": timedelta(days=-1),
            "fidas-next-day": timedelta(days=1),
            "fidas-prev-hour": timedelta(hours=-1),
            "fidas-next-hour": timedelta(hours=1),
            "fidas-prev-minute": timedelta(minutes=-1),
            "fidas-next-minute": timedelta(minutes=1),
        }
        
        if trig in delta_map:
            available_times = fidas.list_datetimes(dr)
            if not available_times:
                return cur_iso
            
            target_dt = current_dt + delta_map[trig]
            forward_buttons = {"fidas-next-day", "fidas-next-hour", "fidas-next-minute"}
            timestamps = [t.timestamp() for t in available_times]
            curr_ts = current_dt.timestamp()
            target_ts = target_dt.timestamp()
            
            if trig in forward_buttons:
                idx = bisect_left(timestamps, target_ts)
                if idx < len(available_times):
                    return available_times[idx].isoformat()
                idx = bisect_right(timestamps, curr_ts)
                if idx < len(available_times):
                    return available_times[idx].isoformat()
                return available_times[-1].isoformat()
            else:
                idx = bisect_right(timestamps, target_ts) - 1
                if idx >= 0:
                    return available_times[idx].isoformat()
                idx = bisect_left(timestamps, curr_ts) - 1
                if idx >= 0:
                    return available_times[idx].isoformat()
                return available_times[0].isoformat()
        
        return cur_iso

    # date-picker or time-input jump
    if trig in ("fidas-date-picker", "fidas-time-input") and picked_date:
        try:
            # Parse the date string (format: YYYY-MM-DD from HTML5 date input)
            if isinstance(picked_date, str):
                day = pd.to_datetime(picked_date).date()
            else:
                day = picked_date
            
            # Parse time if provided
            hour, minute = 0, 0
            if picked_time:
                try:
                    time_parts = picked_time.split(":")
                    hour = int(time_parts[0])
                    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                except:
                    pass
            
            # Find closest matching datetime in available data
            from datetime import datetime as dt
            target_dt = dt.combine(day, dt.min.time().replace(hour=hour, minute=minute))
            available_times = fidas.list_datetimes(dr)
            
            if available_times:
                # Find the closest available time
                closest = min(available_times, key=lambda t: abs((t - target_dt).total_seconds()))
                return closest.isoformat()
        except Exception as e:
            print(f"Date/time picker error: {e}")
            return cur_iso
        
        return cur_iso

    return cur_iso


@dash.callback(
    Output("fidas-tab-content","children"),
    [
      Input("fidas-tabs","value"),
      Input("fidas-date-range","value"),
      Input("fidas-aggregation","value"),
      Input("fidas-param-checklist","value"),
      Input("fidas-current-dt","data")
    ]
)
def _render_tab(tab, dr, agg, params, cur_iso):
    if tab=="tab-timeseries":
        # Reverse parameters so newest selections appear on top
        if params:
            params = list(reversed(params))
        df = fidas.fetch_time_series(dr, params, agg)
        if df.empty:
            return html.Div("No data available.", style={"color":"gray"})
        figs = fidas.create_time_series_figures(df, params)
        return html.Div([
            dbc.Card(
                dbc.CardBody(
                    dcc.Graph(figure=fig, config={'displayModeBar': True, 'displaylogo': False})
                ),
                className="maccess-card dashboard-graph-card",
                style={"border": "none"}
            )
            for fig in figs
        ], style={"display":"flex","flexDirection":"column","gap":"0"})

    # Spectra
    if not cur_iso:
        return html.Div("No spectrum selected.", style={"color":"gray"})
    dt = datetime.fromisoformat(cur_iso)
    doc = fidas.fetch_spectrum_doc(dt)
    if not doc:
        return html.Div("Spectrum not found.", style={"color":"gray"})
    fig = fidas.create_spectrum_figure(doc["sizes"], doc["spectra"])
    return dbc.Card(
        dbc.CardBody(
            dcc.Graph(figure=fig, config={'displayModeBar': True, 'displaylogo': False})
        ),
        className="maccess-card dashboard-graph-card",
        style={"border":"none"}
    )


# Download‐modal callbacks (unchanged)
@dash.callback(
    Output("fidas-download-modal","is_open"),
    [Input("fidas-download-open","n_clicks"), Input("fidas-download-close","n_clicks")],
    State("fidas-download-modal","is_open")
)
def _toggle_modal(o,c,is_open):
    if not callback_context.triggered:
        return is_open
    return not is_open

@dash.callback(
    Output("fidas-download-data","data"),
    Input("fidas-download-confirm","n_clicks"),
    State("fidas-download-range","value"),
    State("fidas-download-params","value"),
    prevent_initial_call=True
)
def _dl_csv(n, dr, params):
    df = fidas.fetch_time_series(dr, params, "None")
    return dcc.send_data_frame(df.to_csv, "fidas_data.csv", index=False)
