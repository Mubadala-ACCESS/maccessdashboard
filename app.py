import dash
import dash_bootstrap_components as dbc
from dash import html, dcc

# Initialize Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    use_pages=True,
    title="Station Monitoring Dashboard",
)

app._favicon = "favicon.png" 

# Define main layout with navigation and page container
app.layout = dbc.Container(
    [
        dbc.Navbar(
            dbc.Container(
                [
                    html.A(
                        html.Img(
                            src="/assets/maccess-logo.png",
                            title="Back to Map",
                        ),
                        href="/",
                        target="_self",
                        className="navbar-brand",
                    ),
                ],
                fluid=True,
            ),
            dark=True,
            sticky="top",
            className="maccess-navbar",
        ),
        dcc.Location(id="url", refresh=False),
        dbc.Container(dash.page_container, className="py-4", fluid=True),
    ],
    fluid=True,
)


# Run the application
if __name__ == "__main__":
    app.run(debug=True)
