import dash
import dash_bootstrap_components as dbc
from dash import html

dash.register_page(
    __name__,
    path_template="/stationdata/Fidas_Palas/<station_num>",
    title="Station Monitoring Dashboard"
)

layout = dbc.Container([
    html.Iframe(
        src="http://10.224.41.15",
        style={
            "width": "100%",
            "height": "100vh",
            "border": "none",
            "position": "fixed",
            "top": 0,
            "left": 0,
            "right": 0,
            "bottom": 0
        }
    )
], fluid=True, style={"padding": 0, "margin": 0, "height": "100vh"})
