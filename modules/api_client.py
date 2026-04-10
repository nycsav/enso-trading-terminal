"""
Public.com API Client
- Live brokerage connection
- Account data, positions, orders
"""
import requests
from config import PUBLIC_API_KEY, PUBLIC_API_BASE


class PublicAPIClient:
    """Client for interacting with Public.com brokerage API."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or PUBLIC_API_KEY
        self.base_url = PUBLIC_API_BASE
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            })

    @property
    def is_connected(self) -> bool:
        return bool(self.api_key)

    def get_account(self) -> dict:
        """Get account information."""
        if not self.is_connected:
            return {"error": "No API key configured"}
        try:
            resp = self.session.get(f"{self.base_url}/account")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def get_positions(self) -> list:
        """Get current positions."""
        if not self.is_connected:
            return []
        try:
            resp = self.session.get(f"{self.base_url}/positions")
            resp.raise_for_status()
            return resp.json().get("positions", [])
        except Exception as e:
            return [{"error": str(e)}]

    def get_orders(self, status: str = "all") -> list:
        """Get order history."""
        if not self.is_connected:
            return []
        try:
            resp = self.session.get(f"{self.base_url}/orders", params={"status": status})
            resp.raise_for_status()
            return resp.json().get("orders", [])
        except Exception as e:
            return [{"error": str(e)}]

    def place_order(self, symbol: str, side: str, quantity: int,
                    order_type: str = "market", limit_price: float = None) -> dict:
        """Place a new order."""
        if not self.is_connected:
            return {"error": "No API key configured"}
        payload = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "type": order_type,
        }
        if limit_price is not None:
            payload["limit_price"] = limit_price
        try:
            resp = self.session.post(f"{self.base_url}/orders", json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol."""
        try:
            resp = self.session.get(f"{self.base_url}/market/quote/{symbol}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
