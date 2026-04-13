# Enso Trading Terminal — Capability Instructions
## Stocks & Options Only (Phase 1)

These are the exact instructions to give the Enso engine to add each new capability. Each section is one standalone feature. Add them one at a time, test, then move to the next.

---

## Capability 1: Scheduled Morning Briefing

**What it does:** Every weekday at 9:30 AM ET, Perplexity pulls your portfolio from Public.com and sends you a summary of overnight moves, position P&L, and any options expiring this week.

**Instruction to give Perplexity:**

> "Set up a recurring task: Every weekday at 9:30 AM Eastern, run the following workflow:
> 1. Pull my portfolio from Public.com (account 5LF05438)
> 2. Show total equity, buying power, and today's change
> 3. List my top 3 movers (biggest gains and losses)
> 4. Check if any options positions expire within the next 5 trading days
> 5. If expiring options exist, show current price vs. strike and suggest: hold, roll, or close
> 6. Send me a summary notification"

**How to verify it works:** The morning after setup, check your Perplexity notifications at 9:30 AM. You should see a clean portfolio summary.

**What this uses:** `get_portfolio.py`, `get_orders.py`, `get_quotes.py` from the Perplexity skill + Perplexity cron scheduling.

---

## Capability 2: Options Expiration Alert

**What it does:** Every weekday at 3:45 PM ET, checks if any options positions are expiring within 3 days and alerts you with action recommendations.

**Instruction to give Perplexity:**

> "Set up a recurring task: Every weekday at 3:45 PM Eastern:
> 1. Pull my portfolio and filter for options positions only
> 2. Check which options expire within the next 3 trading days
> 3. For each expiring option, show: symbol, strike, expiration, current price, intrinsic value, and whether it's ITM or OTM
> 4. Recommend one of: close now, roll to next expiration, or let expire
> 5. Send me a notification only if there are expiring options"

**How to verify:** Place or hold any short-dated option, and the alert should fire at 3:45 PM showing that position.

**What this uses:** `get_portfolio.py`, `get_quotes.py`, `get_option_chain.py` + Perplexity cron scheduling.

---

## Capability 3: Weekly Covered Call Scanner

**What it does:** Every Monday at 9:00 AM ET, scans your stock holdings and suggests covered call opportunities based on current options premiums.

**Instruction to give Perplexity:**

> "Set up a recurring task: Every Monday at 9:00 AM Eastern:
> 1. Pull my portfolio from Public.com and list all equity positions where I hold 100+ shares
> 2. For each qualifying position, pull the options chain for the nearest monthly expiration
> 3. Find OTM call options (5-10% above current price) with the highest premium
> 4. For each, show: symbol, current price, recommended strike, premium, % return if assigned, days to expiry
> 5. Send me the top 3 covered call opportunities ranked by premium yield"

**How to verify:** Next Monday, check for the notification. If you hold fewer than 100 shares of anything, it should tell you "No covered call candidates found."

**What this uses:** `get_portfolio.py`, `get_option_chain.py`, `get_option_expirations.py`, `get_quotes.py` + Perplexity cron scheduling.

---

## Capability 4: Stock Dip Alert with Options Protection

**What it does:** Monitors a watchlist of stocks. If any drops more than 5% in a single day, alerts you and shows protective put options.

**Instruction to give Perplexity:**

> "Set up a recurring task: Every weekday at 3:00 PM Eastern:
> 1. Get quotes for these symbols: NVDA, AAPL, TSLA, META, MSFT, AMZN, SPY, QQQ
> 2. Calculate today's % change for each
> 3. If any stock dropped more than 5% today:
>    a. Pull the options chain for the nearest weekly or monthly expiration
>    b. Find the ATM put option and the first OTM put option
>    c. Show: symbol, today's drop %, put strike, put premium, breakeven price
>    d. Send me a notification with the header 'Dip Alert'
> 4. If nothing dropped 5%+, do nothing (no notification)"

**How to verify:** This will only fire on big down days. You can test by temporarily lowering the threshold to 1% for one day.

**What this uses:** `get_quotes.py`, `get_option_chain.py` + Perplexity cron scheduling.

---

## Capability 5: Research-to-Trade Pipeline (On Demand)

**What it does:** A single prompt workflow where you name a stock, and Perplexity researches it, pulls live data, recommends a strategy, preflights it, and lets you execute — all in one conversation.

**Instruction to give Perplexity (use whenever you want):**

> "I want to evaluate a trade on [SYMBOL]. Do the following in order:
> 1. Research: What's the latest news, earnings date, analyst sentiment?
> 2. Pull a live quote from Public.com
> 3. Pull the options chain for the next 2 expiration dates
> 4. Based on the research and data, recommend ONE strategy (keep it simple — covered call, cash-secured put, or vertical spread)
> 5. Show me the exact contracts: symbol, strike, expiration, premium
> 6. Run a preflight check showing total cost, buying power impact, and max loss
> 7. Ask me if I want to place the trade — do NOT place it automatically"

**How to verify:** Walk through it once with a stock you're watching. The preflight should show real numbers from your account.

**What this uses:** Perplexity web search + `get_quotes.py`, `get_option_chain.py`, `get_option_expirations.py`, `preflight.py`, `place_order.py` from the skill.

---

## Capability 6: Options Rebate Tracker (On Demand)

**What it does:** Checks your monthly options trading volume and shows how close you are to the next rebate tier.

**Instruction to give Perplexity (use monthly):**

> "Check my options rebate status:
> 1. Pull my transaction history for this month from Public.com
> 2. Count the total number of options contracts traded
> 3. Show my current rebate tier based on this table:
>    - Tier 1: 0-999 contracts = $0.06/contract
>    - Tier 2: 1,000-4,999 contracts = $0.06/contract (API)
>    - Tier 3: 5,000-9,999 contracts = $0.06/contract (API)
>    - Tier 4: 10,000+ contracts = $0.10/contract (API)
> 4. Calculate total rebates earned this month
> 5. Show how many more contracts needed to reach the next tier"

**How to verify:** Compare the contract count against your Public.com trade history in the app.

**What this uses:** `get_history.py` from the skill.

---

## Capability 7: Cancel-and-Replace Orders (Dashboard Enhancement)

**What it does:** Adds an "Edit Order" button to the Orders page so you can modify active orders without canceling and re-placing.

**What needs to change in code:**
1. In `modules/api_client.py` — add a new method:
```python
def edit_order(self, account_id, order_id, updates):
    """Edit/replace an active order via PUT endpoint."""
    # Uses PUT /userapigateway/trading/{accountId}/order
    # Supports: options orders, crypto quantity orders, equity orders
    pass
```
2. In `pages/orders.py` — add an "Edit" button next to each active order that opens a modal to change price/quantity.

**Instruction for Perplexity (to build it):**

> "In the Enso Trading Terminal repo, add cancel-and-replace order support:
> 1. Add an edit_order() method to modules/api_client.py that sends a PUT request to edit an active order
> 2. On the Orders page, add an Edit button next to each active order
> 3. Clicking Edit opens a modal where I can change limit price or quantity
> 4. The modal should show current order details and preflight the new values before submitting"

**What this uses:** Public.com API PUT endpoint (added February/March 2026 per [changelog](https://public.com/api/docs/changelog)).

---

## Capability 8: Multi-Leg Options Builder (Dashboard Enhancement)

**What it does:** Adds a strategy builder to the Orders page for placing multi-leg options trades (spreads, iron condors, straddles) as a single order.

**What needs to change in code:**
1. In `modules/api_client.py` — add multi-leg preflight and order methods using `MultilegOrderRequest` and `PreflightMultiLegRequest` from the SDK.
2. New UI section on Orders page (or new page `pages/strategy_builder.py`) with:
   - Strategy template dropdown: Bull Call Spread, Bear Put Spread, Iron Condor, Straddle, Covered Call
   - Auto-populates legs based on template + user's symbol/expiration selection
   - Multi-leg preflight showing net debit/credit, max profit, max loss
   - Single "Place Strategy" button that executes all legs together

**Instruction for Perplexity (to build it):**

> "In the Enso Trading Terminal repo, add a multi-leg options strategy builder:
> 1. Add multi_leg_preflight() and place_multi_leg_order() methods to api_client.py using MultilegOrderRequest from the SDK
> 2. Create a new section on the Orders page with a strategy template dropdown
> 3. Templates: Bull Call Spread, Bear Put Spread, Iron Condor, Long Straddle, Covered Call
> 4. When I select a template and enter symbol + expiration, auto-fill the legs from the options chain
> 5. Show a preflight summary: net debit/credit, max loss, max profit, breakeven(s)
> 6. Add a Place Strategy button that submits all legs as one multi-leg order"

**What this uses:** `MultilegOrderRequest`, `PreflightMultiLegRequest`, `OrderLegRequest`, `LegInstrument` from `public_api_sdk` (already documented in the options-automation-library.md).

---

## Implementation Order

| Step | Capability | Type | Time to Add |
|------|-----------|------|-------------|
| 1 | Morning Briefing | Perplexity prompt | 5 minutes |
| 2 | Expiration Alert | Perplexity prompt | 5 minutes |
| 3 | Research-to-Trade Pipeline | Perplexity prompt | Use anytime |
| 4 | Stock Dip Alert | Perplexity prompt | 5 minutes |
| 5 | Weekly Covered Call Scanner | Perplexity prompt | 5 minutes |
| 6 | Rebate Tracker | Perplexity prompt | Use anytime |
| 7 | Cancel-and-Replace Orders | Code change | 1-2 hours |
| 8 | Multi-Leg Strategy Builder | Code change | 3-4 hours |

**Steps 1-6 require zero code changes.** They use the existing Perplexity skill scripts that are already working. You just give the prompt and Perplexity sets it up.

**Steps 7-8 require code changes** to the dashboard. These can be done in a future session.

---

## Sources
- Public.com API: https://public.com/api
- Public.com Perplexity Agent Skill Setup: https://public.com/api/docs/templates/perplexity-agent-skill
- Public.com API Changelog (cancel-replace, bonds, rate limits): https://public.com/api/docs/changelog
- Public.com Options Rebate Terms: https://public.com/disclosures/rebate-terms
- Public.com Options Rebate Tiers: https://public.com/options-rebate-explained
- Options Automation Library: enso-build/skills/user/publicdotcom-perplexity-skill/options-automation-library.md
- SDK Reference: public_api_sdk v0.1.10 (publicdotcom-py)
