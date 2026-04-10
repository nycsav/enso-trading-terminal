"""
Enso Trading Terminal
Main Dash application with sidebar navigation.

Run: python app.py
Dashboard: http://localhost:8050
"""
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from config import DASH_HOST, DASH_PORT, DASH_DEBUG
from modules.api_client import PublicAPIClient
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

# Initialize API client and signal monitor
api_client = PublicAPIClient()
signal_monitor = SignalMonitor()

# -- Sidebar
sidebar = html.Div([
    html.Div([
        html.H3("ENSO", style={"fontWeight": "800", "letterSpacing": "3px",
                                "color": "#4CAF50", "marginBottom": "2px"}),
        html.P("Trading Terminal", style={"fontSize": "11px", "color": "#666",
                                          "letterSpacing": "2px", "textTransform": "uppercase"}),
    ], style={"padding": "24px 20px", "borderBottom": "1px solid #2a2a3e"}),
    html.Nav([
        dcc.Link([
            html.I(className="fas fa-chart-area", style={"width": "20px"}),
            html.Span(" Dashboard"),
        ], href="/", className="nav-link",
           style={"display": "flex", "alignItems": "center", "gap": "10px",
                  "padding": "12px 20px", "color": "#ccc", "textDecoration": "none",
                  "borderLeft": "3px solid transparent"}),
        dcc.Link([
            html.I(className="fas fa-chart-line", style={"width": "20px"}),
            html.Span(" Backtest"),
        ], href="/backtest", className="nav-link",
           style={"display": "flex", "alignItems": "center", "gap": "10px",
                  "padding": "12px 20px", "color": "#ccc", "textDecoration": "none",
                  "borderLeft": "3px solid transparent"}),
    ], style={"marginTop": "10px"}),
    # Connection status
    html.Div([
        html.Div([
            html.Div(style={
                "width": "8px", "height": "8px", "borderRadius": "50%",
                "backgroundColor": "#4CAF50" if api_client.is_connected else "#f44336",
                "display": "inline-block", "marginRight": "8px",
            }),
            html.Span(
                "Public.com Connected" if api_client.is_connected else "No API Key",
                style={"fontSize": "11px", "color": "#888"},
            ),
        ], style={"display": "flex", "alignItems": "center"}),
    ], style={"position": "absolute", "bottom": "20px", "left": "20px"}),
], style={
    "width": "220px", "height": "100vh", "position": "fixed",
    "backgroundColor": "#0f0f1a", "borderRight": "1px solid #1a1a2e",
    "zIndex": "100",
})

# -- Layout
app.layout = html.Div([
    sidebar,
    html.Div([
        dash.page_container,
    ], style={"marginLeft": "220px", "padding": "30px",
              "backgroundColor": "#0a0a1a", "minHeight": "100vh", "color": "#eee"}),
])

# -- Run
if __name__ == "__main__":
    app.run(host=DASH_HOST, port=DASH_PORT, debug=DASH_DEBUG)
