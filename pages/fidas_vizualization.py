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
          html.Label("Display Period", style={"font-weight":"bold"}),
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
          ], value="1D"),

          html.Hr(style={"border-top":"2px solid purple"}),
          html.Label("Aggregation", style={"font-weight":"bold"}),
          dcc.Dropdown(id="fidas-aggregation", options=[
            {"label":"None","value":"None"},
            {"label":"Hourly","value":"H"},
            {"label":"Daily","value":"D"},
            {"label":"Weekly","value":"W"},
            {"label":"Monthly","value":"M"},
          ], value="None"),

          html.Hr(style={"border-top":"2px solid purple"}),
          html.Label("Select Parameters", style={"font-weight":"bold"}),
          dcc.Checklist(id="fidas-param-checklist",
            style={"height":"24vh","overflow-y":"auto"},
            options=[{"label":fidas.param_labels[p],"value":p}
                     for p in fidas.scalar_params],
            value=["PM2.5","PMtot"]
          ),

          html.Hr(style={"border-top":"2px solid purple"}),
          html.Div(dbc.Row([
            dbc.Col(dbc.Button("« Yr",  id="step-prev-year",  size="sm"), width="auto"),
            dbc.Col(dbc.Button("‹ Mo",  id="step-prev-month", size="sm"), width="auto"),
            dbc.Col(dbc.Button("– Dy",  id="step-prev-day",   size="sm"), width="auto"),
            dbc.Col(dbc.Button("— Hr",  id="step-prev-hour",  size="sm"), width="auto"),
            dbc.Col(dbc.Button("· Min", id="step-prev-min",   size="sm"), width="auto"),
            dbc.Col(dcc.DatePickerSingle(
              id="fidas-date-picker",
              date=datetime.now().date(),
              display_format="YYYY-MM-DD"
            ), width="auto", style={"padding-left":"8px"}),
            dbc.Col(dbc.Button("Min ·", id="step-next-min",   size="sm"), width="auto"),
            dbc.Col(dbc.Button("Hr —", id="step-next-hour",  size="sm"), width="auto"),
            dbc.Col(dbc.Button("Dy –", id="step-next-day",   size="sm"), width="auto"),
            dbc.Col(dbc.Button("Mo ›", id="step-next-month", size="sm"), width="auto"),
            dbc.Col(dbc.Button("Yr »", id="step-next-year",  size="sm"), width="auto"),
          ]), id="step-controls",
             style={"display":"none","margin":"10px 0"}),

          html.Hr(style={"border-top":"2px solid purple"}),
          dbc.Button("Download Data", id="fidas-download-open", color="primary", className="w-100")
        ])
      ],
      className="mb-2",
      style={
        "border":"3px solid purple","box-shadow":"2px 2px 5px lightgrey",
        "height":"85vh","overflow-y":"auto"
      }), width=3, style={"padding":"10px"}),

      # Graphs
      dbc.Col(dbc.Card([
        dbc.CardBody([
          dcc.Tabs(id="fidas-tabs", value="tab-timeseries", children=[
            dcc.Tab(label="Time Series", value="tab-timeseries"),
            dcc.Tab(label="Spectra",     value="tab-spectra"),
          ]),
          html.Div(id="fidas-tab-content", style={
            "height":"80vh","overflow-y":"auto","padding":"10px"
          })
        ])
      ],
      className="mb-2",
      style={
        "border":"3px solid purple","box-shadow":"2px 2px 5px lightgrey",
        "height":"85vh","overflow":"hidden"
      }), width=9, style={"padding":"10px"})
    ], class_name="mb-3", align="center"),

    # Download Modal
    dbc.Modal([
      dbc.ModalHeader("Download Fidas Data"),
      dbc.ModalBody([
        html.Label("Select Date Range:", style={"font-weight":"bold"}),
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
        html.Label("Select Parameters:", style={"font-weight":"bold"}),
        dcc.Checklist(id="fidas-download-params",
          style={"height":"20vh","overflow-y":"auto"},
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
    return {"display":"block","margin":"10px 0"} if tab=="tab-spectra" else {"display":"none"}


# single callback for both init & stepping of fidas-current-dt
@dash.callback(
    Output("fidas-current-dt","data"),
    [
      Input("fidas-date-range","value"),
      Input("fidas-param-checklist","value"),

      Input("step-prev-min","n_clicks"),  Input("step-next-min","n_clicks"),
      Input("step-prev-hour","n_clicks"), Input("step-next-hour","n_clicks"),
      Input("step-prev-day","n_clicks"),  Input("step-next-day","n_clicks"),
      Input("step-prev-month","n_clicks"),Input("step-next-month","n_clicks"),
      Input("step-prev-year","n_clicks"), Input("step-next-year","n_clicks"),

      Input("fidas-date-picker","date")
    ],
    State("fidas-current-dt","data"),
    prevent_initial_call=False
)
def _update_current_dt(
    dr, params,
    prev_min, nxt_min, prev_hr, nxt_hr,
    prev_dy, nxt_dy, prev_mo, nxt_mo,
    prev_yr, nxt_yr,
    picked_date,
    cur_iso
):
    trig = callback_context.triggered_id

    # initialize when period or params first fire
    if trig in ("fidas-date-range","fidas-param-checklist") and cur_iso is None:
        times = fidas.list_datetimes(dr)
        return times[-1].isoformat() if times else None

    # date‐picker jump
    if trig == "fidas-date-picker" and picked_date:
        day = pd.to_datetime(picked_date).date()
        for t in fidas.list_datetimes(dr):
            if t.date()==day:
                return t.isoformat()
        return cur_iso

    # stepping
    delta_map = {
      "step-prev-min":   {"minutes": -1},
      "step-next-min":   {"minutes": +1},
      "step-prev-hour":  {"hours":   -1},
      "step-next-hour":  {"hours":   +1},
      "step-prev-day":   {"days":    -1},
      "step-next-day":   {"days":    +1},
      "step-prev-month": {"months":  -1},
      "step-next-month": {"months":  +1},
      "step-prev-year":  {"years":   -1},
      "step-next-year":  {"years":   +1},
    }
    if cur_iso and trig in delta_map:
        from dateutil.relativedelta import relativedelta
        curr = datetime.fromisoformat(cur_iso)
        rd = relativedelta(**delta_map[trig])
        target = curr + rd
        op = "$lte" if "prev" in trig else "$gte"
        sd = -1 if "prev" in trig else 1
        doc = fidas.collection.find_one(
            {"datetime": {op: target}},
            {"datetime":1,"_id":0},
            sort=[("datetime", sd)]
        )
        return doc["datetime"].isoformat() if doc else cur_iso

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
        df = fidas.fetch_time_series(dr, params, agg)
        if df.empty:
            return html.Div("No data available.", style={"color":"gray"})
        figs = fidas.create_time_series_figures(df, params)
        return html.Div([dcc.Graph(figure=fig) for fig in figs],
                        style={"display":"flex","flexDirection":"column","gap":"10px"})

    # Spectra
    if not cur_iso:
        return html.Div("No spectrum selected.", style={"color":"gray"})
    dt = datetime.fromisoformat(cur_iso)
    doc = fidas.fetch_spectrum_doc(dt)
    if not doc:
        return html.Div("Spectrum not found.", style={"color":"gray"})
    fig = fidas.create_spectrum_figure(doc["sizes"], doc["spectra"])
    return dcc.Graph(figure=fig, style={"height":"100%"})


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
