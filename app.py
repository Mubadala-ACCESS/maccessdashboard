import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, clientside_callback, Input, Output
import threading
from station_status_monitor import check_and_update_status


# Initialize Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    use_pages=True,
    title="Station Monitoring Dashboard",
    suppress_callback_exceptions=True
)


app._favicon = "favicon.png" 


# Define main layout with navigation and page container
app.layout = dbc.Container(
    [
        dcc.Store(id="scroll-position", data=0),
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
            id="main-navbar",
            className="maccess-navbar navbar-visible",
        ),
        dcc.Location(id="url", refresh=False),
        dbc.Container(dash.page_container, className="dashboard-shell", fluid=True, style={"paddingTop": "0.5rem"}),
    ],
    fluid=True,
)


# Clientside callback for navbar hide/show on scroll
clientside_callback(
    """
    function(pathname) {
        if (typeof window === 'undefined') return window.dash_clientside.no_update;
        
        // Remove any existing scroll listener
        if (window.navbarScrollHandler) {
            window.removeEventListener('scroll', window.navbarScrollHandler);
        }
        
        let lastScroll = 0;
        let ticking = false;
        const navbar = document.getElementById('main-navbar');
        const scrollThreshold = 5;
        
        if (!navbar) return window.dash_clientside.no_update;
        
        // Optimized scroll handler using requestAnimationFrame
        window.navbarScrollHandler = function() {
            if (!ticking) {
                window.requestAnimationFrame(function() {
                    const currentScroll = window.pageYOffset || document.documentElement.scrollTop;
                    
                    // Don't hide navbar if at the very top
                    if (currentScroll < 80) {
                        navbar.classList.remove('navbar-hidden');
                        navbar.classList.add('navbar-visible');
                    } 
                    // Scrolling down - hide navbar
                    else if (currentScroll > lastScroll + scrollThreshold) {
                        navbar.classList.remove('navbar-visible');
                        navbar.classList.add('navbar-hidden');
                    } 
                    // Scrolling up - show navbar
                    else if (currentScroll < lastScroll - scrollThreshold) {
                        navbar.classList.remove('navbar-hidden');
                        navbar.classList.add('navbar-visible');
                    }
                    
                    lastScroll = currentScroll;
                    ticking = false;
                });
                ticking = true;
            }
        };
        
        // Add the event listener
        window.addEventListener('scroll', window.navbarScrollHandler, { passive: true });
        
        return window.dash_clientside.no_update;
    }
    """,
    Output("scroll-position", "data"),
    Input("url", "pathname"),
)


# Background monitor starter function
def start_station_monitor():
    """Start the station status monitoring in a background thread."""
    def monitor_loop():
        import time
        print("Station status monitor started in background thread...")
        while True:
            try:
                check_and_update_status()
            except Exception as e:
                print(f"Error in station monitor: {e}")
            time.sleep(300) 
    
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()


# Run the application
if __name__ == "__main__":
    # Start the background station monitor
    start_station_monitor()
    
    # Run the Dash app
    app.run(debug=True)
