"""
Reinforcement Learning Agent for Position Sizing & Timing
- Q-Learning based agent for adaptive position sizing
- State: market regime, volatility, signal confidence, portfolio exposure
- Actions: position size (0%, 2%, 5%, 10%) and hold duration
- Reward: risk-adjusted P&L (Sharpe-like)
- No external RL library dependency (pure numpy implementation)
"""
import numpy as np
import json
import os
from typing import Tuple


class TradingState:
    """Discretize continuous market state into bins for Q-table."""

    # State dimensions and their bins
    REGIME_BINS = ["BEARISH", "SIDEWAYS", "BULLISH"]  # 3
    VOL_BINS = ["LOW", "MEDIUM", "HIGH"]  # 3
    CONFIDENCE_BINS = ["LOW", "MEDIUM", "HIGH"]  # 3
    EXPOSURE_BINS = ["NONE", "LOW", "MEDIUM", "HIGH"]  # 4
    RSI_BINS = ["OVERSOLD", "NEUTRAL", "OVERBOUGHT"]  # 3

    @staticmethod
    def discretize_volatility(vol: float) -> str:
        if vol < 0.15:
            return "LOW"
        elif vol < 0.30:
            return "MEDIUM"
        return "HIGH"

    @staticmethod
    def discretize_confidence(conf: float) -> str:
        if conf < 40:
            return "LOW"
        elif conf < 65:
            return "MEDIUM"
        return "HIGH"

    @staticmethod
    def discretize_exposure(exposure_pct: float) -> str:
        if exposure_pct <= 0:
            return "NONE"
        elif exposure_pct < 10:
            return "LOW"
        elif exposure_pct < 25:
            return "MEDIUM"
        return "HIGH"

    @staticmethod
    def discretize_rsi(rsi: float) -> str:
        if rsi < 30:
            return "OVERSOLD"
        elif rsi > 70:
            return "OVERBOUGHT"
        return "NEUTRAL"

    @classmethod
    def get_state(cls, regime: str, volatility: float, confidence: float,
                  exposure_pct: float, rsi: float) -> tuple:
        return (
            regime,
            cls.discretize_volatility(volatility),
            cls.discretize_confidence(confidence),
            cls.discretize_exposure(exposure_pct),
            cls.discretize_rsi(rsi),
        )

    @classmethod
    def state_space_size(cls) -> int:
        return (len(cls.REGIME_BINS) * len(cls.VOL_BINS) *
                len(cls.CONFIDENCE_BINS) * len(cls.EXPOSURE_BINS) *
                len(cls.RSI_BINS))


class RLPositionSizer:
    """
    Q-Learning agent that learns optimal position sizing.

    Actions:
    0 = NO_TRADE (skip)
    1 = SMALL (2% of capital)
    2 = MEDIUM (5% of capital)
    3 = LARGE (10% of capital)
    """

    ACTIONS = {
        0: {"name": "NO_TRADE", "size_pct": 0},
        1: {"name": "SMALL", "size_pct": 2},
        2: {"name": "MEDIUM", "size_pct": 5},
        3: {"name": "LARGE", "size_pct": 10},
    }
    N_ACTIONS = len(ACTIONS)

    def __init__(self, alpha=0.1, gamma=0.95, epsilon=0.15,
                 epsilon_decay=0.995, epsilon_min=0.05):
        self.alpha = alpha  # Learning rate
        self.gamma = gamma  # Discount factor
        self.epsilon = epsilon  # Exploration rate
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.q_table = {}  # state -> action values
        self.training_history = []
        self.total_episodes = 0

    def _get_q_values(self, state: tuple) -> np.ndarray:
        state_key = str(state)
        if state_key not in self.q_table:
            self.q_table[state_key] = np.zeros(self.N_ACTIONS)
        return self.q_table[state_key]

    def choose_action(self, state: tuple, explore: bool = True) -> int:
        if explore and np.random.random() < self.epsilon:
            return np.random.randint(self.N_ACTIONS)
        q_values = self._get_q_values(state)
        return int(np.argmax(q_values))

    def update(self, state: tuple, action: int, reward: float,
               next_state: tuple, done: bool = False):
        q_values = self._get_q_values(state)
        next_q = self._get_q_values(next_state)

        if done:
            target = reward
        else:
            target = reward + self.gamma * np.max(next_q)

        q_values[action] += self.alpha * (target - q_values[action])
        self.q_table[str(state)] = q_values

        # Decay exploration
        self.epsilon = max(self.epsilon_min,
                           self.epsilon * self.epsilon_decay)

    def get_position_size(self, state: tuple) -> dict:
        action = self.choose_action(state, explore=False)
        action_info = self.ACTIONS[action]
        q_values = self._get_q_values(state)

        return {
            "action": action,
            "action_name": action_info["name"],
            "size_pct": action_info["size_pct"],
            "q_values": {self.ACTIONS[i]["name"]: round(float(q_values[i]), 4)
                         for i in range(self.N_ACTIONS)},
            "confidence": round(float(np.max(q_values) - np.mean(q_values)), 4),
        }

    def train_on_backtest(self, trades: list, capital: float,
                          regime_fn=None) -> dict:
        """
        Train the RL agent on historical backtest trades.
        Each trade becomes a state-action-reward transition.
        """
        if not trades:
            return {"error": "No trades to train on"}

        episode_rewards = []
        total_reward = 0

        for i, trade in enumerate(trades):
            # Build state from trade context
            regime = "SIDEWAYS"
            if regime_fn and "entry_date" in trade:
                try:
                    regime = regime_fn(trade["entry_date"])
                except Exception:
                    pass

            vol = trade.get("iv", 0.25)
            conf = trade.get("confluence", 50)
            exposure = trade.get("cost", 0) / capital * 100 if capital > 0 else 0
            rsi = trade.get("rsi", 50)

            state = TradingState.get_state(regime, vol, conf, exposure, rsi)

            # Determine what action was taken (map position size to action)
            trade_size_pct = trade.get("cost", 0) / capital * 100 if capital > 0 else 0
            if trade_size_pct <= 0.5:
                action = 0
            elif trade_size_pct <= 3:
                action = 1
            elif trade_size_pct <= 7:
                action = 2
            else:
                action = 3

            # Reward: risk-adjusted P&L
            pnl = trade.get("pnl", 0)
            cost = trade.get("cost", 1)
            pnl_pct = pnl / cost if cost > 0 else 0

            # Penalize large losses more than rewarding gains
            if pnl_pct > 0:
                reward = pnl_pct * 1.0
            else:
                reward = pnl_pct * 1.5  # Asymmetric penalty

            # Bonus for no-trade when loss would occur
            if action == 0 and pnl < 0:
                reward = 0.1  # Small reward for avoiding loss

            # Next state
            is_done = (i == len(trades) - 1)
            if not is_done:
                next_trade = trades[i + 1]
                next_exposure = next_trade.get("cost", 0) / capital * 100
                next_state = TradingState.get_state(
                    regime, vol, next_trade.get("confluence", 50),
                    next_exposure, next_trade.get("rsi", 50)
                )
            else:
                next_state = state

            self.update(state, action, reward, next_state, is_done)
            total_reward += reward
            episode_rewards.append(reward)

        self.total_episodes += 1
        self.training_history.append({
            "episode": self.total_episodes,
            "total_reward": round(total_reward, 4),
            "avg_reward": round(np.mean(episode_rewards), 4),
            "n_trades": len(trades),
            "epsilon": round(self.epsilon, 4),
            "q_table_size": len(self.q_table),
        })

        return self.training_history[-1]

    def get_training_summary(self) -> dict:
        if not self.training_history:
            return {"error": "No training history"}

        return {
            "total_episodes": self.total_episodes,
            "q_table_states": len(self.q_table),
            "current_epsilon": round(self.epsilon, 4),
            "avg_reward_last_5": round(
                np.mean([h["avg_reward"] for h in self.training_history[-5:]]), 4
            ) if self.training_history else 0,
            "history": self.training_history[-10:],
        }

    def save(self, filepath: str = "rl_agent_state.json"):
        data = {
            "q_table": {k: v.tolist() for k, v in self.q_table.items()},
            "epsilon": self.epsilon,
            "total_episodes": self.total_episodes,
            "training_history": self.training_history,
        }
        with open(filepath, "w") as f:
            json.dump(data, f)

    def load(self, filepath: str = "rl_agent_state.json"):
        if not os.path.exists(filepath):
            return False
        with open(filepath, "r") as f:
            data = json.load(f)
        self.q_table = {k: np.array(v) for k, v in data["q_table"].items()}
        self.epsilon = data.get("epsilon", 0.15)
        self.total_episodes = data.get("total_episodes", 0)
        self.training_history = data.get("training_history", [])
        return True
