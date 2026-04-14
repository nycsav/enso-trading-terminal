# Enso Multi-Agent Trading Framework
## Architecture Design Document

---

## Overview

The Enso multi-agent framework replaces manual backtesting with AI-driven signal generation. Instead of you testing every symbol against every strategy, the system scans the market, synthesizes multiple data sources, and presents you with 1-3 actionable trade ideas each morning.

**You always make the final call.** The system never places trades without your explicit approval.

---

## The 3-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 1: INTELLIGENCE                     │
│                   (Data Collection Agents)                    │
│                                                               │
│  ┌──────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │  News Agent   │  │ Technical Agent  │  │ Volatility     │  │
│  │              │  │                 │  │ Agent          │  │
│  │ • Overnight   │  │ • SMA 20/50     │  │ • Hist vol     │  │
│  │   news scan   │  │ • RSI 14        │  │ • Vol regime   │  │
│  │ • Sentiment   │  │ • ATR           │  │ • IV vs RV     │  │
│  │   scoring     │  │ • 52-week range │  │ • Percentile   │  │
│  │ • Source:     │  │ • Source:       │  │ • Source:      │  │
│  │   Perplexity  │  │   yfinance      │  │   yfinance     │  │
│  └──────┬───────┘  └───────┬─────────┘  └───────┬────────┘  │
│         │                  │                     │            │
└─────────┼──────────────────┼─────────────────────┼────────────┘
          │                  │                     │
          ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 2: STRATEGY                         │
│                  (Signal Synthesis + Debate)                  │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Signal Synthesizer                          │ │
│  │                                                         │ │
│  │  Bull Case ◄──────────► Bear Case                       │ │
│  │  (What supports      (What argues                       │ │
│  │   this trade?)        against it?)                      │ │
│  │                                                         │ │
│  │  Confidence Score: 0-100                                │ │
│  │  • All 3 agents agree → 80-100 (High)                  │ │
│  │  • 2 of 3 agree → 50-79 (Moderate)                     │ │
│  │  • Mixed signals → 0-49 (Skip)                         │ │
│  │                                                         │ │
│  │  Strategy Map: Direction + Vol Regime → Options Play    │ │
│  │  • BULLISH + HIGH_VOL → Cash-Secured Put               │ │
│  │  • BULLISH + LOW_VOL → Bull Call Spread                 │ │
│  │  • BEARISH + HIGH_VOL → Bear Call Spread                │ │
│  │  • NEUTRAL + HIGH_VOL → Iron Condor                    │ │
│  └──────────────────────┬──────────────────────────────────┘ │
│                         │                                     │
└─────────────────────────┼─────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 3: EXECUTION                        │
│                (Risk Management + Order Prep)                 │
│                                                               │
│  ┌──────────────────┐  ┌─────────────────────────────────┐  │
│  │  Risk Manager     │  │  Trade Prep                     │  │
│  │                  │  │                                 │  │
│  │ • Max 5% per     │  │ • Final recommendation         │  │
│  │   position       │  │ • Bull case + Bear case        │  │
│  │ • Max 20%        │  │ • Strategy with description    │  │
│  │   portfolio risk │  │ • Max loss in dollars          │  │
│  │ • Max $500       │  │ • Confidence score             │  │
│  │   single loss    │  │ • Action: APPROVE or REJECT    │  │
│  │ • Max 5 open     │  │                                 │  │
│  │   positions      │  │  ──► SENT TO YOU VIA           │  │
│  └──────────────────┘  │      NOTIFICATION               │  │
│                        └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Inspired By (Sources)

| Source | What We Took | Link |
|--------|-------------|------|
| QuantInsti Multi-Agent Bot | The analyst → portfolio → execution pipeline pattern with LLM sentiment + ML technical dual-signal | https://www.quantinsti.com/articles/agentic-ai-portfolio-manager-alpaca-trading-bot/ |
| TradingAgents (UCLA/MIT) | The bull/bear debate pattern for balanced analysis; risk management as a separate agent layer | https://tradingagents-ai.github.io |
| LLM-Enhanced-Trading | Sentiment integration with technical indicators (TSLA Sharpe went from 0.34 to 3.47) | https://github.com/Ronitt272/LLM-Enhanced-Trading |
| FinRL-Trading | Weight-centric architecture: selection → allocation → timing → risk overlay; Alpaca paper trading deployment | https://github.com/AI4Finance-Foundation/FinRL-Trading |

---

## How It Connects to Existing Enso Components

| Component | Role in New Framework |
|-----------|-----------------------|
| Morning Scanner (cron) | Feeds Layer 1 News Agent with overnight news data |
| api_client.py | Layer 3 uses this to pull live options chains and run preflight on Public.com |
| Alpaca paper trading | Layer 3 can execute approved trades on paper account for testing |
| Backtest engine | Still available for deep-dive validation of specific strategies |
| strategy_engines.py | The 8 backtesting strategies remain for historical testing |
| options-automation-library.md | Strategy Map references these 35+ strategies for recommendations |

---

## Daily Workflow

```
8:15 AM  → Morning Scanner cron fires
         → News Agent scans overnight news
         → Technical Agent runs on watchlist symbols
         → Volatility Agent checks vol regimes
         → Signal Synthesizer builds bull/bear cases
         → Risk Manager filters out oversized/risky ideas
         → Trade Prep sends you top 1-3 ideas via notification

8:15 AM  → YOU receive notification on your phone/desktop
         → Review the bull case, bear case, strategy, max loss
         → Reply: "pull chain for NVDA" or "paper trade the SPY idea"

9:30 AM  → Market opens
         → If you approved an idea, Perplexity pulls live options chain
         → Runs preflight on Public.com showing exact cost
         → You confirm → trade placed (or paper traded on Alpaca)

3:45 PM  → Expiration Alert cron checks open positions
         → Flags anything expiring within 3 days
```

---

## Risk Parameters (Configurable)

| Parameter | Default | What It Does |
|-----------|---------|-------------|
| max_position_pct | 5% | No single trade can be more than 5% of portfolio |
| max_portfolio_risk_pct | 20% | Total open risk capped at 20% of portfolio |
| max_single_loss | $500 | No trade can lose more than $500 |
| max_open_positions | 5 | Maximum 5 simultaneous positions |
| min_confidence | 60 | Only recommend trades scoring 60+ confidence |

---

## Files

| File | Purpose |
|------|---------|
| modules/agent_framework.py | The 3-layer multi-agent engine (6 agent classes + pipeline) |
| modules/strategy_map.py | Direction + Vol Regime → Options Strategy mapping |
| docs/multi-agent-architecture.md | This document |
