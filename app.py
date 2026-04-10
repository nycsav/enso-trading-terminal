"""
Enso Trading Terminal
Main Dash application with sidebar navigation.

Run: python app.py
Dashboard: http://localhost:8050
"""
import dash
from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime

from config import DASH_HOST, DASH_PORT, DASH_DEBUG, SYMBOLS
from modules.sr_engine import get_sr_summary, generate_signals
from modules.research import fetch_market_data, add_technical_indicators
from modules.api_client import PublicAPIClient
from modules.scheduled_tasks import SignalMonitor

# ── App Setup ─────────────────────────────────────────────────────────────────

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


# ── Sidebar ───────────────────────────────────────────────────────────────────

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


# ── Main Dashboard Content ───────────────────────────────────────────────────

def build_dashboard_content():
    """Build the main dashboard page with S/R signals and market overview."""
    return html.Div([
        html.H2("Market Overview", style={"marginBottom": "5px"}),
        html.P(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
               style={"color": "#666", "fontSize": "12px", "marginBottom": "20px"}),

        # Symbol selector
        html.Div([
            html.Label("Select Symbol"),
            dcc.Dropdown(
                id="main-symbol",
                options=[{"label": s, "value": s} for s in SYMBOLS],
                value="SPY",
                style={"width": "200px"},
            ),
            html.Button("Refresh", id="main-refresh-btn", n_clicks=0,
                        style={"marginLeft": "10px", "padding": "8px 16px",
                               "backgroundColor": "#4CAF50", "color": "white",
                               "border": "none", "borderRadius": "6px", "cursor": "pointer"}),
        ], style={"display": "flex", "alignItems": "end", "gap": "15px", "marginBottom": "25px"}),

        # Price chart with S/R levels
        dcc.Loading(
            dcc.Graph(id="main-price-chart", style={"height": "500px"}),
            type="circle",
        ),

        # Signals table
        html.Div(id="main-signals-table", style={"marginTop": "25px"}),
    ], style={"padding": "20px"})


# ── Layout ────────────────────────────────────────────────────────────────────

app.layout = html.Div([
    sidebar,
    html.Div([
        dash.page_container,
        html.Div(id="home-content"),
    ], style={"marginLeft": "220px", "padding": "30px",
              "backgroundColor": "#0a0a1a", "minHeight": "100vh", "color": "#eee"}),
    dcc.Interval(id="auto-refresh", interval=60000, n_intervals=0),
])


# ── Dashboard Callbacks ──────────────────────────────────────────────────────

@callback(
    Output("home-content", "children"),
    Input("auto-refresh", "n_intervals"),
)
def update_home(n):
    """Render home dashboard on load."""
    return build_dashboard_content()


@callback(
    [Output("main-price-chart", "figure"),
     Output("main-signals-table", "children")],
    [Input("main-refresh-btn", "n_clicks"),
     Input("main-symbol", "value")],
)
def update_main_chart(n_clicks, symbol):
    """Update the main price chart with S/R levels and signals."""
    if not symbol:
        empty = go.Figure()
        empty.update_layout(template="plotly_dark", paper_bgcolor="#1a1a2e")
        return empty, html.Div()

    df = fetch_market_data(symbol, period="6mo")
    if df.empty:
        empty = go.Figure()
        empty.update_layout(template="plotly_dark", paper_bgcolor="#1a1a2e",
                           title=f"No data for {symbol}")
        return empty, html.Div("Unable to fetch data.")

    df = add_technical_indicators(df)
    summary = get_sr_summary(df, symbol=symbol)

    # Build candlestick chart
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3], vertical_spacing=0.05)

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=symbol,
    ), row=1, col=1)

    # Add SMAs
    fig.add_trace(go.Scatter(
        x=df.index, y=df["SMA_20"], mode="lines",
        name="SMA 20", line=dict(color="#ffeb3b", width=1, dash="dot"),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["SMA_50"], mode="lines",
        name="SMA 50", line=dict(color="#2196F3", width=1, dash="dot"),
    ), row=1, col=1)

    # S/R lines
    for s in summary["supports"]:
        fig.add_hline(y=s["level_price"], line_dash="dash",
                      line_color="#4CAF50", opacity=0.5, row=1, col=1,
                      annotation_text=f"S: ${s['level_price']:.2f}")
    for r in summary["resistances"]:
        fig.add_hline(y=r["level_price"], line_dash="dash",
                      line_color="#f44336", opacity=0.5, row=1, col=1,
                      annotation_text=f"R: ${r['level_price']:.2f}")

    # Volume
    vol_colors = ["#4CAF50" if df["Close"].iloc[i] >= df["Open"].iloc[i]
                  else "#f44336" for i in range(len(df))]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"], name="Volume",
        marker_color=vol_colors, opacity=0.6,
    ), row=2, col=1)

    fig.update_layout(
        title=f"{symbol} — S/R Analysis",
        template="plotly_dark",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(x=0, y=1, bgcolor="rgba(0,0,0,0)"),
    )

    # Build signals table
    signals = summary["signals"]
    if signals:
        signal_rows = []
        for sig in signals[:10]:
            c = sig["confluence"]
            signal_rows.append(html.Tr([
                html.Td(sig["type"],
                        style={"color": "#4CAF50" if sig["type"] == "BUY_CALL" else "#f44336"}),
                html.Td(f"${sig['level_price']:.2f}"),
                html.Td(f"${sig['current_price']:.2f}"),
                html.Td(f"{c['distance_pct']:.2f}%"),
                html.Td(f"{c['confluence_total']:.1f}",
                        style={"fontWeight": "bold"}),
                html.Td(c["trend_direction"]),
            ]))

        signals_table = html.Div([
            html.H4("Active Signals", style={"marginBottom": "10px"}),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Signal"), html.Th("Level"),
                    html.Th("Price"), html.Th("Distance"),
                    html.Th("Confluence"), html.Th("Trend"),
                ])),
                html.Tbody(signal_rows),
            ], style={"width": "100%", "borderCollapse": "collapse",
                       "fontSize": "13px"}),
        ])
    else:
        signals_table = html.Div([
            html.H4("Active Signals"),
            html.P("No signals at current proximity threshold.",
                   style={"color": "#888"}),
        ])

    return fig, signals_table


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host=DASH_HOST, port=DASH_PORT, debug=DASH_DEBUG)
