"""
Public.com API Client — SDK Wrapper
Thin wrapper around publicdotcom-py SDK. All dashboard modules import from here.

SDK fields verified against public_api_sdk v0.1.10 source.
"""
import os
import sys
import uuid
import traceback
from decimal import Decimal

import config as cfg

# ---------------------------------------------------------------------------
# Lazy SDK import (auto-installs if missing)
# ---------------------------------------------------------------------------
try:
    from public_api_sdk import (
        PublicApiClient,
        PublicApiClientConfiguration,
        InstrumentsRequest,
        InstrumentType,
        OrderInstrument,
        OrderRequest,
        OrderSide,
        OrderType,
        OrderExpirationRequest,
        TimeInForce,
        EquityMarketSession,
        OpenCloseIndicator,
        PreflightRequest,
        OptionChainRequest,
        OptionExpirationsRequest,
        HistoryRequest,
    )
    from public_api_sdk.auth_config import ApiKeyAuthConfig
    from public_api_sdk.models.instrument import Trading
    SDK_AVAILABLE = True
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "publicdotcom-py>=0.1.8"])
    from public_api_sdk import (
        PublicApiClient,
        PublicApiClientConfiguration,
        InstrumentsRequest,
        InstrumentType,
        OrderInstrument,
        OrderRequest,
        OrderSide,
        OrderType,
        OrderExpirationRequest,
        TimeInForce,
        EquityMarketSession,
        OpenCloseIndicator,
        PreflightRequest,
        OptionChainRequest,
        OptionExpirationsRequest,
        HistoryRequest,
    )
    from public_api_sdk.auth_config import ApiKeyAuthConfig
    from public_api_sdk.models.instrument import Trading
    SDK_AVAILABLE = True

# ---------------------------------------------------------------------------
# Enum maps (verified against SDK enums)
# ---------------------------------------------------------------------------
INST_TYPE_MAP = {
    "EQUITY": InstrumentType.EQUITY,
    "OPTION": InstrumentType.OPTION,
    "CRYPTO": InstrumentType.CRYPTO,
}
SIDE_MAP = {
    "BUY": OrderSide.BUY,
    "SELL": OrderSide.SELL,
}
ORDER_TYPE_MAP = {
    "LIMIT": OrderType.LIMIT,
    "MARKET": OrderType.MARKET,
    "STOP": OrderType.STOP,
    "STOP_LIMIT": OrderType.STOP_LIMIT,
}
SESSION_MAP = {
    "CORE": EquityMarketSession.CORE,
    "EXTENDED": EquityMarketSession.EXTENDED,
}
OC_MAP = {
    "OPEN": OpenCloseIndicator.OPEN,
    "CLOSE": OpenCloseIndicator.CLOSE,
}
# SDK TimeInForce: DAY and GTD (NOT GTC)
TIF_MAP = {
    "DAY": TimeInForce.DAY,
    "GTD": TimeInForce.GTD,
}
# Trading enum: BUY_AND_SELL, LIQUIDATION_ONLY, DISABLED (NOT BUY_ONLY/SELL_ONLY)
TRADING_MAP = {
    "BUY_AND_SELL": Trading.BUY_AND_SELL,
    "LIQUIDATION_ONLY": Trading.LIQUIDATION_ONLY,
    "DISABLED": Trading.DISABLED,
}


# ---------------------------------------------------------------------------
# Connection check (used by sidebar)
# ---------------------------------------------------------------------------
@property
def is_connected():
    return bool(cfg.PUBLIC_COM_SECRET)


def check_connection():
    """Returns True if PUBLIC_COM_SECRET is configured."""
    return bool(cfg.PUBLIC_COM_SECRET)


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------
def _make_client(account_id=None):
    secret = cfg.PUBLIC_COM_SECRET
    if not secret:
        raise RuntimeError("PUBLIC_COM_SECRET not set")
    acct = account_id or cfg.PUBLIC_COM_ACCOUNT_ID
    client = PublicApiClient(
        ApiKeyAuthConfig(api_secret_key=secret),
        config=PublicApiClientConfiguration(default_account_number=acct),
    )
    client.api_client.session.headers["User-Agent"] = "enso-trading-terminal/2.0"
    return client


# ---------------------------------------------------------------------------
# Account methods
# ---------------------------------------------------------------------------
def get_accounts():
    """List all accounts. Returns list of dicts."""
    try:
        c = _make_client()
        resp = c.get_accounts()
        c.close()
        return [
            {"account_id": a.account_id, "account_type": str(a.account_type)}
            for a in resp.accounts
        ]
    except Exception as e:
        return [{"error": str(e)}]


def get_portfolio(account_id=None):
    """
    Full portfolio snapshot: equity, buying power, positions, orders.
    Field names verified against SDK v0.1.10:
      - PortfolioPosition: instrument, quantity, current_value, percent_of_portfolio,
        last_price (Price), position_daily_gain (Gain), instrument_gain (Gain), cost_basis (CostBasis)
      - Price: last_price, timestamp
      - Gain: gain_value, gain_percentage, timestamp
      - CostBasis: total_cost, unit_cost, gain_value, gain_percentage, last_update
      - BuyingPower: buying_power, cash_only_buying_power, options_buying_power
      - PortfolioEquity: type (AssetType), value, percentage_of_portfolio
    """
    try:
        c = _make_client(account_id)
        p = c.get_portfolio()
        c.close()

        positions = []
        for pos in (p.positions or []):
            inst = pos.instrument
            daily = pos.position_daily_gain  # Gain object
            total = pos.instrument_gain  # Gain object
            cb = pos.cost_basis  # CostBasis object
            positions.append({
                "symbol": inst.symbol,
                "name": inst.name,
                "type": inst.type.value if inst.type else "",
                "quantity": float(pos.quantity) if pos.quantity else 0,
                "current_value": float(pos.current_value) if pos.current_value else 0,
                "last_price": float(pos.last_price.last_price) if pos.last_price and pos.last_price.last_price else 0,
                "pct_of_portfolio": float(pos.percent_of_portfolio) if pos.percent_of_portfolio else 0,
                "daily_gain_value": float(daily.gain_value) if daily and daily.gain_value else 0,
                "daily_gain_pct": float(daily.gain_percentage) if daily and daily.gain_percentage else 0,
                "total_gain_value": float(total.gain_value) if total and total.gain_value else 0,
                "total_gain_pct": float(total.gain_percentage) if total and total.gain_percentage else 0,
                "total_cost": float(cb.total_cost) if cb and cb.total_cost else 0,
                "unit_cost": float(cb.unit_cost) if cb and cb.unit_cost else 0,
            })

        bp = p.buying_power
        equity_items = [
            {
                "type": e.type.value,
                "value": float(e.value),
                "pct_of_portfolio": float(e.percentage_of_portfolio) if e.percentage_of_portfolio else 0,
            }
            for e in (p.equity or [])
        ]
        total_equity = sum(e["value"] for e in equity_items)

        orders = []
        for o in (p.orders or []):
            orders.append({
                "order_id": o.order_id,
                "symbol": o.instrument.symbol if o.instrument else "",
                "type": o.instrument.type.value if o.instrument and o.instrument.type else "",
                "side": o.side.value if o.side else "",
                "order_type": o.type.value if o.type else "",
                "status": o.status.value if o.status else "",
                "quantity": float(o.quantity) if o.quantity else None,
                "limit_price": float(o.limit_price) if o.limit_price else None,
                "stop_price": float(o.stop_price) if o.stop_price else None,
                "filled_quantity": float(o.filled_quantity) if o.filled_quantity else 0,
                "average_price": float(o.average_price) if o.average_price else None,
                "created_at": o.created_at.isoformat() if o.created_at else "",
            })

        return {
            "account_id": p.account_id,
            "account_type": p.account_type.value if p.account_type else "",
            "buying_power": float(bp.buying_power) if bp else 0,
            "cash_only_buying_power": float(bp.cash_only_buying_power) if bp else 0,
            "options_buying_power": float(bp.options_buying_power) if bp else 0,
            "total_equity": total_equity,
            "equity": equity_items,
            "positions": positions,
            "orders": orders,
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "error": str(e),
            "positions": [], "orders": [], "equity": [],
            "total_equity": 0, "buying_power": 0,
        }


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------
def get_all_instruments(types=None, trading_filter=None):
    """List tradeable instruments. types: list of 'EQUITY'/'CRYPTO'/'OPTION'."""
    try:
        c = _make_client()
        type_filters = [INST_TYPE_MAP[t] for t in (types or [])]
        kwargs = {}
        if type_filters:
            kwargs["instrument_types"] = type_filters
        if trading_filter and trading_filter in TRADING_MAP:
            kwargs["trading"] = [TRADING_MAP[trading_filter]]
        req = InstrumentsRequest(**kwargs)
        resp = c.get_all_instruments(req)
        c.close()

        results = []
        for inst in (resp.instruments or []):
            results.append({
                "symbol": inst.instrument.symbol,
                "type": inst.instrument.type.value,
                "trading": inst.trading.value if inst.trading else "",
                "fractional_trading": inst.fractional_trading.value if inst.fractional_trading else "",
                "option_trading": inst.option_trading.value if inst.option_trading else "",
            })
        return results
    except Exception as e:
        traceback.print_exc()
        return [{"error": str(e)}]


# ---------------------------------------------------------------------------
# Quotes — SDK Quote fields: instrument, last, bid, bid_size, ask, ask_size, volume, open_interest
# NOTE: SDK Quote does NOT have open/high/low/close fields
# ---------------------------------------------------------------------------
def get_quotes(symbol_type_pairs):
    """
    Get live quotes. symbol_type_pairs: list of (symbol, type_str) tuples.
    Example: [("AAPL", "EQUITY"), ("BTC", "CRYPTO")]
    """
    try:
        c = _make_client()
        instruments = [
            OrderInstrument(symbol=s, type=INST_TYPE_MAP[t])
            for s, t in symbol_type_pairs
        ]
        quotes = c.get_quotes(instruments)
        c.close()

        results = []
        for q in quotes:
            results.append({
                "symbol": q.instrument.symbol,
                "type": q.instrument.type.value,
                "last": float(q.last) if q.last is not None else None,
                "bid": float(q.bid) if q.bid is not None else None,
                "ask": float(q.ask) if q.ask is not None else None,
                "bid_size": int(q.bid_size) if q.bid_size is not None else None,
                "ask_size": int(q.ask_size) if q.ask_size is not None else None,
                "volume": int(q.volume) if q.volume is not None else None,
                "open_interest": int(q.open_interest) if q.open_interest is not None else None,
            })
        return results
    except Exception as e:
        traceback.print_exc()
        return [{"error": str(e)}]


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------
def get_option_expirations(symbol):
    """Get available option expiration dates for a symbol."""
    try:
        c = _make_client()
        req = OptionExpirationsRequest(
            instrument=OrderInstrument(symbol=symbol, type=InstrumentType.EQUITY)
        )
        resp = c.get_option_expirations(req)
        c.close()
        return resp.expirations if resp.expirations else []
    except Exception as e:
        return [{"error": str(e)}]


def get_option_chain(symbol, expiration_date=None):
    """Get option chain (calls + puts). Auto-selects nearest expiration if none given."""
    try:
        c = _make_client()
        if not expiration_date:
            req0 = OptionExpirationsRequest(
                instrument=OrderInstrument(symbol=symbol, type=InstrumentType.EQUITY)
            )
            resp0 = c.get_option_expirations(req0)
            exps = resp0.expirations if resp0.expirations else []
            if not exps:
                c.close()
                return {"calls": [], "puts": [], "expiration": ""}
            expiration_date = exps[0]

        req = OptionChainRequest(
            instrument=OrderInstrument(symbol=symbol, type=InstrumentType.EQUITY),
            expiration_date=expiration_date,
        )
        chain = c.get_option_chain(req)
        c.close()

        def _parse_option(opt):
            """Parse a Quote object from option chain."""
            osi = opt.instrument.symbol if opt.instrument else ""
            strike = None
            try:
                strike = int(osi[-8:]) / 1000
            except Exception:
                pass
            return {
                "symbol": osi,
                "strike": strike,
                "bid": float(opt.bid) if opt.bid is not None else None,
                "ask": float(opt.ask) if opt.ask is not None else None,
                "last": float(opt.last) if opt.last is not None else None,
                "volume": int(opt.volume) if opt.volume is not None else None,
                "open_interest": int(opt.open_interest) if opt.open_interest is not None else None,
                "bid_size": int(opt.bid_size) if opt.bid_size is not None else None,
                "ask_size": int(opt.ask_size) if opt.ask_size is not None else None,
            }

        calls = [_parse_option(o) for o in (chain.calls or [])]
        puts = [_parse_option(o) for o in (chain.puts or [])]
        return {"calls": calls, "puts": puts, "expiration": str(expiration_date)}
    except Exception as e:
        traceback.print_exc()
        return {"calls": [], "puts": [], "error": str(e)}


def get_option_greeks(osi_symbols):
    """Get greeks for specific option contracts (OSI symbol format)."""
    try:
        c = _make_client()
        resp = c.get_option_greeks(osi_symbols=osi_symbols)
        c.close()
        results = []
        for gd in (resp.greeks or []):
            g = gd.greeks
            results.append({
                "symbol": getattr(gd, "symbol", "") or getattr(gd, "osi_symbol", ""),
                "delta": float(g.delta) if hasattr(g, "delta") and g.delta is not None else None,
                "gamma": float(g.gamma) if hasattr(g, "gamma") and g.gamma is not None else None,
                "theta": float(g.theta) if hasattr(g, "theta") and g.theta is not None else None,
                "vega": float(g.vega) if hasattr(g, "vega") and g.vega is not None else None,
                "rho": float(g.rho) if hasattr(g, "rho") and g.rho is not None else None,
                "implied_volatility": float(g.implied_volatility) if hasattr(g, "implied_volatility") and g.implied_volatility is not None else None,
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


# ---------------------------------------------------------------------------
# Preflight (order cost estimate)
# SDK PreflightResponse fields: order_value, estimated_cost, estimated_commission,
#   buying_power_requirement, regulatory_fees, estimated_proceeds, margin_requirement, etc.
# ---------------------------------------------------------------------------
def preflight_order(
    symbol, inst_type, side, order_type,
    quantity=None, amount=None, limit_price=None, stop_price=None,
    session="CORE", open_close=None, tif="DAY",
):
    """Estimate order cost before placing."""
    try:
        c = _make_client()
        kwargs = {
            "instrument": OrderInstrument(symbol=symbol, type=INST_TYPE_MAP[inst_type]),
            "side": SIDE_MAP[side],
            "type": ORDER_TYPE_MAP[order_type],
            "expiration": OrderExpirationRequest(time_in_force=TIF_MAP.get(tif, TimeInForce.DAY)),
        }
        if quantity is not None:
            kwargs["quantity"] = Decimal(str(quantity))
        if amount is not None:
            kwargs["amount"] = Decimal(str(amount))
        if limit_price is not None:
            kwargs["limit_price"] = Decimal(str(limit_price))
        if stop_price is not None:
            kwargs["stop_price"] = Decimal(str(stop_price))
        if inst_type == "EQUITY" and session:
            kwargs["market_session"] = SESSION_MAP.get(session, EquityMarketSession.CORE)
        if inst_type == "OPTION" and open_close:
            kwargs["open_close"] = OC_MAP.get(open_close, OpenCloseIndicator.OPEN)

        resp = c.perform_preflight_calculation(PreflightRequest(**kwargs))
        c.close()
        return {
            "order_value": str(resp.order_value) if resp.order_value else "",
            "estimated_cost": str(resp.estimated_cost) if resp.estimated_cost else "",
            "estimated_commission": str(resp.estimated_commission) if resp.estimated_commission else "",
            "buying_power_requirement": str(resp.buying_power_requirement) if resp.buying_power_requirement else "",
            "estimated_proceeds": str(resp.estimated_proceeds) if resp.estimated_proceeds else "",
            "raw": str(resp),
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Order placement
# ---------------------------------------------------------------------------
def place_order(
    symbol, inst_type, side, order_type,
    quantity=None, amount=None, limit_price=None, stop_price=None,
    session="CORE", open_close=None, tif="DAY",
):
    """Place a trade. Returns order_id on success."""
    try:
        c = _make_client()
        kwargs = {
            "client_order_id": str(uuid.uuid4()),
            "instrument": OrderInstrument(symbol=symbol, type=INST_TYPE_MAP[inst_type]),
            "side": SIDE_MAP[side],
            "type": ORDER_TYPE_MAP[order_type],
            "expiration": OrderExpirationRequest(time_in_force=TIF_MAP.get(tif, TimeInForce.DAY)),
        }
        if quantity is not None:
            kwargs["quantity"] = Decimal(str(quantity))
        if amount is not None:
            kwargs["amount"] = Decimal(str(amount))
        if limit_price is not None:
            kwargs["limit_price"] = Decimal(str(limit_price))
        if stop_price is not None:
            kwargs["stop_price"] = Decimal(str(stop_price))
        if inst_type == "EQUITY" and session:
            kwargs["market_session"] = SESSION_MAP.get(session, EquityMarketSession.CORE)
        if inst_type == "OPTION" and open_close:
            kwargs["open_close"] = OC_MAP.get(open_close, OpenCloseIndicator.OPEN)

        new_order = c.place_order(OrderRequest(**kwargs))
        order_id = new_order.order_id
        c.close()
        return {"order_id": order_id, "status": "submitted"}
    except Exception as e:
        return {"error": str(e)}


def cancel_order(order_id, account_id=None):
    """Cancel an order by ID."""
    try:
        c = _make_client(account_id)
        c.cancel_order(order_id=order_id)
        c.close()
        return {"status": "cancelled", "order_id": order_id}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Transaction history
# SDK HistoryTransaction fields: id, timestamp, type, sub_type, symbol,
#   side, description, net_amount, quantity, fees (plural — verified in SDK)
# ---------------------------------------------------------------------------
def get_history(account_id=None, tx_type=None, limit=None):
    """Get transaction history. Optional filter by type (TRADE, MONEY_MOVEMENT, etc.)."""
    try:
        c = _make_client(account_id)
        resp = c.get_history()
        c.close()
        txns = resp.transactions or []
        if tx_type:
            txns = [t for t in txns if t.type.value == tx_type]
        if limit:
            txns = txns[:limit]
        results = []
        for t in txns:
            results.append({
                "id": t.id,
                "type": t.type.value,
                "sub_type": t.sub_type.value if t.sub_type else "",
                "description": t.description or "",
                "symbol": t.symbol or "",
                "side": t.side.value if t.side else "",
                "quantity": float(t.quantity) if t.quantity is not None else None,
                "net_amount": float(t.net_amount) if t.net_amount is not None else None,
                "fees": float(t.fees) if t.fees is not None else 0,
                "timestamp": t.timestamp.isoformat() if t.timestamp else "",
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]
