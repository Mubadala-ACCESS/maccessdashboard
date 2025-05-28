import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, callback, State
import pandas as pd
from graphs.iot_graphs import IoTGraphs

# Register the page with a URL pattern for device_type and station_num
dash.register_page(__name__, path_template="/livedata/<device_type>/<station_num>", title="Station Monitoring Dashboard")

# Initialize IoTGraphs (assumes your MongoDB and data are set up as in your other modules)
iot_graphs = IoTGraphs()

def layout(station_num=None, device_type=None):
    """
    Layout for live data dashboard.
    This layout displays a fixed-top navbar with a logo and a container that
    will be populated with live data cards via a callback.
    """
    return dbc.Container([
        # Navbar (using the custom color and logo styling from your HTML)
        dbc.Navbar(
            dbc.Container(
                html.A(
                    html.Img(src="/assets/logo.png", style={"width": "200px"}, className="rounded-pill"),
                    href="/"
                )
            ),
            color="rgb(87,6,140)",
            dark=True,
            fixed="top"
        ),
        # Hidden store to save URL parameters (station number and device type)
        dcc.Store(id="station-info", data={"station_num": station_num, "device_type": device_type}),
        # Main content container (padding-top adjusted to avoid navbar overlap)
        dbc.Container(id="live-data-content", style={"paddingTop": "150px"}),
        # Interval component for live updates (update every 5 seconds)
        dcc.Interval(id="live-update-interval", interval=5000, n_intervals=0)
    ], fluid=True)

@callback(
    Output("live-data-content", "children"),
    Input("live-update-interval", "n_intervals"),
    State("station-info", "data")
)
def update_live_data(n_intervals, station_info):
    """
    Callback to update the live dashboard data.
    It fetches the available parameters for the station, gets recent data from the last 6 hours,
    and then for each parameter computes the current value, min, and max. These are then used to
    populate styled cards that mimic your HTML template -this is just an addition to the commments.
    """
    if not station_info or not station_info.get("station_num"):
        return html.Div("Invalid station information.", style={"color": "red"})
    try:
        station_num = int(station_info["station_num"])
    except ValueError:
        return html.Div("Invalid station number.", style={"color": "red"})
    
    # Get the available parameters and their labels
    parameters = iot_graphs.get_available_parameters(station_num)
    if not parameters:
        return html.Div("No parameters available for this station.", style={"color": "gray"})
    
    # Fetch recent data for the station (using a 6-hour window)
    selected_parameters = list(parameters.keys())
    df = iot_graphs.fetch_station_data(station_num, "6H", selected_parameters, split_view=False)
    if df.empty:
        return html.Div("No recent data available.", style={"color": "gray"})
    
    # Prepare a card for each parameter
    cards = []
    # Iterate over the parameters in the order provided by your available parameters mapping
    for param_key, param_label in parameters.items():
        # Extract the unit from the label if it exists (e.g., "Temperature (°C)")
        unit = ""
        if "(" in param_label and ")" in param_label:
            unit = param_label.split("(")[-1].split(")")[0]
        
        if param_key not in df.columns:
            continue

        # Get the most recent value for the parameter (by sorting on DateTime)
        try:
            latest_record = df.sort_values(by="DateTime").iloc[-1]
        except Exception:
            continue
        current_value = latest_record.get(param_key, "N/A")
        # Compute the min and max over the fetched period
        try:
            min_value = df[param_key].min()
            max_value = df[param_key].max()
        except Exception:
            min_value, max_value = "N/A", "N/A"
        
        # Set a generic description (you can adjust this as needed)
        description = "Latest reading"

        # Determine icon and color based on the parameter label
        if "Temperature" in param_label:
            icon = "fa fa-thermometer-half"
            color = "red"
        elif "Humidity" in param_label:
            icon = "fa fa-tint"
            color = "blue"
        elif "Pressure" in param_label:
            icon = "fa fa-compress"
            color = "green"
        elif "CO2" in param_label:
            icon = "fa fa-cloud"
            color = "orange"
        elif "PM1" in param_label or "PM2.5" in param_label or "PM10" in param_label:
            icon = "fa fa-smog"
            color = "brown"
        else:
            icon = "fa fa-info-circle"
            color = "purple"
        
        # Create a card for the parameter (using Bootstrap card styling to mimic your HTML)
        card = dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H6(param_label, className="order-card", style={"fontWeight": "bold"}),
                    html.H2([
                        html.I(className=f"{icon} f-left", style={"color": color, "marginRight": "5px"}),
                        html.Span(f"{current_value}{unit}")
                    ], className="text-right value-text", style={"color": color}),
                    html.P(description, className="value-text", style={"color": color}),
                    html.P(f"Min: {min_value}{unit} | Max: {max_value}{unit}",
                           className="min-max", style={"fontSize": "12px", "color": "rgba(0,0,0,0.6)"})
                ]),
                className="order-card",
                style={
                    "backgroundColor": "rgba(211,211,211,0.7)",
                    "borderRadius": "5px",
                    "boxShadow": "0 1px 3px rgba(0,0,0,0.2)",
                    "marginBottom": "30px"
                }
            ),
            xs=12, sm=6, md=4, lg=3, xl=3,
            style={"padding": "10px"}
        )
        cards.append(card)
    
    # Return the row of cards
    return dbc.Row(cards, justify="start")

# End of liveData.py
