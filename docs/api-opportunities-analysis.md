# Public.com API: Untapped Opportunities for Enso Trading Terminal

## What We Already Have (Built & Working)

### Dashboard (enso-build/)
| Feature | Status |
|---------|--------|
| Portfolio view (equity, P&L, buying power) | Live |
| Options chain viewer (calls/puts by expiration) | Live |
| Order management (preflight + place, single-leg) | Live |
| Signal monitor (dashboard page) | Live |
| 8 backtesting strategies | Live |
| 60+ stock symbols, searchable | Live |
| Dark theme CSS | Live |

### Perplexity Skill Scripts (15 scripts)
| Script | Status |
|--------|--------|
| get_accounts, get_portfolio, get_orders | Working |
| get_quotes, get_instruments, get_instrument | Working |
| get_option_chain, get_option_expirations, get_option_greeks | Working |
| preflight, place_order, cancel_order | Working |
| get_history | Working |
| check_setup, config | Working |

### Options Automation Library
- 35+ named strategies documented
- SDK code examples for each
- Covers: verticals, iron condors, straddles, strangles, calendars, diagonals, synthetics, wheels, and event-driven plays

---

## NEW Opportunities Not Yet Leveraged

### 1. Bond Trading via API (NEW — March 25, 2026)
**What:** Public just added bond trading (corporate bonds + treasuries) via API.  
**Why it matters:** No other retail API offers bond trading. Your dashboard doesn't touch bonds at all.  
**Implementation:**
- Add BOND to `INST_TYPE_MAP` in `api_client.py`
- New page: `pages/bonds.py` — view bond holdings from the Bond account (3CT06086)
- Add bond instruments to the quote/trade flow
- Backtest idea: bond/equity rotation strategy using yield data

### 2. Cancel-and-Replace Orders (NEW — Feb/March 2026)
**What:** PUT endpoint to edit/replace active orders without canceling + re-placing.  
**Why it matters:** Faster order management, critical for active options trading.  
**Implementation:**
- Add `edit_order()` method to `api_client.py`
- Add "Edit" button next to active orders on the Orders page
- New skill script: `edit_order.py`

### 3. Crypto Trading
**What:** Full crypto support (BTC, ETH, etc.) with 0.6% fees, notional limit orders.  
**Why it matters:** Currently in the API client enum maps but no dedicated crypto page or crypto-specific features.  
**Implementation:**
- New page: `pages/crypto.py` — live crypto quotes, portfolio view, trade execution
- Crypto-specific backtesting strategies (momentum, mean reversion on BTC/ETH)
- Notional limit orders (buy $X worth) — unique to crypto on Public

### 4. Options Rebate Tracking & Optimization
**What:** Public pays $0.06-$0.18 per options contract traded. API traders earn $0.06/contract (Tiers 1-3) and $0.10/contract at Tier 4 (10,000+ contracts/month).  
**Why it matters:** At scale, this is real money. 1,000 contracts/month = $60+ back. No other commission-free broker does this.  
**Implementation:**
- Add rebate calculator widget to the dashboard
- Track monthly contract volume from transaction history
- Show current tier + contracts needed for next tier
- Show estimated rebate earnings alongside trade P&L

### 5. Scheduled Automation Workflows (Perplexity Cron Jobs)
**What:** Perplexity Computer can run recurring tasks on schedule.  
**Why it matters:** This is the killer feature. You can set up fully automated trading workflows that run without you.  
**Workflow Ideas (all executable today via Perplexity skill):**
- **Morning Briefing (9:30 AM):** Pull portfolio, summarize overnight moves, flag expiring options
- **Expiration Watch (3:45 PM):** Check options expiring this week, alert with roll/close recommendations
- **Weekly Covered Call Scanner (Monday AM):** Scan option chains on held positions, suggest covered calls
- **Dip Alerts:** If a watchlist stock drops 5%+, show nearest put options for protection
- **Earnings Calendar Prep:** 1 week before earnings, pull IV data, suggest pre-earnings strategy
- **Rebate Tracker:** Weekly check of contract volume vs. next rebate tier threshold

### 6. Multi-Leg Options Execution from Dashboard
**What:** The API supports multi-leg orders natively (MultilegOrderRequest, PreflightMultiLegRequest).  
**Why it matters:** The skill scripts have the code patterns, but the dashboard Orders page only handles single-leg.  
**Implementation:**
- Add multi-leg order builder to Orders page (or new dedicated page)
- Pre-built strategy templates: bull call spread, iron condor, straddle, covered call
- Multi-leg preflight showing net debit/credit, max loss, max profit
- One-click execution of all legs simultaneously

### 7. TradingView Webhook Integration
**What:** Traders set up alerts in TradingView → webhook hits a server → server places orders via Public API.  
**Why it matters:** Mentioned in the official Public.com API webinar as a popular user pattern. Bridges technical analysis with automated execution.  
**Implementation:**
- Add a lightweight webhook receiver endpoint to the Enso app
- Parse TradingView alert JSON (symbol, price, action)
- Auto-execute or queue orders based on alert conditions
- Log all webhook-triggered trades in a dedicated view

### 8. Research-to-Execution Pipeline
**What:** Perplexity's native web search + Public's execution API in one flow.  
**Why it matters:** This is unique to the Perplexity + Public combination. No other broker offers this.  
**Workflow Examples:**
- "Research NVDA earnings → pull options chain for earnings date → recommend strategy → preflight → place trade"
- "Scan news for Fed rate decision impact → identify affected sectors → pull option chains → suggest hedges"
- "Find stocks with unusual options volume → cross-reference with news → build watchlist → set alerts"

### 9. IRA Account Trading
**What:** API supports Traditional and Roth IRA trading — rare for retail APIs.  
**Why it matters:** Dashboard currently only targets the brokerage account (5LF05438). IRA accounts could use the same strategies.  
**Implementation:**
- Account switcher in the dashboard sidebar
- Portfolio/orders views per account
- Strategy recommendations appropriate for IRA (no margin plays)

### 10. Doubled Rate Limits (Feb 2026)
**What:** API rate limits doubled from 5 req/sec to 10 req/sec.  
**Why it matters:** Enables more aggressive real-time monitoring, faster multi-symbol scans, and better signal detection.  
**Implementation:**
- Update signal monitor to scan more symbols per cycle
- Enable real-time multi-symbol quote streaming for the dashboard
- Faster option chain scanning for multi-leg strategy builders

### 11. Extended Hours Trading
**What:** Up to 16 hours/day equity trading, supported via API (EXTENDED session).  
**Why it matters:** Pre-market and after-hours where earnings moves happen. Dashboard supports it via the CORE/EXTENDED dropdown in orders, but no dedicated strategy.  
**Implementation:**
- Pre-market scanner: Check gap ups/downs before 9:30 AM
- After-hours earnings reaction: Auto-pull post-earnings quotes, compare to expected move
- Extended hours backtesting strategy

### 12. Greek Exposure Heatmap (Community Inspiration)
**What:** A Reddit user built an options intelligence dashboard with Perplexity + Public API featuring vol smile, OI visualization, and Greek heatmaps.  
**Why it matters:** Our options page shows chain data in a table, but no visual analytics.  
**Implementation:**
- Vol smile/skew chart by strike
- Open interest + volume bar chart
- Greek heatmap (Delta, Gamma, Theta, Vega across strikes)
- KPI cards: ATM IV, put/call ratio, straddle price, max pain, implied move

---

## Priority Matrix

| Opportunity | Effort | Impact | Priority |
|------------|--------|--------|----------|
| Scheduled cron workflows | Low (just prompts) | Very High | **Do First** |
| Options rebate tracker | Medium | High | **Do First** |
| Multi-leg order builder | Medium-High | Very High | **Do Next** |
| Cancel-and-replace orders | Low | Medium | **Do Next** |
| Bond trading page | Medium | Medium | **Do Next** |
| Crypto trading page | Medium | Medium | **Backlog** |
| TradingView webhooks | High | High | **Backlog** |
| Greek heatmap / vol visualizations | Medium | High | **Backlog** |
| Research-to-execution pipelines | Low (prompts) | Very High | **Do First** |
| IRA account switcher | Low-Medium | Medium | **Backlog** |
| Extended hours strategies | Medium | Medium | **Backlog** |
| Rate limit optimization | Low | Medium | **Backlog** |

---

## Sources
- Public.com API Documentation: https://public.com/api
- Public.com Perplexity Agent Skill: https://public.com/api/docs/templates/perplexity-agent-skill
- Public.com API Changelog: https://public.com/api/docs/changelog
- Public.com Options Rebate Program: https://public.com/options-rebate-explained
- Public.com Rebate Terms: https://public.com/disclosures/rebate-terms
- Public.com Options Trading Automation Webinar: https://www.youtube.com/watch?v=_-d3zhleWx4
- How to Trade with Perplexity Computer Guide: https://public.com/learn/how-to-trade-stocks-options-crypto-using-perplexity-computer
- Reddit: Options Dashboard built with Perplexity + Public API: https://www.reddit.com/r/ai_trading/comments/1s5cees/
