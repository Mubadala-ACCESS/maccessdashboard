import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, callback_context
from graphs.buoy_graphs import BuoyGraphs

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
    dcc.Download(id="buoy-download-data")
], fluid=True)


# Callbacks

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
