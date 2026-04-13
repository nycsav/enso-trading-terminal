"""Portfolio Page — Live brokerage data from Public.com SDK."""
import dash
from dash import html, dcc, callback, Input, Output, State, dash_table, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import config as cfg
from modules import api_client as api

dash.register_page(__name__, path="/portfolio", name="Portfolio", icon="fa-wallet")

C = cfg.COLORS

HEADER_STYLE = {
    "color": C["text"],
    "fontWeight": "600",
    "fontSize": "13px",
    "marginBottom": "8px",
    "textTransform": "uppercase",
    "letterSpacing": "0.5px",
}

TABLE_HEADER_STYLE = {
    "backgroundColor": C["surface_alt"],
    "color": C["text"],
    "fontWeight": "600",
    "fontSize": "12px",
    "border": f"1px solid {C['border']}",
    "padding": "8px",
}

TABLE_CELL_STYLE = {
    "backgroundColor": C["surface"],
    "color": C["text"],
    "border": f"1px solid {C['border']}",
    "padding": "6px 10px",
    "fontSize": "12px",
    "fontFamily": "monospace",
}

CONDITIONAL_STYLES = [
    {"if": {"filter_query": "{daily_gain_value} > 0", "column_id": "daily_gain_value"}, "color": C["green"]},
    {"if": {"filter_query": "{daily_gain_value} < 0", "column_id": "daily_gain_value"}, "color": C["red"]},
    {"if": {"filter_query": "{daily_gain_pct} > 0", "column_id": "daily_gain_pct"}, "color": C["green"]},
    {"if": {"filter_query": "{daily_gain_pct} < 0", "column_id": "daily_gain_pct"}, "color": C["red"]},
    {"if": {"filter_query": "{total_gain_value} > 0", "column_id": "total_gain_value"}, "color": C["green"]},
    {"if": {"filter_query": "{total_gain_value} < 0", "column_id": "total_gain_value"}, "color": C["red"]},
    {"if": {"filter_query": "{total_gain_pct} > 0", "column_id": "total_gain_pct"}, "color": C["green"]},
    {"if": {"filter_query": "{total_gain_pct} < 0", "column_id": "total_gain_pct"}, "color": C["red"]},
]


def make_kpi_card(title, value, delta=None, color=None, prefix="$"):
    """Create a KPI metric card."""
    color = color or C["text"]
    if isinstance(value, (int, float)):
        formatted = f"{prefix}{value:,.2f}" if prefix else f"{value:,.0f}"
    else:
        formatted = str(value)

    delta_el = ""
    if delta is not None and isinstance(delta, (int, float)):
        d_color = C["green"] if delta >= 0 else C["red"]
        d_sign = "+" if delta >= 0 else ""
        delta_el = html.Div(
            f"{d_sign}{delta:,.2f}", style={"color": d_color, "fontSize": "11px", "fontFamily": "monospace"}
        )

    return html.Div([
        html.Div(title, style={"color": C["text_muted"], "fontSize": "11px", "textTransform": "uppercase",
                                "letterSpacing": "0.5px", "marginBottom": "4px"}),
        html.Div(formatted, style={"color": color, "fontSize": "20px", "fontWeight": "700",
                                    "fontFamily": "monospace"}),
        delta_el,
    ], style={"padding": "16px", "backgroundColor": C["surface"], "borderRadius": "8px",
              "border": f"1px solid {C['border']}"})


# -- Layout
layout = html.Div([
    html.Div([
        html.H2("Portfolio", style={"marginBottom": "5px", "color": C["text"]}),
        html.P("Live brokerage data from Public.com",
               style={"color": C["text_muted"], "fontSize": "12px", "marginBottom": "20px"}),
    ]),
    html.Div([
        html.Label("Account", style={"color": C["text_muted"], "fontSize": "12px"}),
        dcc.Dropdown(
            id="portfolio-account-selector",
            options=[
                {"label": f"Brokerage ({cfg.ACCOUNTS['brokerage']})", "value": cfg.ACCOUNTS["brokerage"]},
                {"label": f"Bond ({cfg.ACCOUNTS['bond']})", "value": cfg.ACCOUNTS["bond"]},
                {"label": f"High Yield ({cfg.ACCOUNTS['high_yield']})", "value": cfg.ACCOUNTS["high_yield"]},
            ],
            value=cfg.PUBLIC_COM_ACCOUNT_ID,
            style={"width": "300px"},
            className="dash-bootstrap",
        ),
        html.Button("Refresh", id="portfolio-refresh-btn", n_clicks=0,
                    style={"marginLeft": "10px", "padding": "8px 20px",
                           "backgroundColor": C["green"], "color": "#fff",
                           "border": "none", "borderRadius": "6px", "cursor": "pointer"}),
    ], style={"display": "flex", "alignItems": "end", "gap": "15px", "marginBottom": "25px"}),

    dcc.Loading([
        html.Div(id="portfolio-kpis"),
        html.Div(id="portfolio-equity-chart", style={"marginTop": "20px"}),
        html.Div(id="portfolio-positions-table", style={"marginTop": "20px"}),
        html.Div(id="portfolio-orders-table", style={"marginTop": "20px"}),
    ], type="circle"),
], style={"padding": "20px", "color": C["text"]})


@callback(
    [
        Output("portfolio-kpis", "children"),
        Output("portfolio-equity-chart", "children"),
        Output("portfolio-positions-table", "children"),
        Output("portfolio-orders-table", "children"),
    ],
    [
        Input("portfolio-refresh-btn", "n_clicks"),
        Input("portfolio-account-selector", "value"),
    ],
)
def update_portfolio(n_clicks, account_id):
    if not account_id:
        return no_update, no_update, no_update, no_update

    if not cfg.PUBLIC_COM_SECRET:
        msg = html.Div([
            html.Div("API Key Required", style={**HEADER_STYLE, "color": C["red"]}),
            html.P("Set PUBLIC_COM_SECRET env var to connect.", style={"color": C["text_muted"], "fontSize": "13px"}),
        ])
        return msg, "", "", ""

    data = api.get_portfolio(account_id)
    if "error" in data and not data.get("positions"):
        msg = html.Div([
            html.Div("API Error", style={**HEADER_STYLE, "color": C["red"]}),
            html.P(data["error"], style={"color": C["text_muted"], "fontSize": "13px"}),
        ])
        return msg, "", "", ""

    # KPIs
    total_equity = data.get("total_equity", 0)
    buying_power = data.get("buying_power", 0)
    positions = data.get("positions", [])
    daily_pnl = sum(p.get("daily_gain_value", 0) for p in positions)
    total_pnl = sum(p.get("total_gain_value", 0) for p in positions)

    kpis = dbc.Row([
        dbc.Col(make_kpi_card("Total Equity", total_equity), width=3),
        dbc.Col(make_kpi_card("Buying Power", buying_power, color=C["blue"]), width=3),
        dbc.Col(make_kpi_card("Daily P&L", daily_pnl, delta=daily_pnl), width=3),
        dbc.Col(make_kpi_card("Total P&L", total_pnl, delta=total_pnl), width=3),
    ])

    # Equity breakdown pie chart
    eq_items = data.get("equity", [])
    if eq_items:
        fig = go.Figure(go.Pie(
            labels=[e["type"].replace("_", " ").title() for e in eq_items],
            values=[e["value"] for e in eq_items],
            hole=0.6,
            marker=dict(colors=[C["blue"], C["green"], C["purple"], C["yellow"], C["orange"]]),
            textinfo="label+percent",
            textfont=dict(size=11, color=C["text"]),
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=30, b=20), height=250,
            font=dict(color=C["text"]),
            legend=dict(font=dict(size=10, color=C["text"])),
            title=dict(text="Equity Breakdown", font=dict(size=13, color=C["text"])),
        )
        eq_chart = dcc.Graph(figure=fig, config={"displayModeBar": False})
    else:
        eq_chart = html.Div("No equity data", style={"color": C["text_muted"], "padding": "20px"})

    # Positions table
    if positions:
        pos_df = pd.DataFrame(positions)
        cols_display = ["symbol", "name", "type", "quantity", "last_price", "current_value",
                        "pct_of_portfolio", "daily_gain_value", "daily_gain_pct",
                        "total_gain_value", "total_gain_pct", "total_cost"]
        available_cols = [c for c in cols_display if c in pos_df.columns]
        pos_table = html.Div([
            html.Div("Positions", style=HEADER_STYLE),
            dash_table.DataTable(
                data=pos_df[available_cols].to_dict("records"),
                columns=[{"name": c.replace("_", " ").title(), "id": c} for c in available_cols],
                style_table={"overflowX": "auto"},
                style_header=TABLE_HEADER_STYLE,
                style_cell=TABLE_CELL_STYLE,
                style_data_conditional=CONDITIONAL_STYLES,
                sort_action="native",
                filter_action="native",
                page_size=20,
            ),
        ])
    else:
        pos_table = html.Div("No positions", style={"color": C["text_muted"], "padding": "20px"})

    # Active orders table
    orders = data.get("orders", [])
    if orders:
        ord_df = pd.DataFrame(orders)
        ord_cols = ["symbol", "side", "order_type", "status", "quantity", "limit_price", "filled_quantity", "created_at"]
        avail_ord = [c for c in ord_cols if c in ord_df.columns]
        ord_table = html.Div([
            html.Div("Active Orders", style=HEADER_STYLE),
            dash_table.DataTable(
                data=ord_df[avail_ord].to_dict("records"),
                columns=[{"name": c.replace("_", " ").title(), "id": c} for c in avail_ord],
                style_table={"overflowX": "auto"},
                style_header=TABLE_HEADER_STYLE,
                style_cell=TABLE_CELL_STYLE,
                sort_action="native",
                page_size=10,
            ),
        ])
    else:
        ord_table = html.Div("No active orders", style={"color": C["text_muted"], "padding": "20px"})

    return kpis, eq_chart, pos_table, ord_table
