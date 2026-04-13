"""
Backtest Dashboard Page
- Interactive controls for configuring backtests
- 7 Plotly charts for analyzing results
- Walk-forward optimization with overfit detection
- CSV export
"""
import dash
from dash import html, dcc, callback, Input, Output, State, dash_table, ctx
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import io
from datetime import datetime, timedelta

from modules.backtester import run_backtest, walk_forward_optimization, run_ml_backtest
from modules.strategy_engines import (
    run_iv_rv_backtest, run_event_vol_backtest, run_vrp_backtest,
    run_sr_vol_backtest, run_term_carry_backtest, run_cross_asset_backtest,
)
from modules.research import fetch_market_data
from modules.sr_engine import find_pivots
from config import SYMBOLS, DEFAULT_CAPITAL, DEFAULT_OPTION_EXPIRY_WEEKS

dash.register_page(__name__, path="/backtest", name="Backtest", icon="fa-chart-line")


# ── Layout ────────────────────────────────────────────────────────────────────

layout = html.Div([
    html.H2("Backtesting Engine", className="page-title"),
    html.P("Configure and run backtests with walk-forward optimization.",
           className="page-subtitle"),

    # Controls row
    html.Div([
        html.Div([
            html.Label("Symbols"),
            dcc.Dropdown(
                id="bt-symbols",
                options=[{"label": s, "value": s} for s in SYMBOLS],
                value=["NVDA"],
                multi=True,
                placeholder="Select symbols...",
            ),
        ], className="control-group", style={"flex": "2"}),

        html.Div([
            html.Label("Start Date"),
            dcc.DatePickerSingle(
                id="bt-start-date",
                date=(datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
            ),
        ], className="control-group"),

        html.Div([
            html.Label("End Date"),
            dcc.DatePickerSingle(
                id="bt-end-date",
                date=datetime.now().strftime("%Y-%m-%d"),
            ),
        ], className="control-group"),
    ], className="controls-row", style={"display": "flex", "gap": "20px", "marginBottom": "20px"}),

    # Parameter controls
    html.Div([
        html.Div([
            html.Label("Proximity Threshold (%)"),
            dcc.Slider(
                id="bt-proximity",
                min=0.5, max=3.0, step=0.1, value=1.5,
                marks={0.5: "0.5%", 1.0: "1%", 1.5: "1.5%", 2.0: "2%", 2.5: "2.5%", 3.0: "3%"},
                tooltip={"placement": "bottom", "always_visible": True},
            ),
        ], className="control-group", style={"flex": "2"}),

        html.Div([
            html.Label("Option Expiry (weeks)"),
            dcc.Dropdown(
                id="bt-expiry",
                options=[{"label": f"{w}w", "value": w} for w in range(1, 7)],
                value=DEFAULT_OPTION_EXPIRY_WEEKS,
            ),
        ], className="control-group"),

        html.Div([
            html.Label("Starting Capital ($)"),
            dcc.Input(
                id="bt-capital",
                type="number",
                value=DEFAULT_CAPITAL,
                min=1000, step=1000,
                style={"width": "100%"},
            ),
        ], className="control-group"),

        html.Div([
            html.Label("Position Size (%)"),
            dcc.Input(
                id="bt-position-size",
                type="number",
                value=5,
                min=1, max=25, step=1,
                style={"width": "100%"},
            ),
        ], className="control-group"),
    ], className="controls-row", style={"display": "flex", "gap": "20px", "marginBottom": "20px"}),

    # Action buttons
    html.Div([
                    dcc.Dropdown(
                id="bt-strategy",
                options=[
                    {"label": "S/R Mean Reversion", "value": "sr"},
                    {"label": "ML Gradient Boosted Trees", "value": "ml"},
                    {"label": "IV vs RV Gap Monitor", "value": "iv_rv"},
                    {"label": "Event Vol Strangle", "value": "event_vol"},
                    {"label": "Vol Risk Premium Harvest", "value": "vrp"},
                    {"label": "S/R + Vol Filter Overlay", "value": "sr_vol"},
                    {"label": "Term Structure Carry", "value": "term_carry"},
                    {"label": "Cross-Asset Momentum", "value": "cross_asset"},
                ],
                value="sr",
                clearable=False,
                style={"width": "280px", "marginRight": "10px", "display": "inline-block",
                       "verticalAlign": "middle"},
            ),
        html.Button("Run Backtest", id="bt-run-btn", n_clicks=0,
                     className="btn-primary",
                     style={"marginRight": "10px", "padding": "10px 24px",
                            "backgroundColor": "#4CAF50", "color": "white",
                            "border": "none", "borderRadius": "6px", "cursor": "pointer",
                            "fontSize": "14px", "fontWeight": "600"}),
        html.Button("Walk-Forward Optimization", id="bt-wfo-btn", n_clicks=0,
                     className="btn-secondary",
                     style={"marginRight": "10px", "padding": "10px 24px",
                            "backgroundColor": "#2196F3", "color": "white",
                            "border": "none", "borderRadius": "6px", "cursor": "pointer",
                            "fontSize": "14px", "fontWeight": "600"}),
        html.Button("Export CSV", id="bt-export-btn", n_clicks=0,
                     className="btn-outline",
                     style={"padding": "10px 24px",
                            "backgroundColor": "transparent", "color": "#ccc",
                            "border": "1px solid #555", "borderRadius": "6px", "cursor": "pointer",
                            "fontSize": "14px"}),
        dcc.Download(id="bt-download"),
    ], style={"marginBottom": "30px"}),

    # Loading indicator
    dcc.Loading(
        id="bt-loading",
        type="circle",
        children=[
            # Metrics summary cards
            html.Div(id="bt-metrics-cards"),

            # WFO results
            html.Div(id="bt-wfo-results"),

            # Charts grid (7 charts)
            html.Div([
                # Row 1: Equity curve (full width)
                html.Div([
                    dcc.Graph(id="bt-equity-chart", style={"height": "400px"}),
                ], style={"marginBottom": "20px"}),

                # Row 2: Price + S/R overlay | Win rate by symbol
                html.Div([
                    html.Div([
                        dcc.Graph(id="bt-price-sr-chart", style={"height": "400px"}),
                    ], style={"flex": "1"}),
                    html.Div([
                        dcc.Graph(id="bt-winrate-chart", style={"height": "400px"}),
                    ], style={"flex": "1"}),
                ], style={"display": "flex", "gap": "20px", "marginBottom": "20px"}),

                # Row 3: P&L histogram | Monthly heatmap
                html.Div([
                    html.Div([
                        dcc.Graph(id="bt-pnl-histogram", style={"height": "400px"}),
                    ], style={"flex": "1"}),
                    html.Div([
                        dcc.Graph(id="bt-monthly-heatmap", style={"height": "400px"}),
                    ], style={"flex": "1"}),
                ], style={"display": "flex", "gap": "20px", "marginBottom": "20px"}),

                # Row 4: Drawdown chart | Confluence scatter
                html.Div([
                    html.Div([
                        dcc.Graph(id="bt-drawdown-chart", style={"height": "400px"}),
                    ], style={"flex": "1"}),
                    html.Div([
                        dcc.Graph(id="bt-confluence-scatter", style={"height": "400px"}),
                    ], style={"flex": "1"}),
                ], style={"display": "flex", "gap": "20px", "marginBottom": "20px"}),
            ], id="bt-charts-container"),
        ],
    ),

    # Hidden store for results
    dcc.Store(id="bt-results-store"),
], style={"padding": "20px", "color": "#eee"})


# ── Callbacks ─────────────────────────────────────────────────────────────────

DARK_TEMPLATE = "plotly_dark"
CHART_BG = "rgba(0,0,0,0)"
PAPER_BG = "#1a1a2e"


@callback(
    [Output("bt-results-store", "data"),
     Output("bt-metrics-cards", "children"),
     Output("bt-equity-chart", "figure"),
     Output("bt-price-sr-chart", "figure"),
     Output("bt-winrate-chart", "figure"),
     Output("bt-pnl-histogram", "figure"),
     Output("bt-monthly-heatmap", "figure"),
     Output("bt-drawdown-chart", "figure"),
     Output("bt-confluence-scatter", "figure")],
    [Input("bt-run-btn", "n_clicks")],
    [State("bt-symbols", "value"),
     State("bt-start-date", "date"),
     State("bt-end-date", "date"),
     State("bt-proximity", "value"),
     State("bt-expiry", "value"),
     State("bt-capital", "value"),
     State("bt-position-size", "value"),
         State("bt-strategy", "value"),],
    prevent_initial_call=True,
)
def run_backtest_callback(n_clicks, symbols, start_date, end_date,
                          proximity, expiry, capital, position_size,
                                                  strategy):
    """Run backtest and update all charts."""
    if not symbols:
        empty = go.Figure()
        empty.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG)
        return ({}, html.Div("Select at least one symbol."),
                empty, empty, empty, empty, empty, empty, empty)

    import yfinance as yf

    all_trades = []
    all_equity = []
    symbol_metrics = {}

    for symbol in symbols:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)
        if df.empty or len(df) < 30:
            continue

        if strategy == "ml":
            result = run_ml_backtest(
                df, symbol=symbol,
                option_expiry_weeks=expiry,
                starting_capital=capital,
                position_size_pct=position_size,
            )
        elif strategy == "iv_rv":
            result = run_iv_rv_backtest(
                df, symbol=symbol,
                option_expiry_weeks=expiry,
                starting_capital=capital,
                position_size_pct=position_size,
            )
        elif strategy == "event_vol":
            result = run_event_vol_backtest(
                df, symbol=symbol,
                option_expiry_weeks=expiry,
                starting_capital=capital,
                position_size_pct=position_size,
            )
        elif strategy == "vrp":
            result = run_vrp_backtest(
                df, symbol=symbol,
                option_expiry_weeks=expiry,
                starting_capital=capital,
                position_size_pct=position_size,
            )
        elif strategy == "sr_vol":
            result = run_sr_vol_backtest(
                df, symbol=symbol,
                proximity_threshold_pct=proximity,
                option_expiry_weeks=expiry,
                starting_capital=capital,
                position_size_pct=position_size,
            )
        elif strategy == "term_carry":
            result = run_term_carry_backtest(
                df, symbol=symbol,
                option_expiry_weeks=expiry,
                starting_capital=capital,
                position_size_pct=position_size,
            )
        elif strategy == "cross_asset":
            result = run_cross_asset_backtest(
                df, symbol=symbol,
                option_expiry_weeks=expiry,
                starting_capital=capital,
                position_size_pct=position_size,
            )
        else:
            result = run_backtest(
                df, symbol=symbol,
                proximity_threshold_pct=proximity,
                option_expiry_weeks=expiry,
                starting_capital=capital,
                position_size_pct=position_size,
            )

        if "error" not in result:
            all_trades.extend(result["trades"])
            symbol_metrics[symbol] = result["metrics"]
            if not result["equity_curve"].empty:
                ec = result["equity_curve"].copy()
                ec["symbol"] = symbol
                all_equity.append(ec)

    if not all_trades:
        empty = go.Figure()
        empty.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                           title="No trades generated")
        return ({}, html.Div("No trades generated. Try adjusting parameters."),
                empty, empty, empty, empty, empty, empty, empty)

    # Serialize results for store
    store_data = {
        "trades": [
            {k: (v.isoformat() if hasattr(v, "isoformat") else v)
             for k, v in t.items() if k != "confluence"}
            for t in all_trades
        ],
        "metrics": symbol_metrics,
    }

    # ── Metric cards ──
    total_pnl = sum(t["pnl"] for t in all_trades)
    win_count = sum(1 for t in all_trades if t["pnl"] > 0)
    total_count = len(all_trades)
    win_rate = win_count / total_count * 100 if total_count > 0 else 0

    cards = html.Div([
        _metric_card("Total Trades", str(total_count), "#4CAF50"),
        _metric_card("Win Rate", f"{win_rate:.1f}%",
                     "#4CAF50" if win_rate > 50 else "#f44336"),
        _metric_card("Total P&L", f"${total_pnl:,.2f}",
                     "#4CAF50" if total_pnl > 0 else "#f44336"),
        _metric_card("Best Trade", f"${max(t['pnl'] for t in all_trades):,.2f}", "#4CAF50"),
        _metric_card("Worst Trade", f"${min(t['pnl'] for t in all_trades):,.2f}", "#f44336"),
        _metric_card("Calls / Puts",
                     f"{sum(1 for t in all_trades if t['type']=='BUY_CALL')} / "
                     f"{sum(1 for t in all_trades if t['type']=='BUY_PUT')}", "#2196F3"),
    ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginBottom": "30px"})

    # ── Chart 1: Equity Curve ──
    fig_equity = go.Figure()
    for ec_df in all_equity:
        sym = ec_df["symbol"].iloc[0]
        fig_equity.add_trace(go.Scatter(
            x=ec_df["date"], y=ec_df["equity"],
            mode="lines", name=sym,
            line=dict(width=2),
        ))
    fig_equity.update_layout(
        title="Equity Curve", template=DARK_TEMPLATE,
        paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG,
        xaxis_title="Date", yaxis_title="Portfolio Value ($)",
        yaxis_tickprefix="$",
    )

    # ── Chart 2: Price + S/R Overlay (first symbol) ──
    fig_price_sr = go.Figure()
    first_sym = symbols[0]
    ticker = yf.Ticker(first_sym)
    df_plot = ticker.history(start=start_date, end=end_date)
    if not df_plot.empty:
        fig_price_sr.add_trace(go.Candlestick(
            x=df_plot.index, open=df_plot["Open"], high=df_plot["High"],
            low=df_plot["Low"], close=df_plot["Close"], name=first_sym,
        ))
        levels = find_pivots(df_plot)
        for s in levels["support"]:
            fig_price_sr.add_hline(y=s["price"], line_dash="dash",
                                   line_color="#4CAF50", opacity=0.6,
                                   annotation_text=f"S: ${s['price']:.2f}")
        for r in levels["resistance"]:
            fig_price_sr.add_hline(y=r["price"], line_dash="dash",
                                   line_color="#f44336", opacity=0.6,
                                   annotation_text=f"R: ${r['price']:.2f}")
    fig_price_sr.update_layout(
        title=f"{first_sym} Price with S/R Levels", template=DARK_TEMPLATE,
        paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG,
        xaxis_rangeslider_visible=False,
    )

    # ── Chart 3: Win Rate by Symbol ──
    wr_data = []
    for sym, met in symbol_metrics.items():
        wr_data.append({"Symbol": sym, "Win Rate": met["win_rate"],
                        "Total Trades": met["total_trades"]})
    if wr_data:
        wr_df = pd.DataFrame(wr_data)
        fig_winrate = px.bar(
            wr_df, x="Symbol", y="Win Rate", color="Win Rate",
            color_continuous_scale=["#f44336", "#ffeb3b", "#4CAF50"],
            text="Total Trades",
        )
        fig_winrate.update_layout(
            title="Win Rate by Symbol", template=DARK_TEMPLATE,
            paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG,
            yaxis_title="Win Rate (%)",
        )
    else:
        fig_winrate = go.Figure()
        fig_winrate.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG)

    # ── Chart 4: P&L Histogram ──
    pnls = [t["pnl"] for t in all_trades]
    colors = ["#4CAF50" if p > 0 else "#f44336" for p in pnls]
    fig_pnl_hist = go.Figure(go.Histogram(
        x=pnls, nbinsx=30,
        marker_color="#2196F3", opacity=0.8,
    ))
    fig_pnl_hist.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.5)
    fig_pnl_hist.update_layout(
        title="P&L Distribution", template=DARK_TEMPLATE,
        paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG,
        xaxis_title="P&L ($)", yaxis_title="Count",
    )

    # ── Chart 5: Monthly P&L Heatmap ──
    monthly_data = {}
    for t in all_trades:
        if "exit_date" in t and t["exit_date"] is not None:
            dt = t["exit_date"]
            key = (dt.year, dt.month)
            monthly_data[key] = monthly_data.get(key, 0) + t["pnl"]

    if monthly_data:
        months_sorted = sorted(monthly_data.keys())
        month_labels = [f"{y}-{m:02d}" for y, m in months_sorted]
        month_values = [monthly_data[k] for k in months_sorted]
        fig_heatmap = go.Figure(go.Bar(
            x=month_labels, y=month_values,
            marker_color=["#4CAF50" if v > 0 else "#f44336" for v in month_values],
        ))
        fig_heatmap.update_layout(
            title="Monthly P&L", template=DARK_TEMPLATE,
            paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG,
            xaxis_title="Month", yaxis_title="P&L ($)", yaxis_tickprefix="$",
        )
    else:
        fig_heatmap = go.Figure()
        fig_heatmap.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG,
                                  title="Monthly P&L")

    # ── Chart 6: Drawdown Chart ──
    fig_drawdown = go.Figure()
    for ec_df in all_equity:
        sym = ec_df["symbol"].iloc[0]
        equities = ec_df["equity"].values
        peak = np.maximum.accumulate(equities)
        drawdown = (peak - equities) / peak * 100
        fig_drawdown.add_trace(go.Scatter(
            x=ec_df["date"], y=-drawdown,
            mode="lines", name=sym, fill="tozeroy",
            line=dict(width=1),
        ))
    fig_drawdown.update_layout(
        title="Drawdown", template=DARK_TEMPLATE,
        paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG,
        xaxis_title="Date", yaxis_title="Drawdown (%)",
        yaxis_ticksuffix="%",
    )

    # ── Chart 7: Confluence Scatter ──
    conf_data = []
    for t in all_trades:
        conf_data.append({
            "Confluence": t.get("confluence", 0),
            "P&L": t["pnl"],
            "Type": t["type"],
            "Symbol": t.get("symbol", ""),
        })
    if conf_data:
        conf_df = pd.DataFrame(conf_data)
        fig_confluence = px.scatter(
            conf_df, x="Confluence", y="P&L",
            color="Type", symbol="Symbol",
            color_discrete_map={"BUY_CALL": "#4CAF50", "BUY_PUT": "#f44336"},
        )
        fig_confluence.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
        fig_confluence.update_layout(
            title="Confluence Score vs P&L", template=DARK_TEMPLATE,
            paper_bgcolor=PAPER_BG, plot_bgcolor=CHART_BG,
            xaxis_title="Confluence Score", yaxis_title="P&L ($)",
            yaxis_tickprefix="$",
        )
    else:
        fig_confluence = go.Figure()
        fig_confluence.update_layout(template=DARK_TEMPLATE, paper_bgcolor=PAPER_BG)

    return (store_data, cards, fig_equity, fig_price_sr, fig_winrate,
            fig_pnl_hist, fig_heatmap, fig_drawdown, fig_confluence)


@callback(
    Output("bt-wfo-results", "children"),
    Input("bt-wfo-btn", "n_clicks"),
    [State("bt-symbols", "value"),
     State("bt-start-date", "date"),
     State("bt-end-date", "date"),
     State("bt-expiry", "value"),
     State("bt-capital", "value")],
    prevent_initial_call=True,
)
def run_wfo_callback(n_clicks, symbols, start_date, end_date, expiry, capital):
    """Run walk-forward optimization."""
    if not symbols:
        return html.Div("Select at least one symbol.")

    import yfinance as yf

    results = []
    for symbol in symbols:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)
        if df.empty or len(df) < 60:
            continue

        wfo = walk_forward_optimization(
            df, symbol=symbol,
            option_expiry_weeks=expiry or DEFAULT_OPTION_EXPIRY_WEEKS,
            starting_capital=capital or DEFAULT_CAPITAL,
        )

        if "error" not in wfo:
            results.append(wfo)

    if not results:
        return html.Div("Insufficient data for WFO. Need 60+ bars.",
                        style={"color": "#f44336", "padding": "20px"})

    # Build WFO results display
    wfo_cards = []
    for wfo in results:
        rating_color = {
            "ROBUST": "#4CAF50",
            "MODERATE": "#ffeb3b",
            "OVERFIT": "#f44336",
        }.get(wfo["overfit_rating"], "#ccc")

        wfo_cards.append(html.Div([
            html.H4(f"{wfo['symbol']} — Walk-Forward Results",
                    style={"marginBottom": "10px"}),
            html.Div([
                html.Span("Overfit Rating: ", style={"fontWeight": "bold"}),
                html.Span(wfo["overfit_rating"],
                          style={"color": rating_color, "fontWeight": "bold",
                                 "fontSize": "18px"}),
            ]),
            html.Div([
                html.P(f"Best Proximity: {wfo['best_proximity']}%"),
                html.P(f"Train Sharpe: {wfo['train_sharpe']:.2f} | Test Sharpe: {wfo['test_sharpe']:.2f}"),
                html.P(f"Train: {wfo['train_period']}"),
                html.P(f"Test: {wfo['test_period']}"),
                html.P(f"Test P&L: ${wfo['test_metrics']['total_pnl']:,.2f}"),
                html.P(f"Test Win Rate: {wfo['test_metrics']['win_rate']:.1f}%"),
            ], style={"fontSize": "13px", "lineHeight": "1.6"}),
        ], style={
            "backgroundColor": "#1a1a2e", "border": f"1px solid {rating_color}",
            "borderRadius": "8px", "padding": "20px", "marginBottom": "15px",
        }))

    return html.Div([
        html.H3("Walk-Forward Optimization Results",
                style={"marginBottom": "15px", "marginTop": "20px"}),
        *wfo_cards,
    ])


@callback(
    Output("bt-download", "data"),
    Input("bt-export-btn", "n_clicks"),
    State("bt-results-store", "data"),
    prevent_initial_call=True,
)
def export_csv(n_clicks, store_data):
    """Export backtest results to CSV."""
    if not store_data or "trades" not in store_data:
        return None

    df = pd.DataFrame(store_data["trades"])
    return dcc.send_data_frame(df.to_csv, "backtest_results.csv", index=False)


def _metric_card(title: str, value: str, color: str = "#4CAF50") -> html.Div:
    """Create a metric display card."""
    return html.Div([
        html.Div(title, style={"fontSize": "11px", "color": "#888",
                                "textTransform": "uppercase", "letterSpacing": "1px"}),
        html.Div(value, style={"fontSize": "24px", "fontWeight": "bold",
                                "color": color, "marginTop": "4px"}),
    ], style={
        "backgroundColor": "#16213e", "borderRadius": "8px",
        "padding": "16px 20px", "minWidth": "140px", "textAlign": "center",
    })
