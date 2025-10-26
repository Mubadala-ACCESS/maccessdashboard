# stationdata_fidas.py

import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, callback_context, no_update
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go
from graphs.fidas_graphs import FidasGraphs

dash.register_page(
    __name__,
    path_template="/stationdata/fidas/<station_num>",
    title="Station Monitoring Dashboard"
)

fidas = FidasGraphs()

layout = dbc.Container([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="fidas-current-dt"),

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
          ], value="1D", className="maccess-dropdown"),

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
          html.Label("Select Parameters", className="fw-semibold text-uppercase text-muted small"),
          dcc.Checklist(id="fidas-param-checklist",
            className="fidas-param-checklist list-unstyled",
            options=[{"label":fidas.param_labels[p],"value":p}
                     for p in fidas.scalar_params],
            value=["PM2.5","PMtot"]
          ),

          html.Hr(className="maccess-divider"),
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
            
            # Week/Day Navigation
            html.Div([
              dbc.Button("+1w", id="fidas-next-week", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("+1d", id="fidas-next-day", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("-1d", id="fidas-prev-day", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("-1w", id="fidas-prev-week", size="sm", color="light", className="fidas-nav-button"),
            ], style={"display":"flex", "gap":"6px", "justifyContent":"center", "marginBottom":"8px"}),
            
            # Year/Month Navigation
            html.Div([
              dbc.Button("+1yr", id="fidas-next-year", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("+6mo", id="fidas-next-6month", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("-6mo", id="fidas-prev-6month", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("-1yr", id="fidas-prev-year", size="sm", color="light", className="fidas-nav-button"),
            ], style={"display":"flex", "gap":"6px", "justifyContent":"center", "marginBottom":"8px"}),
            
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
            
            # Hour Navigation
            html.Div([
              dbc.Button("+12hr", id="fidas-next-12hour", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("+1hr", id="fidas-next-hour", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("-1hr", id="fidas-prev-hour", size="sm", color="light", className="fidas-nav-button"),
              dbc.Button("-12hr", id="fidas-prev-12hour", size="sm", color="light", className="fidas-nav-button"),
            ], style={"display":"flex", "gap":"6px", "justifyContent":"center"}),
          ], id="step-controls",
             style={"display":"block"}),

          html.Hr(className="maccess-divider"),
          dbc.Button("Download Data", id="fidas-download-open", color="primary", className="w-100 rounded-md")
        ], style={"overflowY": "auto", "height": "100%", "position": "relative"})
      ],
      className="mb-2 maccess-card",
      style={
        "height":"85vh", "overflowX": "visible", "overflowY": "hidden"
      }), width=4, className="p-1"),

      # Graphs
      dbc.Col(dbc.Card([
        dbc.CardBody([
          dcc.Tabs(id="fidas-tabs", value="tab-timeseries", children=[
            dcc.Tab(label="Time Series", value="tab-timeseries"),
            dcc.Tab(label="Spectra",     value="tab-spectra"),
          ]),
          html.Div(id="fidas-tab-content", style={
            "height":"88vh","overflow-y":"auto","overflow-x":"hidden","padding":"20px","scrollSnapType":"y mandatory"
          })
        ], style={"padding":"0"})
      ],
      className="mb-2 maccess-card",
      style={
        "height":"92vh","overflow":"hidden"
      }), width=8, className="p-1")
    ], class_name="mb-3", align="center", justify="center"),

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
], fluid=True)


# ─── CALLBACKS ─────────────────────────────────────────────────────

# show step‐controls only on Spectra tab
@dash.callback(
    Output("step-controls","style"),
    Input("fidas-tabs","value")
)
def _show_steps(tab):
    return {"display":"block"} if tab=="tab-spectra" else {"display":"none"}


# Callback to update date picker value when navigation buttons are clicked
@dash.callback(
    Output("fidas-date-picker", "value"),
    [Input("fidas-prev-day", "n_clicks"),
     Input("fidas-next-day", "n_clicks"),
     Input("fidas-prev-week", "n_clicks"),
     Input("fidas-next-week", "n_clicks"),
     Input("fidas-prev-6month", "n_clicks"),
     Input("fidas-next-6month", "n_clicks"),
     Input("fidas-prev-year", "n_clicks"),
     Input("fidas-next-year", "n_clicks")],
    State("fidas-date-picker", "value"),
    prevent_initial_call=True,
    suppress_callback_exceptions=True
)
def _update_date_picker(prev_day, next_day, prev_week, next_week, 
                        prev_6mo, next_6mo, prev_year, next_year, current_date):
    from datetime import datetime as dt, timedelta
    from dateutil.relativedelta import relativedelta
    
    trig = callback_context.triggered_id
    if not trig or not current_date:
        return no_update
    
    try:
        current = dt.strptime(current_date, "%Y-%m-%d")
        
        # Map button IDs to time deltas
        delta_map = {
            "fidas-prev-day": timedelta(days=-1),
            "fidas-next-day": timedelta(days=1),
            "fidas-prev-week": timedelta(weeks=-1),
            "fidas-next-week": timedelta(weeks=1),
            "fidas-prev-6month": relativedelta(months=-6),
            "fidas-next-6month": relativedelta(months=6),
            "fidas-prev-year": relativedelta(years=-1),
            "fidas-next-year": relativedelta(years=1),
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
     Input("fidas-prev-12hour", "n_clicks"),
     Input("fidas-next-12hour", "n_clicks")],
    State("fidas-time-input", "value"),
    prevent_initial_call=True,
    suppress_callback_exceptions=True
)
def _update_time_picker(prev_hr, next_hr, prev_12hr, next_12hr, current_time):
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
            "fidas-prev-12hour": timedelta(hours=-12),
            "fidas-next-12hour": timedelta(hours=12),
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
      Input("fidas-prev-week","n_clicks"),
      Input("fidas-next-week","n_clicks"),
      Input("fidas-prev-6month","n_clicks"),
      Input("fidas-next-6month","n_clicks"),
      Input("fidas-prev-year","n_clicks"),
      Input("fidas-next-year","n_clicks"),
      Input("fidas-prev-hour","n_clicks"),
      Input("fidas-next-hour","n_clicks"),
      Input("fidas-prev-12hour","n_clicks"),
      Input("fidas-next-12hour","n_clicks")
    ],
    State("fidas-current-dt","data"),
    prevent_initial_call=False
)
def _update_current_dt(
    dr, params,
    picked_date,
    picked_time,
    prev_day, next_day,
    prev_week, next_week,
    prev_6mo, next_6mo,
    prev_year, next_year,
    prev_hr, next_hr,
    prev_12hr, next_12hr,
    cur_iso
):
    trig = callback_context.triggered_id

    # initialize when period or params first fire
    if trig in ("fidas-date-range","fidas-param-checklist") and cur_iso is None:
        times = fidas.list_datetimes(dr)
        return times[-1].isoformat() if times else None
    
    # Handle navigation buttons (date and time)
    nav_buttons = ("fidas-prev-day", "fidas-next-day", "fidas-prev-week", "fidas-next-week",
                   "fidas-prev-6month", "fidas-next-6month", "fidas-prev-year", "fidas-next-year",
                   "fidas-prev-hour", "fidas-next-hour", "fidas-prev-12hour", "fidas-next-12hour")
    
    if trig in nav_buttons and cur_iso:
        from datetime import timedelta
        from datetime import datetime as dt
        from dateutil.relativedelta import relativedelta
        
        current_dt = dt.fromisoformat(cur_iso)
        
        # Map button IDs to time deltas
        delta_map = {
            "fidas-prev-day": timedelta(days=-1),
            "fidas-next-day": timedelta(days=1),
            "fidas-prev-week": timedelta(weeks=-1),
            "fidas-next-week": timedelta(weeks=1),
            "fidas-prev-6month": relativedelta(months=-6),
            "fidas-next-6month": relativedelta(months=6),
            "fidas-prev-year": relativedelta(years=-1),
            "fidas-next-year": relativedelta(years=1),
            "fidas-prev-hour": timedelta(hours=-1),
            "fidas-next-hour": timedelta(hours=1),
            "fidas-prev-12hour": timedelta(hours=-12),
            "fidas-next-12hour": timedelta(hours=12),
        }
        
        if trig in delta_map:
            target_dt = current_dt + delta_map[trig]
            
            # Find closest available datetime in data
            available_times = fidas.list_datetimes(dr)
            if available_times:
                closest = min(available_times, key=lambda t: abs((t - target_dt).total_seconds()))
                return closest.isoformat()
        
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
        return html.Div([dcc.Graph(figure=fig, config={'displayModeBar': False}, style={"height":"85vh","scrollSnapAlign":"start","padding":"0","margin":"0"}) for fig in figs],
                        style={"display":"flex","flexDirection":"column","gap":"0"})

    # Spectra
    if not cur_iso:
        return html.Div("No spectrum selected.", style={"color":"gray"})
    dt = datetime.fromisoformat(cur_iso)
    doc = fidas.fetch_spectrum_doc(dt)
    if not doc:
        return html.Div("Spectrum not found.", style={"color":"gray"})
    fig = fidas.create_spectrum_figure(doc["sizes"], doc["spectra"])
    return dcc.Graph(figure=fig, config={'displayModeBar': False}, style={"height":"85vh","width":"100%","scrollSnapAlign":"start","padding":"0","margin":"0"})


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
