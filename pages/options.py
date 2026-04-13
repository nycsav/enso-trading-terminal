"""Options Chain Page — Live options data from Public.com SDK."""
import dash
from dash import html, dcc, callback, Input, Output, State, dash_table, no_update
import dash_bootstrap_components as dbc
import pandas as pd
import config as cfg
from modules import api_client as api

dash.register_page(__name__, path="/options", name="Options Chain", icon="fa-link")

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
}

TABLE_CELL_STYLE = {
    "backgroundColor": C["surface"],
    "color": C["text"],
    "border": f"1px solid {C['border']}",
    "padding": "5px 8px",
    "fontSize": "12px",
    "fontFamily": "monospace",
}


layout = html.Div([
    html.H2("Options Chain", style={"marginBottom": "5px", "color": C["text"]}),
    html.P("Live options data from Public.com",
           style={"color": C["text_muted"], "fontSize": "12px", "marginBottom": "20px"}),

    html.Div([
        html.Div([
            html.Label("Symbol", style={"color": C["text_muted"], "fontSize": "12px"}),
            dcc.Input(id="options-symbol", type="text", value="NVDA", placeholder="e.g. AAPL",
                      style={"width": "120px", "padding": "8px", "backgroundColor": C["surface"],
                             "color": C["text"], "border": f"1px solid {C['border']}", "borderRadius": "4px"}),
        ]),
        html.Button("Load Expirations", id="options-load-expiry-btn", n_clicks=0,
                    style={"padding": "8px 16px", "backgroundColor": C["blue"], "color": "#fff",
                           "border": "none", "borderRadius": "6px", "cursor": "pointer", "alignSelf": "end"}),
        html.Div([
            html.Label("Expiration", style={"color": C["text_muted"], "fontSize": "12px"}),
            dcc.Dropdown(id="options-expiry-dropdown", placeholder="Select expiration",
                         style={"width": "200px"}, className="dash-bootstrap"),
        ]),
        html.Button("Load Chain", id="options-load-chain-btn", n_clicks=0,
                    style={"padding": "8px 16px", "backgroundColor": C["green"], "color": "#fff",
                           "border": "none", "borderRadius": "6px", "cursor": "pointer", "alignSelf": "end"}),
    ], style={"display": "flex", "gap": "15px", "alignItems": "end", "marginBottom": "25px"}),

    dcc.Loading(html.Div(id="options-chain-display"), type="circle"),
], style={"padding": "20px", "color": C["text"]})


@callback(
    Output("options-expiry-dropdown", "options"),
    Input("options-load-expiry-btn", "n_clicks"),
    State("options-symbol", "value"),
    prevent_initial_call=True,
)
def load_expirations(n, symbol):
    if not symbol or not cfg.PUBLIC_COM_SECRET:
        return []
    exps = api.get_option_expirations(symbol.upper().strip())
    if exps and isinstance(exps[0], dict) and "error" in exps[0]:
        return []
    return [{"label": str(e), "value": str(e)} for e in exps]


@callback(
    Output("options-chain-display", "children"),
    Input("options-load-chain-btn", "n_clicks"),
    [State("options-symbol", "value"), State("options-expiry-dropdown", "value")],
    prevent_initial_call=True,
)
def load_option_chain(n, symbol, expiration):
    if not symbol:
        return html.Div("Enter a symbol", style={"color": C["text_muted"], "padding": "20px"})
    if not cfg.PUBLIC_COM_SECRET:
        return html.Div("Set PUBLIC_COM_SECRET to load options data",
                        style={"color": C["red"], "padding": "20px"})

    chain = api.get_option_chain(symbol.upper().strip(), expiration)
    if "error" in chain:
        return html.Div(f"Error: {chain['error']}", style={"color": C["red"], "padding": "20px"})

    calls = chain.get("calls", [])
    puts = chain.get("puts", [])

    def make_chain_table(options, label):
        if not options:
            return html.Div(f"No {label}", style={"color": C["text_muted"], "padding": "10px"})
        df = pd.DataFrame(options)
        cols = [c for c in ["strike", "bid", "ask", "last", "volume", "open_interest"] if c in df.columns]
        title_color = C["green"] if "Call" in label else C["red"]
        return html.Div([
            html.Div(label, style={**HEADER_STYLE, "color": title_color}),
            dash_table.DataTable(
                data=df[cols].to_dict("records"),
                columns=[{"name": c.replace("_", " ").title(), "id": c} for c in cols],
                style_table={"overflowX": "auto", "overflowY": "auto", "maxHeight": "500px"},
                style_header=TABLE_HEADER_STYLE,
                style_cell=TABLE_CELL_STYLE,
                sort_action="native",
                page_size=30,
            ),
        ])

    return html.Div([
        html.Div(f"Expiration: {chain.get('expiration', 'nearest')}",
                 style={"color": C["text_muted"], "fontSize": "12px", "marginBottom": "12px"}),
        dbc.Row([
            dbc.Col(make_chain_table(calls, "Calls"), width=6),
            dbc.Col(make_chain_table(puts, "Puts"), width=6),
        ]),
    ])
