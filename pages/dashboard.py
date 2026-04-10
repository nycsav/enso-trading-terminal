"""Dashboard Page - Main market overview with S/R signals."""
import dash
from dash import html, dcc, callback, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from config import SYMBOLS
from modules.research import fetch_market_data, add_technical_indicators
from modules.sr_engine import get_sr_summary

dash.register_page(__name__, path="/", name="Dashboard", icon="fa-chart-area")

layout = html.Div([
    html.H2("Market Overview", style={"marginBottom": "5px"}),
    html.P(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
           style={"color": "#666", "fontSize": "12px", "marginBottom": "20px"}),
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
    dcc.Loading(
        dcc.Graph(id="main-price-chart", style={"height": "500px"}),
        type="circle",
    ),
    html.Div(id="main-signals-table", style={"marginTop": "25px"}),
], style={"padding": "20px", "color": "#eee"})


@callback(
    [Output("main-price-chart", "figure"),
     Output("main-signals-table", "children")],
    [Input("main-refresh-btn", "n_clicks"),
     Input("main-symbol", "value")],
)
def update_main_chart(n_clicks, symbol):
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
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=symbol,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["SMA_20"], mode="lines",
        name="SMA 20", line=dict(color="#ffeb3b", width=1, dash="dot"),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["SMA_50"], mode="lines",
        name="SMA 50", line=dict(color="#2196F3", width=1, dash="dot"),
    ), row=1, col=1)
    for s in summary["supports"]:
        fig.add_hline(y=s["level_price"], line_dash="dash",
                      line_color="#4CAF50", opacity=0.5, row=1, col=1,
                      annotation_text=f"S: ${s['level_price']:.2f}")
    for r in summary["resistances"]:
        fig.add_hline(y=r["level_price"], line_dash="dash",
                      line_color="#f44336", opacity=0.5, row=1, col=1,
                      annotation_text=f"R: ${r['level_price']:.2f}")
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
