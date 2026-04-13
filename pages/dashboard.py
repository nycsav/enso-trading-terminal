"""Dashboard Page - Main market overview with S/R signals and live quotes."""
import dash
from dash import html, dcc, callback, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import config as cfg
from modules.research import fetch_market_data, add_technical_indicators
from modules.sr_engine import get_sr_summary
from modules import api_client as api

dash.register_page(__name__, path="/", name="Dashboard", icon="fa-chart-area")

C = cfg.COLORS

layout = html.Div([
    html.H2("Market Overview", style={"marginBottom": "5px", "color": C["text"]}),
    html.P(id="dashboard-timestamp",
           style={"color": C["text_muted"], "fontSize": "12px", "marginBottom": "20px"}),
    html.Div([
        html.Div([
            html.Label("Select Symbol", style={"color": C["text_muted"], "fontSize": "12px"}),
            dcc.Dropdown(
                id="main-symbol",
                options=[{"label": s, "value": s} for s in cfg.SYMBOLS],
                value="SPY",
                style={"width": "200px"},
                className="dash-bootstrap",
            ),
        ]),
        html.Button("Refresh", id="main-refresh-btn", n_clicks=0,
                    style={"marginLeft": "10px", "padding": "8px 16px",
                           "backgroundColor": C["green"], "color": "#fff",
                           "border": "none", "borderRadius": "6px", "cursor": "pointer",
                           "alignSelf": "end"}),
    ], style={"display": "flex", "alignItems": "end", "gap": "15px", "marginBottom": "25px"}),

    # Live quote bar (from Public.com SDK if connected)
    html.Div(id="dashboard-live-quote", style={"marginBottom": "20px"}),

    dcc.Loading(
        dcc.Graph(id="main-price-chart", style={"height": "500px"}),
        type="circle",
    ),
    html.Div(id="main-signals-table", style={"marginTop": "25px"}),
], style={"padding": "20px", "color": C["text"]})


@callback(
    Output("dashboard-timestamp", "children"),
    Input("main-refresh-btn", "n_clicks"),
)
def update_timestamp(n):
    return f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"


@callback(
    Output("dashboard-live-quote", "children"),
    [Input("main-refresh-btn", "n_clicks"),
     Input("main-symbol", "value")],
)
def update_live_quote(n, symbol):
    if not symbol or not cfg.PUBLIC_COM_SECRET:
        return ""
    try:
        quotes = api.get_quotes([(symbol, "EQUITY")])
        if quotes and "error" not in quotes[0]:
            q = quotes[0]
            last = q.get("last")
            bid = q.get("bid")
            ask = q.get("ask")
            vol = q.get("volume")
            if last is not None:
                spread = (ask - bid) if bid and ask else None
                items = [
                    html.Span(f"Last: ${last:,.2f}",
                              style={"color": C["text"], "fontWeight": "700", "fontFamily": "monospace"}),
                ]
                if bid is not None:
                    items.append(html.Span(f"  Bid: ${bid:,.2f}", style={"color": C["green"], "fontFamily": "monospace"}))
                if ask is not None:
                    items.append(html.Span(f"  Ask: ${ask:,.2f}", style={"color": C["red"], "fontFamily": "monospace"}))
                if spread is not None:
                    items.append(html.Span(f"  Spread: ${spread:,.2f}", style={"color": C["text_muted"], "fontFamily": "monospace"}))
                if vol is not None:
                    items.append(html.Span(f"  Vol: {vol:,}", style={"color": C["text_muted"], "fontFamily": "monospace"}))

                return html.Div(items, style={
                    "display": "flex", "gap": "20px", "padding": "12px 16px",
                    "backgroundColor": C["surface"], "borderRadius": "8px",
                    "border": f"1px solid {C['border']}", "fontSize": "13px",
                })
    except Exception:
        pass
    return ""


@callback(
    [Output("main-price-chart", "figure"),
     Output("main-signals-table", "children")],
    [Input("main-refresh-btn", "n_clicks"),
     Input("main-symbol", "value")],
)
def update_main_chart(n_clicks, symbol):
    if not symbol:
        empty = go.Figure()
        empty.update_layout(template="plotly_dark", paper_bgcolor=C["bg"])
        return empty, html.Div()

    df = fetch_market_data(symbol, period="6mo")
    if df.empty:
        empty = go.Figure()
        empty.update_layout(template="plotly_dark", paper_bgcolor=C["bg"],
                            title=f"No data for {symbol}")
        return empty, html.Div("Unable to fetch data.", style={"color": C["text_muted"]})

    df = add_technical_indicators(df)
    summary = get_sr_summary(df, symbol=symbol)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3], vertical_spacing=0.05)

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=symbol,
        increasing=dict(line=dict(color=C["green"]), fillcolor=C["green"]),
        decreasing=dict(line=dict(color=C["red"]), fillcolor=C["red"]),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["SMA_20"], mode="lines",
        name="SMA 20", line=dict(color=C["yellow"], width=1, dash="dot"),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["SMA_50"], mode="lines",
        name="SMA 50", line=dict(color=C["blue"], width=1, dash="dot"),
    ), row=1, col=1)

    for s in summary["supports"]:
        fig.add_hline(y=s["level_price"], line_dash="dash",
                      line_color=C["green"], opacity=0.5, row=1, col=1,
                      annotation_text=f"S: ${s['level_price']:.2f}",
                      annotation_font_color=C["green"])

    for r in summary["resistances"]:
        fig.add_hline(y=r["level_price"], line_dash="dash",
                      line_color=C["red"], opacity=0.5, row=1, col=1,
                      annotation_text=f"R: ${r['level_price']:.2f}",
                      annotation_font_color=C["red"])

    vol_colors = [C["green"] if df["Close"].iloc[i] >= df["Open"].iloc[i]
                  else C["red"] for i in range(len(df))]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"], name="Volume",
        marker_color=vol_colors, opacity=0.6,
    ), row=2, col=1)

    fig.update_layout(
        title=f"{symbol} — S/R Analysis",
        template="plotly_dark",
        paper_bgcolor=C["bg"],
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(x=0, y=1, bgcolor="rgba(0,0,0,0)", font=dict(color=C["text"])),
        font=dict(color=C["text"]),
    )

    # Signals table
    signals = summary["signals"]
    if signals:
        signal_rows = []
        for sig in signals[:10]:
            c = sig["confluence"]
            sig_color = C["green"] if sig["type"] == "BUY_CALL" else C["red"]
            signal_rows.append(html.Tr([
                html.Td(sig["type"], style={"color": sig_color}),
                html.Td(f"${sig['level_price']:.2f}"),
                html.Td(f"${sig['current_price']:.2f}"),
                html.Td(f"{c['distance_pct']:.2f}%"),
                html.Td(f"{c['confluence_total']:.1f}", style={"fontWeight": "bold"}),
                html.Td(c["trend_direction"]),
            ]))

        header_style = {"padding": "8px 12px", "color": C["text_muted"], "fontSize": "12px",
                        "borderBottom": f"1px solid {C['border']}"}
        cell_style = {"padding": "8px 12px", "fontSize": "13px", "fontFamily": "monospace",
                      "borderBottom": f"1px solid {C['border']}"}

        signals_table = html.Div([
            html.H4("Active Signals", style={"marginBottom": "10px", "color": C["text"]}),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Signal", style=header_style),
                    html.Th("Level", style=header_style),
                    html.Th("Price", style=header_style),
                    html.Th("Distance", style=header_style),
                    html.Th("Confluence", style=header_style),
                    html.Th("Trend", style=header_style),
                ])),
                html.Tbody(signal_rows),
            ], style={"width": "100%", "borderCollapse": "collapse",
                      "backgroundColor": C["surface"], "borderRadius": "8px"}),
        ])
    else:
        signals_table = html.Div([
            html.H4("Active Signals", style={"color": C["text"]}),
            html.P("No signals at current proximity threshold.",
                   style={"color": C["text_muted"]}),
        ])

    return fig, signals_table
