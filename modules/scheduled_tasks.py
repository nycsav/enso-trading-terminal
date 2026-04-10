"""
Scheduled Tasks
- Periodic S/R level recalculation
- Signal monitoring and alerts
"""
import threading
import time
from datetime import datetime
from modules.research import fetch_market_data
from modules.sr_engine import generate_signals, get_sr_summary
from config import SYMBOLS


class SignalMonitor:
    """Background monitor for S/R signals across symbols."""

    def __init__(self, symbols: list = None, interval_minutes: int = 15):
        self.symbols = symbols or SYMBOLS
        self.interval = interval_minutes * 60
        self.running = False
        self._thread = None
        self.latest_signals = {}
        self.last_update = None

    def start(self):
        """Start the monitoring loop."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the monitoring loop."""
        self.running = False

    def _run_loop(self):
        """Main monitoring loop."""
        while self.running:
            self.refresh()
            time.sleep(self.interval)

    def refresh(self):
        """Manually refresh all signals."""
        for symbol in self.symbols:
            try:
                df = fetch_market_data(symbol, period="3mo")
                if df.empty:
                    continue
                summary = get_sr_summary(df, symbol=symbol)
                self.latest_signals[symbol] = {
                    "summary": summary,
                    "signals": summary["signals"],
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as e:
                self.latest_signals[symbol] = {
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
        self.last_update = datetime.now().isoformat()

    def get_all_signals(self) -> dict:
        """Get latest signals for all symbols."""
        return self.latest_signals

    def get_active_alerts(self, min_confluence: float = 50.0) -> list:
        """Get high-confluence signals that warrant attention."""
        alerts = []
        for symbol, data in self.latest_signals.items():
            for sig in data.get("signals", []):
                if sig["confluence"]["confluence_total"] >= min_confluence:
                    alerts.append({
                        "symbol": symbol,
                        "type": sig["type"],
                        "level": sig["level_price"],
                        "confluence": sig["confluence"]["confluence_total"],
                        "timestamp": data.get("timestamp"),
                    })
        return sorted(alerts, key=lambda x: x["confluence"], reverse=True)
