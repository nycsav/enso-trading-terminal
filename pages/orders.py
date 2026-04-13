"""Orders Page — Place and manage orders via Public.com SDK."""
import dash
from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import config as cfg
from modules import api_client as api

dash.register_page(__name__, path="/orders", name="Orders", icon="fa-exchange-alt")

C = cfg.COLORS

HEADER_STYLE = {
    "color": C["text"],
    "fontWeight": "600",
    "fontSize": "13px",
    "marginBottom": "8px",
    "textTransform": "uppercase",
    "letterSpacing": "0.5px",
}


layout = html.Div([
    html.H2("Order Management", style={"marginBottom": "5px", "color": C["text"]}),
    html.P("Preflight and place orders via Public.com",
           style={"color": C["text_muted"], "fontSize": "12px", "marginBottom": "25px"}),

    dbc.Row([
        dbc.Col([
            html.Div("Order Entry", style=HEADER_STYLE),
            html.Div([
                html.Div([
                    html.Label("Symbol", style={"color": C["text_muted"], "fontSize": "11px"}),
                    dcc.Input(id="order-symbol", type="text", placeholder="AAPL",
                              style={"width": "100%", "padding": "8px", "backgroundColor": C["surface"],
                                     "color": C["text"], "border": f"1px solid {C['border']}", "borderRadius": "4px"}),
                ], style={"marginBottom": "10px"}),
                html.Div([
                    html.Label("Type", style={"color": C["text_muted"], "fontSize": "11px"}),
                    dcc.Dropdown(id="order-inst-type", options=[
                        {"label": "Equity", "value": "EQUITY"},
                        {"label": "Option", "value": "OPTION"},
                        {"label": "Crypto", "value": "CRYPTO"},
                    ], value="EQUITY", className="dash-bootstrap"),
                ], style={"marginBottom": "10px"}),
                html.Div([
                    html.Label("Side", style={"color": C["text_muted"], "fontSize": "11px"}),
                    dcc.Dropdown(id="order-side", options=[
                        {"label": "Buy", "value": "BUY"},
                        {"label": "Sell", "value": "SELL"},
                    ], value="BUY", className="dash-bootstrap"),
                ], style={"marginBottom": "10px"}),
                html.Div([
                    html.Label("Order Type", style={"color": C["text_muted"], "fontSize": "11px"}),
                    dcc.Dropdown(id="order-type", options=[
                        {"label": "Market", "value": "MARKET"},
                        {"label": "Limit", "value": "LIMIT"},
                        {"label": "Stop", "value": "STOP"},
                        {"label": "Stop Limit", "value": "STOP_LIMIT"},
                    ], value="MARKET", className="dash-bootstrap"),
                ], style={"marginBottom": "10px"}),
                html.Div([
                    html.Label("Quantity", style={"color": C["text_muted"], "fontSize": "11px"}),
                    dcc.Input(id="order-qty", type="number", placeholder="10",
                              style={"width": "100%", "padding": "8px", "backgroundColor": C["surface"],
                                     "color": C["text"], "border": f"1px solid {C['border']}", "borderRadius": "4px"}),
                ], style={"marginBottom": "10px"}),
                html.Div([
                    html.Label("Limit Price (if applicable)", style={"color": C["text_muted"], "fontSize": "11px"}),
                    dcc.Input(id="order-limit-price", type="number", placeholder="0.00",
                              style={"width": "100%", "padding": "8px", "backgroundColor": C["surface"],
                                     "color": C["text"], "border": f"1px solid {C['border']}", "borderRadius": "4px"}),
                ], style={"marginBottom": "10px"}),
                html.Div([
                    html.Label("Stop Price (if applicable)", style={"color": C["text_muted"], "fontSize": "11px"}),
                    dcc.Input(id="order-stop-price", type="number", placeholder="0.00",
                              style={"width": "100%", "padding": "8px", "backgroundColor": C["surface"],
                                     "color": C["text"], "border": f"1px solid {C['border']}", "borderRadius": "4px"}),
                ], style={"marginBottom": "15px"}),
                html.Div([
                    html.Button("Preflight", id="preflight-btn", n_clicks=0,
                                style={"padding": "10px 24px", "backgroundColor": C["blue"], "color": "#fff",
                                       "border": "none", "borderRadius": "6px", "cursor": "pointer",
                                       "marginRight": "10px"}),
                    html.Button("Place Order", id="order-submit-btn", n_clicks=0,
                                style={"padding": "10px 24px", "backgroundColor": C["green"], "color": "#fff",
                                       "border": "none", "borderRadius": "6px", "cursor": "pointer"}),
                ]),
            ], style={"padding": "20px", "backgroundColor": C["surface"],
                      "borderRadius": "8px", "border": f"1px solid {C['border']}"}),
        ], width=5),
        dbc.Col([
            html.Div("Results", style=HEADER_STYLE),
            html.Div(id="preflight-result", style={"marginBottom": "20px"}),
            html.Div(id="order-submit-result"),
        ], width=7),
    ]),
], style={"padding": "20px", "color": C["text"]})


@callback(
    Output("preflight-result", "children"),
    Input("preflight-btn", "n_clicks"),
    [State("order-symbol", "value"), State("order-inst-type", "value"),
     State("order-side", "value"), State("order-type", "value"),
     State("order-qty", "value"), State("order-limit-price", "value"),
     State("order-stop-price", "value")],
    prevent_initial_call=True,
)
def run_preflight(n, symbol, inst_type, side, order_type, qty, limit_p, stop_p):
    if not symbol or not qty:
        return html.Div("Enter symbol and quantity", style={"color": C["text_muted"], "padding": "12px"})
    if not cfg.PUBLIC_COM_SECRET:
        return html.Div("Set PUBLIC_COM_SECRET first", style={"color": C["red"], "padding": "12px"})

    result = api.preflight_order(
        symbol=symbol.upper().strip(), inst_type=inst_type, side=side, order_type=order_type,
        quantity=float(qty),
        limit_price=float(limit_p) if limit_p else None,
        stop_price=float(stop_p) if stop_p else None,
    )
    if "error" in result:
        return html.Div(f"Error: {result['error']}", style={"color": C["red"], "padding": "12px"})

    return html.Div([
        html.Div("Preflight Result", style={**HEADER_STYLE, "color": C["blue"]}),
        html.Div(f"Order Value: {result.get('order_value', '-')}", style={"color": C["text"], "fontSize": "13px"}),
        html.Div(f"Estimated Cost: {result.get('estimated_cost', '-')}", style={"color": C["text"], "fontSize": "13px"}),
        html.Div(f"Commission: {result.get('estimated_commission', '-')}", style={"color": C["text"], "fontSize": "13px"}),
        html.Div(f"Buying Power Required: {result.get('buying_power_requirement', '-')}", style={"color": C["text"], "fontSize": "13px"}),
    ], style={"padding": "16px", "backgroundColor": C["surface"],
              "borderRadius": "8px", "border": f"1px solid {C['border']}"})


@callback(
    Output("order-submit-result", "children"),
    Input("order-submit-btn", "n_clicks"),
    [State("order-symbol", "value"), State("order-inst-type", "value"),
     State("order-side", "value"), State("order-type", "value"),
     State("order-qty", "value"), State("order-limit-price", "value"),
     State("order-stop-price", "value")],
    prevent_initial_call=True,
)
def submit_order(n, symbol, inst_type, side, order_type, qty, limit_p, stop_p):
    if not symbol or not qty:
        return html.Div("Enter symbol and quantity", style={"color": C["text_muted"], "padding": "12px"})
    if not cfg.PUBLIC_COM_SECRET:
        return html.Div("Set PUBLIC_COM_SECRET first", style={"color": C["red"], "padding": "12px"})

    result = api.place_order(
        symbol=symbol.upper().strip(), inst_type=inst_type, side=side, order_type=order_type,
        quantity=float(qty),
        limit_price=float(limit_p) if limit_p else None,
        stop_price=float(stop_p) if stop_p else None,
    )
    if "error" in result:
        return html.Div(f"Error: {result['error']}", style={"color": C["red"], "padding": "12px"})

    return html.Div([
        html.Div("Order Submitted", style={**HEADER_STYLE, "color": C["green"]}),
        html.Div(f"Order ID: {result.get('order_id', '-')}", style={"color": C["text"], "fontSize": "13px"}),
        html.P("Order placement is async. Check portfolio for status.",
               style={"color": C["text_muted"], "fontSize": "11px", "marginTop": "8px"}),
    ], style={"padding": "16px", "backgroundColor": C["surface"],
              "borderRadius": "8px", "border": f"1px solid {C['border']}"})
