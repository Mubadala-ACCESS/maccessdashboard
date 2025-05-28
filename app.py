import dash
import dash_bootstrap_components as dbc
from dash import html, dcc

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], use_pages=True, title="Station Monitoring Dashboard")

app._favicon = "favicon.png" 

# Define main layout with navigation and page container
app.layout = dbc.Container([
    dbc.NavbarSimple(
        brand=html.A(
            html.Img(
                src="/assets/maccess-logo.png",
                style={"height": "60px"},
                title="Back to Map"  
            ),
            href="/",
            target= "_self"              # ← clicking the image goes home
        ),
        color="purple",
        dark=True,
        style={"height": "80px"}
    ),
    dcc.Location(id="url", refresh=False),
    dash.page_container
], fluid=True)


# Run the application
if __name__ == "__main__":
    app.run_server(debug=True)
