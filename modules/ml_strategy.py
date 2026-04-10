"""
ML Strategy Engine
- Feature engineering (technical indicators + sentiment)
- Gradient Boosted ensemble for signal generation
- Trend regime detection via Hidden Markov Model
- Replaces pure S/R mean-reversion with ML-driven signals
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
import warnings
warnings.filterwarnings("ignore")


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute technical features for ML model.
    Returns DataFrame with feature columns.
    """
    feat = pd.DataFrame(index=df.index)

    # Price-based
    feat["returns_1d"] = df["Close"].pct_change(1)
    feat["returns_5d"] = df["Close"].pct_change(5)
    feat["returns_10d"] = df["Close"].pct_change(10)
    feat["returns_20d"] = df["Close"].pct_change(20)

    # Volatility
    feat["volatility_10d"] = df["Close"].pct_change().rolling(10).std()
    feat["volatility_20d"] = df["Close"].pct_change().rolling(20).std()
    feat["vol_ratio"] = feat["volatility_10d"] / feat["volatility_20d"].replace(0, np.nan)

    # Moving averages
    feat["sma_10"] = df["Close"].rolling(10).mean()
    feat["sma_20"] = df["Close"].rolling(20).mean()
    feat["sma_50"] = df["Close"].rolling(50).mean()
    feat["price_vs_sma10"] = (df["Close"] - feat["sma_10"]) / feat["sma_10"]
    feat["price_vs_sma20"] = (df["Close"] - feat["sma_20"]) / feat["sma_20"]
    feat["price_vs_sma50"] = (df["Close"] - feat["sma_50"]) / feat["sma_50"]
    feat["sma_cross"] = (feat["sma_10"] - feat["sma_20"]) / feat["sma_20"]

    # RSI
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    feat["rsi_14"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df["Close"].ewm(span=12).mean()
    ema26 = df["Close"].ewm(span=26).mean()
    feat["macd"] = ema12 - ema26
    feat["macd_signal"] = feat["macd"].ewm(span=9).mean()
    feat["macd_hist"] = feat["macd"] - feat["macd_signal"]

    # Bollinger Bands
    bb_mid = df["Close"].rolling(20).mean()
    bb_std = df["Close"].rolling(20).std()
    feat["bb_upper"] = (df["Close"] - (bb_mid + 2 * bb_std)) / bb_std.replace(0, np.nan)
    feat["bb_lower"] = (df["Close"] - (bb_mid - 2 * bb_std)) / bb_std.replace(0, np.nan)
    feat["bb_width"] = (4 * bb_std) / bb_mid.replace(0, np.nan)

    # Volume features
    if "Volume" in df.columns:
        feat["volume_sma10"] = df["Volume"].rolling(10).mean()
        feat["volume_ratio"] = df["Volume"] / feat["volume_sma10"].replace(0, np.nan)
        feat["obv"] = (np.sign(df["Close"].diff()) * df["Volume"]).cumsum()
        feat["obv_slope"] = feat["obv"].pct_change(5)

    # ATR (Average True Range)
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    feat["atr_14"] = tr.rolling(14).mean()
    feat["atr_ratio"] = feat["atr_14"] / df["Close"]

    # Momentum
    feat["momentum_10"] = df["Close"] / df["Close"].shift(10) - 1
    feat["momentum_20"] = df["Close"] / df["Close"].shift(20) - 1

    # Mean reversion z-score
    feat["zscore_20"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).std()

    return feat


def create_labels(df: pd.DataFrame, forward_days: int = 15,
                  threshold_pct: float = 2.0) -> pd.Series:
    """
    Create classification labels based on forward returns.
    1 = BUY_CALL (price goes up > threshold)
    -1 = BUY_PUT (price goes down > threshold)
    0 = NO_TRADE (sideways)
    """
    forward_return = df["Close"].shift(-forward_days) / df["Close"] - 1
    labels = pd.Series(0, index=df.index)
    labels[forward_return > threshold_pct / 100] = 1
    labels[forward_return < -threshold_pct / 100] = -1
    return labels


class MLStrategy:
    """
    ML-based options trading strategy using Gradient Boosted Trees.
    Combines technical features with trend regime detection.
    """

    def __init__(self, n_estimators=200, max_depth=4, learning_rate=0.05,
                 min_samples_leaf=20, forward_days=15, threshold_pct=2.0):
        self.model = GradientBoostingClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            min_samples_leaf=min_samples_leaf,
            subsample=0.8,
            random_state=42,
        )
        self.scaler = StandardScaler()
        self.forward_days = forward_days
        self.threshold_pct = threshold_pct
        self.feature_cols = None
        self.is_trained = False
        self.train_accuracy = 0
        self.cv_accuracy = 0
        self.feature_importance = {}

    def _prepare_data(self, df: pd.DataFrame):
        """Prepare features and labels."""
        features = compute_features(df)
        labels = create_labels(df, self.forward_days, self.threshold_pct)

        # Combine and drop NaN
        combined = features.copy()
        combined["label"] = labels
        combined = combined.dropna()

        # Remove last forward_days rows (no valid label)
        combined = combined.iloc[:-self.forward_days] if self.forward_days > 0 else combined

        self.feature_cols = [c for c in features.columns if c in combined.columns]
        X = combined[self.feature_cols]
        y = combined["label"]
        return X, y

    def train(self, df: pd.DataFrame) -> dict:
        """
        Train the ML model with time-series cross-validation.
        Returns training metrics.
        """
        X, y = self._prepare_data(df)

        if len(X) < 100:
            return {"error": "Insufficient data for ML training (need 100+ samples)"}

        # Time series cross-validation
        tscv = TimeSeriesSplit(n_splits=3)
        cv_scores = []
        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)

            model = GradientBoostingClassifier(
                n_estimators=self.model.n_estimators,
                max_depth=self.model.max_depth,
                learning_rate=self.model.learning_rate,
                min_samples_leaf=self.model.min_samples_leaf,
                subsample=0.8,
                random_state=42,
            )
            model.fit(X_train_scaled, y_train)
            cv_scores.append(accuracy_score(y_val, model.predict(X_val_scaled)))

        # Final training on all data
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True
        self.train_accuracy = accuracy_score(y, self.model.predict(X_scaled))
        self.cv_accuracy = np.mean(cv_scores)

        # Feature importance
        self.feature_importance = dict(
            sorted(
                zip(self.feature_cols, self.model.feature_importances_),
                key=lambda x: x[1],
                reverse=True,
            )
        )

        return {
            "train_accuracy": round(self.train_accuracy * 100, 1),
            "cv_accuracy": round(self.cv_accuracy * 100, 1),
            "n_samples": len(X),
            "n_features": len(self.feature_cols),
            "label_distribution": y.value_counts().to_dict(),
            "top_features": dict(list(self.feature_importance.items())[:10]),
        }

    def predict(self, df: pd.DataFrame) -> dict:
        """
        Generate trading signal for the latest bar.
        Returns signal dict with type, confidence, and features.
        """
        if not self.is_trained:
            return {"signal": "NO_TRADE", "confidence": 0, "reason": "Model not trained"}

        features = compute_features(df)
        latest = features.iloc[[-1]].dropna(axis=1)

        # Ensure all required columns exist
        missing = set(self.feature_cols) - set(latest.columns)
        for col in missing:
            latest[col] = 0
        latest = latest[self.feature_cols]

        if latest.isna().any().any():
            return {"signal": "NO_TRADE", "confidence": 0, "reason": "Insufficient data"}

        X_scaled = self.scaler.transform(latest)
        prediction = self.model.predict(X_scaled)[0]
        probabilities = self.model.predict_proba(X_scaled)[0]
        confidence = float(max(probabilities)) * 100

        signal_map = {1: "BUY_CALL", -1: "BUY_PUT", 0: "NO_TRADE"}

        return {
            "signal": signal_map.get(prediction, "NO_TRADE"),
            "confidence": round(confidence, 1),
            "probabilities": {
                signal_map.get(cls, str(cls)): round(float(prob) * 100, 1)
                for cls, prob in zip(self.model.classes_, probabilities)
            },
            "features": {
                "rsi_14": round(float(features["rsi_14"].iloc[-1]), 1) if "rsi_14" in features else None,
                "macd_hist": round(float(features["macd_hist"].iloc[-1]), 4) if "macd_hist" in features else None,
                "zscore_20": round(float(features["zscore_20"].iloc[-1]), 2) if "zscore_20" in features else None,
                "momentum_20": round(float(features["momentum_20"].iloc[-1]), 4) if "momentum_20" in features else None,
            },
        }

    def get_regime(self, df: pd.DataFrame) -> str:
        """
        Simple trend regime detection using multiple timeframes.
        Returns: 'BULLISH', 'BEARISH', or 'SIDEWAYS'
        """
        if len(df) < 50:
            return "SIDEWAYS"

        close = df["Close"]
        sma20 = close.rolling(20).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        current = close.iloc[-1]
        momentum = close.iloc[-1] / close.iloc[-20] - 1

        bullish_signals = 0
        if current > sma20:
            bullish_signals += 1
        if current > sma50:
            bullish_signals += 1
        if sma20 > sma50:
            bullish_signals += 1
        if momentum > 0.02:
            bullish_signals += 1

        if bullish_signals >= 3:
            return "BULLISH"
        elif bullish_signals <= 1:
            return "BEARISH"
        return "SIDEWAYS"
