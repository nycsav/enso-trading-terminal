"""
Enso Trading Terminal
Main Dash application with sidebar navigation.

Run: python app.py
Dashboard: http://localhost:8050
"""
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import config as cfg
from modules import api_client as api
from modules.scheduled_tasks import SignalMonitor

# -- App Setup
app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css",
    ],
    suppress_callback_exceptions=True,
    title="Enso Trading Terminal",
)

# Expose server for gunicorn deployment
server = app.server

# Initialize signal monitor
signal_monitor = SignalMonitor()

# Check API connection status
api_connected = api.check_connection()

C = cfg.COLORS

# -- Sidebar
sidebar = html.Div([
    html.Div([
        html.H3("ENSO", style={"fontWeight": "800", "letterSpacing": "3px",
                                "color": C["green"], "marginBottom": "2px"}),
        html.P("Trading Terminal", style={"fontSize": "11px", "color": C["text_muted"],
                                          "letterSpacing": "2px", "textTransform": "uppercase"}),
    ], style={"padding": "24px 20px", "borderBottom": f"1px solid {C['border']}"}),
    html.Nav([
        dcc.Link([
            html.I(className="fas fa-chart-area", style={"width": "20px"}),
            html.Span(" Dashboard"),
        ], href="/", className="nav-link",
           style={"display": "flex", "alignItems": "center", "gap": "10px",
                  "padding": "12px 20px", "color": C["text"], "textDecoration": "none",
                  "borderLeft": "3px solid transparent"}),
        dcc.Link([
            html.I(className="fas fa-wallet", style={"width": "20px"}),
            html.Span(" Portfolio"),
        ], href="/portfolio", className="nav-link",
           style={"display": "flex", "alignItems": "center", "gap": "10px",
                  "padding": "12px 20px", "color": C["text"], "textDecoration": "none",
                  "borderLeft": "3px solid transparent"}),
        dcc.Link([
            html.I(className="fas fa-chart-line", style={"width": "20px"}),
            html.Span(" Backtest"),
        ], href="/backtest", className="nav-link",
           style={"display": "flex", "alignItems": "center", "gap": "10px",
                  "padding": "12px 20px", "color": C["text"], "textDecoration": "none",
                  "borderLeft": "3px solid transparent"}),
        dcc.Link([
            html.I(className="fas fa-link", style={"width": "20px"}),
            html.Span(" Options Chain"),
        ], href="/options", className="nav-link",
           style={"display": "flex", "alignItems": "center", "gap": "10px",
                  "padding": "12px 20px", "color": C["text"], "textDecoration": "none",
                  "borderLeft": "3px solid transparent"}),
        dcc.Link([
            html.I(className="fas fa-exchange-alt", style={"width": "20px"}),
            html.Span(" Orders"),
        ], href="/orders", className="nav-link",
           style={"display": "flex", "alignItems": "center", "gap": "10px",
                  "padding": "12px 20px", "color": C["text"], "textDecoration": "none",
                  "borderLeft": "3px solid transparent"}),
    ], style={"marginTop": "10px"}),
    # Connection status
    html.Div([
        html.Div([
            html.Div(style={
                "width": "8px", "height": "8px", "borderRadius": "50%",
                "backgroundColor": C["green"] if api_connected else C["red"],
                "display": "inline-block", "marginRight": "8px",
            }),
            html.Span(
                "Public.com Connected" if api_connected else "No API Key",
                style={"fontSize": "11px", "color": C["text_muted"]},
            ),
        ], style={"display": "flex", "alignItems": "center"}),
    ], style={"position": "absolute", "bottom": "20px", "left": "20px"}),
], style={
    "width": "220px", "height": "100vh", "position": "fixed",
    "backgroundColor": C["bg"], "borderRight": f"1px solid {C['border']}",
    "zIndex": "100",
})

# -- Layout
app.layout = html.Div([
    sidebar,
    html.Div([
        dash.page_container,
    ], style={"marginLeft": "220px", "padding": "30px",
              "backgroundColor": C["bg"], "minHeight": "100vh", "color": C["text"]}),
])

# -- Run
if __name__ == "__main__":
    print("=" * 60)
    print("  ENSO TRADING TERMINAL")
    print("=" * 60)
    warnings = cfg.validate_config()
    for w in warnings:
        print(f"  {w}")
    if not warnings:
        print("  All config OK")
    print(f"  Refresh interval: {cfg.REFRESH_INTERVAL_MS // 1000}s")
    print("=" * 60)

    # Start signal monitor background thread
    try:
        signal_monitor.start()
        print("  Signal monitor started")
    except Exception as e:
        print(f"  Signal monitor failed to start: {e}")

    app.run(host=cfg.DASH_HOST, port=cfg.DASH_PORT, debug=cfg.DASH_DEBUG)
