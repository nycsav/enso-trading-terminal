# Enso Institutional Options Strategy Guide
## How to Test and Use Each Strategy — Plain English Edition

---

## How to Read This Guide

**Who this is for:** A financially literate solo operator who understands how options work, knows what a P&L is, has used a trading platform before, and wants to implement serious, institutional-quality strategies — but isn't a quant and doesn't have a PhD in math.

**What this covers:** Ten options strategies, ordered by priority. For each one, you get a plain-English explanation of what it does, why it works, how to test it before putting real money on it, what success actually looks like, and when to walk away.

**What you need before starting anything:**
- Python installed, with `yfinance`, `pandas`, `numpy`, and `scipy` available
- A Polygon.io API key (free tier works for early testing; paid tier needed for full options chains)
- A brokerage account with options approval that lets you paper trade (Thinkorswim, Tastytrade, or Interactive Brokers all work)
- A simple spreadsheet or Notion page to log trades — discipline about logging is what separates systematic traders from gamblers
- Roughly $25,000–$50,000 in capital before going live with anything beyond the baseline strategy. Most of these strategies require defined-risk structures and margin; some require significantly more.

---

### The Build Phases

This guide uses five phases to sequence the work. The phases exist because some strategies depend on infrastructure you haven't built yet. Don't skip ahead.

| Phase | Label | What It Means |
|---|---|---|
| Baseline | Now | Already running in Enso. The S/R + vol filter layer. |
| Phase 1 | Near-term | Can be built with yfinance + Polygon. No exotic data needed. |
| Phase 2 | 3–6 months | Needs specialized data sources (GEX, intraday OI, VIX futures). |
| Phase 3 | 6–12 months | Multi-asset data pipelines, LLM integration at scale. |
| Phase 4 | 12+ months | Requires serious capital, execution infrastructure, multiple options legs. |

Build in order. Phase 1 strategies validate your infrastructure and your discipline. If you can't make Phase 1 work cleanly, Phase 4 will definitely fail.

---

### The Scoring Dimensions

Each strategy in this guide has four scores, all out of 10:

- **Edge Potential:** How strong the theoretical edge is, based on academic research and institutional practice. A 9+ means this is a well-documented, persistent edge. A 6 means it's real but thinner.
- **Difficulty:** How hard it is to implement correctly — Low, Medium, High, or Expert. Difficulty is about implementation, not about understanding. Some easy-to-understand ideas are hard to execute well.
- **Enso Fit:** How naturally this connects to the existing Enso Trading Terminal infrastructure. A 9+ means most of the plumbing is already there. A 5 means you're starting from scratch.
- **AI Leverage:** How much an LLM or AI layer can add on top of the mechanical strategy. High AI leverage means regime labeling, signal fusion, and narrative parsing can materially improve results.

---

## Quick Reference: Strategy Priority Table

| Rank | Strategy | Difficulty | Phase | Verdict |
|---|---|---|---|---|
| 1 | IV vs RV Gap Monitor | Medium | Phase 1 | Start now — highest edge, buildable immediately |
| 2 | Dealer Gamma Regime | High | Phase 2 | Build second — powerful, but needs GEX data first |
| 3 | Skew Surface Trading | Expert | Phase 3 | Defer — requires full vol surface infrastructure |
| 4 | Dispersion / Correlation Trades | Expert | Phase 4 | Defer — significant capital and execution complexity |
| 5 | Event Vol Strangle | Medium | Phase 1 | Start now — quick win, clear signals, manageable risk |
| 6 | Term Structure Carry | Medium | Phase 2 | Build alongside Dealer Gamma — shares data sources |
| 7 | Pinning / 0DTE Dynamics | High | Phase 2 | Phase 2 — needs intraday OI data, real-time capable system |
| 8 | Vol Risk Premium Harvest | Medium | Phase 1 | Start now — natural extension of IV vs RV monitor |
| 9 | Cross-Asset Signal Fusion | High | Phase 3 | Defer — highest AI leverage, but multi-source pipeline required |
| 10 | S/R + Vol Filter Overlay | Low | Baseline | Live now — upgrade the vol filters before building anything else |

---

## Strategy 10: S/R + Vol Filter Overlay

**Difficulty:** Low | **Phase:** Baseline | **Edge Potential:** 6.2/10 | **Enso Fit:** 9.2/10

### What This Strategy Does

This is the strategy already running in Enso. You identify support and resistance levels — price zones where buyers and sellers historically cluster — and trade bounces or breakouts from those zones. The upgrade is adding volatility context as a filter: you only take the trade when the vol environment agrees with the setup.

Think of it this way: a support level is like a doorstep. But whether you walk through depends on whether there's a storm outside (high fear, wide spreads, wild swings) or calm weather (low vol, mean-reverting behavior). The vol filter is the weather check.

### Why It Works (The Edge)

Pure support and resistance trading barely has edge on its own anymore — too many people do it, and algos know where the obvious levels are. But filtered S/R works because you're removing bad-weather trades. Options markets embed real information about expected movement; when IV is high relative to what markets actually move (RV), it often signals uncertainty or fear. Taking mean-reversion entries in those conditions usually means getting eaten alive. Filtering for the right vol regime removes a large chunk of the losers without removing many of the winners.

The person on the other side of a good S/R trade (when vol is calm) is often a momentum chaser or a panic seller — they're right about direction sometimes but wrong about timing. You're providing liquidity at a sensible price.

### What You Need Before You Start

- **Data:** yfinance for price history and S/R calculation (already integrated into Enso). You'll need IV data from options chains via Polygon to add the vol filter.
- **Tools:** Enso itself, plus a Polygon API key to pull ATM implied volatility for each ticker.
- **Capital:** This works at almost any size. Options vol filters don't require you to trade options — you can apply them to stock or futures entries.
- **Knowledge:** You need to understand how to calculate 20-day historical volatility (HV20) and how to pull ATM IV from an options chain. Both are covered in the IV vs RV section below.

### Step-by-Step: How to Test This Strategy

1. **Pull one year of daily OHLCV data** for 5–10 liquid tickers you typically trade, using `yfinance`. Keep it to liquid names — at least $1B average daily volume.

2. **Identify your S/R levels programmatically.** The simplest approach: mark price zones where the stock reversed at least twice in 90 days, with at least a 1% move after the touch. You can use a rolling pivot-point script or do this visually in Enso and log the levels manually.

3. **Calculate 20-day realized volatility (HV20).** In Python: take the log returns of daily closes (`np.log(close / close.shift(1))`), compute a 20-day rolling standard deviation, then multiply by `sqrt(252)` to annualize. This gives you the "how much did this stock actually move" number.

4. **Pull the ATM implied volatility** for each ticker from Polygon's options endpoint. Look for the call and put closest to the current price with 20–30 days to expiration. Average their IVs. This is your "what the market expects" number.

5. **Build the filter.** For Version A, log every time price touches a support or resistance level. For Version B, apply the rule: only take the trade if IV is not more than 20% above HV20 (i.e., the options market isn't screaming that something is about to happen). Track both versions.

6. **Run both versions across the full year.** Count the trades, calculate average P&L per trade, win rate, and max drawdown for each version. Use a fixed position size (e.g., 1% of capital per trade) to keep the comparison apples-to-apples.

7. **Check whether the filter actually helped.** If Version B has a higher win rate and lower max drawdown even with fewer trades, the filter is working. If removing the high-IV trades eliminated most of your winners, reconsider the threshold.

### Step-by-Step: How to Paper Trade This Strategy

1. **Set up a daily review routine.** Each morning before the open, check your S/R levels for the next session. Note which levels are within 0.5% of current price.

2. **Check the vol filter.** Pull the ATM IV for those tickers and compare to their HV20. Log the ratio. If IV/HV > 1.3 (meaning implied vol is 30% above what the stock has actually been moving), flag the trade as "elevated risk" and either skip it or reduce size by half.

3. **Log every trade in a spreadsheet:** entry price, level hit, vol filter pass/fail, target, stop, outcome. The log is not optional — it's the only way to know if you're improving.

4. **Paper trade for at least 30 trades before drawing conclusions.** Market conditions change, so 30 trades over 60–90 days is the minimum meaningful sample. With fewer than 20 trades, any result is noise.

5. **After 30 trades, calculate:** win rate, average win, average loss, and whether "filter pass" trades outperformed "filter fail" trades. If they don't differ meaningfully, you either have the wrong filter threshold or the edge isn't there on your specific names.

### What Success Looks Like

- **Win rate:** 52–62% (S/R is mean-reversion at heart; you're not looking for massive winners, just consistent small edges)
- **Average win-to-loss ratio:** 1:1 to 1.5:1 (bigger is fine, but don't force it)
- **Sharpe ratio target:** 0.8–1.2 (this is a modest strategy, not a high-Sharpe machine)
- **Max drawdown:** Should not exceed 3–4x your average trade size. If you're losing on 15+ consecutive trades, something is wrong structurally.
- **Minimum sample for confidence:** 40–50 trades

### Red Flags and When to Stop

- **Win rate drops below 45% for 30 consecutive trades.** That's not variance; the environment has shifted or your levels are stale.
- **You're taking the trade and the stock gaps through your S/R level on open more than 30% of the time.** Gaps mean your entry prices aren't achievable — the model works on close-to-close assumptions, and intraday reality differs.
- **High-IV filter trades are outperforming low-IV trades.** This means you're trading the wrong filter direction; go back to the data and rethink the threshold.
- **Kill switch:** If you lose more than 10% of your capital in this strategy in a single month, stop immediately and audit your level identification methodology.

### When NOT to Use This Strategy

- Earnings week for the underlying — IV is high for a reason, and S/R levels become unreliable when stocks gap 10% overnight.
- Broad market VIX above 35. In high-fear regimes, support levels don't hold because forced selling ignores price.
- When you're also running the IV vs RV Monitor on the same tickers in the same direction — the signals can be redundant or contradictory.

### Enso Integration Notes

This strategy is already live. The next upgrade is adding the IV/HV filter display directly into the Enso S/R dashboard — show the current IV/HV ratio alongside each level, and color-code levels "green" (vol is calm, trade with normal size) or "yellow/red" (vol is elevated, reduce size or skip). The vol data feed from Polygon is the only infrastructure addition needed.

---

## Strategy 1: IV vs RV Gap Monitor

**Difficulty:** Medium | **Phase:** Phase 1 | **Edge Potential:** 9.2/10 | **Enso Fit:** 9.0/10

### What This Strategy Does

Options prices contain a built-in estimate of how much a stock will move over the next month. That estimate — implied volatility (IV) — is usually higher than what the stock actually ends up moving (realized volatility, or RV). This strategy systematically identifies when that gap is unusually large or unusually small, then bets accordingly: sell premium when IV is rich, buy premium when IV is cheap.

Think of it like selling storm insurance. If a weather model says there's a 60% chance of a storm, but you've checked the satellite data and there's actually only a 30% chance, you want to be the insurance seller, not the buyer.

### Why It Works (The Edge)

The IV-RV gap is one of the most well-documented phenomena in all of finance. Academic research going back decades shows that implied volatility systematically overstates subsequent realized volatility — not always, not by a fixed amount, but on average and persistently.

Why does this persist? Because the people buying options are mostly hedgers and retail speculators who are buying *protection*, not betting on volatility being fairly priced. A fund manager buying SPY puts to protect their portfolio doesn't care that they're overpaying for vol — they need the hedge regardless. That structural demand inflates the price of options above fair value, and patient sellers earn the premium over time.

The person on the other side of your short-vol trade is often a hedger who *must* buy regardless of price, or a retail speculator who overestimates how much the stock will move.

### What You Need Before You Start

- **Data:** yfinance for historical prices and HV calculation. Polygon options chain data for IV (specifically, ATM IV at the 20–30 DTE expiration).
- **Tools:** Python with `pandas`, `numpy`, and `scipy`. A spreadsheet to log the IV/HV readings and trade outcomes.
- **Capital:** Minimum $20,000 to trade credit spreads with meaningful size. Naked short options require much more (and are not recommended for most operators).
- **Knowledge:** You need to understand what a credit spread and a debit spread are, how to read an options chain, and how to calculate HV20. All of these are defined in the Glossary at the end of this guide.

### Step-by-Step: How to Test This Strategy

1. **Pull 2 years of daily close data** for a liquid, optionable underlying — SPY, QQQ, or a large-cap stock with high options volume. Use `yfinance`: `df = yf.download('SPY', period='2y')`.

2. **Calculate HV20** for every trading day: `df['returns'] = np.log(df['Close'] / df['Close'].shift(1))` then `df['HV20'] = df['returns'].rolling(20).std() * np.sqrt(252)`. This gives you a percentage — the annualized realized vol.

3. **Pull historical ATM IV** from Polygon for the same period. Specifically, grab the IV of the at-the-money call and put with 20–30 days to expiration, for each trading day. This is your "what the market was expecting" number. Note: Polygon's historical options data goes back several years; you'll need a paid tier for full chain history.

4. **Calculate the IV/HV ratio** for each day. A ratio above 1.3 means options are "rich" — the market is pricing in 30% more movement than the stock has actually been doing. A ratio below 0.85 means options are "cheap."

5. **Bucket trade entries.** For every day where IV/HV > 1.3, simulate a short-premium trade: a 30-delta credit spread in the direction of the current trend (or delta-neutral iron condor on an index). Record the entry IV, the spread width, the credit received, and whether the spread expired worthless or hit the loss limit.

6. **Do the same for cheap IV days** (IV/HV < 0.85): simulate buying a debit spread and track whether the realized move exceeded what you paid for.

7. **Compare the two buckets** plus a control group (neutral IV days). Your hypothesis: the rich-IV bucket should show consistently higher premium capture rates; the cheap-IV bucket should show better debit spread performance. If that pattern doesn't appear in the historical data, your thresholds need adjustment or the edge is not present in your chosen underlyings.

### Step-by-Step: How to Paper Trade This Strategy

1. **Every Monday morning, run the IV/HV script** on your target list (start with SPY, QQQ, IWM, and 5–10 liquid single names). Record the ratios in a spreadsheet.

2. **If IV/HV > 1.3 on an index ETF:** Simulate selling an iron condor — a credit spread above and below the current price, each wing 15–20 points wide on SPY, targeting 30-delta strikes. Log the premium collected, the break-even levels, and the max loss.

3. **Close the paper trade at 50% of max profit** (the premium collected drops to half its original value) or at expiration, whichever comes first. Set a mental stop at 2x the premium collected.

4. **Paper trade for at least 20 cycles** (roughly 5 months of weekly or bi-weekly trades). With fewer cycles, variance swamps signal.

5. **After 20 cycles, calculate:** total premium collected, total losses, net P&L, and win rate. The most important number is whether you collected more premium than you lost across the cycle, not whether any individual trade was right or wrong.

### What Success Looks Like

- **Win rate:** 60–70% on credit spreads (you win most of the time by a little, you lose occasionally by more — that's normal and expected)
- **Average P&L per trade:** Positive expectancy of 5–15% of premium collected per cycle
- **Sharpe ratio target:** 1.0–1.5 over a full year
- **Max drawdown tolerance:** No single loss should exceed 3x your average winning trade
- **Minimum sample for confidence:** 30 trades

### Red Flags and When to Stop

- **Win rate below 50% on the rich-IV bucket after 30 trades.** The edge requires the rich-IV condition to outperform neutral; if it doesn't, your IV calculation is wrong or the underlying is not a good candidate.
- **You're losing money even when IV/HV is at 1.5+.** This usually means a crisis regime — the options are pricing in something real, and your mechanical signal is lying to you. Check the broader market: if VIX is above 30, pull back significantly.
- **Spreads keep getting blown through.** If the stock is regularly moving through your spread strikes, you're sizing the spread too narrow or picking underlyings that move too fast.
- **Kill switch:** If your account drops 15% from this strategy alone over any rolling 60-day period, stop, audit, and reassess.

### When NOT to Use This Strategy

- Do not sell premium ahead of known catalysts (earnings, FDA decisions, major macro events). The IV is high *because* something is about to happen, not because options are mispriced.
- Do not use this strategy when VIX is above 35 and rising. You're likely in a crisis regime where IV stays elevated or goes higher, and the mean-reversion assumption breaks down.
- Don't run this simultaneously with the VRP Harvest strategy (Strategy 8) on the same underlyings — they're doing the same thing, and doubling up doesn't add diversification, it adds concentration.

### Enso Integration Notes

This is the highest-priority Phase 1 build. The HV calculation already works via yfinance. The missing piece is a module that pulls ATM IV from Polygon, calculates the ratio, and displays it on a dashboard panel showing which tickers are currently "rich," "neutral," or "cheap." The trade logging can connect to Enso's existing trade journal infrastructure. Estimated build: 1–2 weeks for the data pipeline, another week for the UI panel.

---

## Strategy 5: Event Vol Strangle

**Difficulty:** Medium | **Phase:** Phase 1 | **Edge Potential:** 8.2/10 | **Enso Fit:** 8.5/10

### What This Strategy Does

Before earnings, FDA approvals, FOMC meetings, and other major events, options prices spike because everyone knows something big is coming but nobody knows what. This strategy systematically asks: is the options market pricing that event correctly? Sometimes it's overpriced (selling strangles is right), sometimes it's underpriced (buying strangles is right). The goal is to have a repeatable process for figuring out which.

A strangle is simply buying (or selling) both a call and a put on the same stock, at different strikes, at the same expiration. If you buy it, you profit from a big move. If you sell it, you profit from a small move.

### Why It Works (The Edge)

Retail traders systematically overpay for earnings protection. They're buying calls because they think the stock will moon, or puts because they're scared, but they're not thinking carefully about what move is already priced in. Institutional options desks know this and structure their event-vol selling accordingly.

There's also a structural edge from the post-event vol crush: after earnings, IV collapses rapidly. If you're short premium going into earnings, you don't even need to be right about direction — you just need the stock not to move as much as the options market priced in.

The person on the other side of a short-event strangle is often a retail momentum chaser who bought options because the stock has been in the news, without checking whether those options were already expensive relative to the expected move.

### What You Need Before You Start

- **Data:** Earnings calendars (available from multiple free sources: Earnings Whispers, Benzinga, or via `yfinance`'s `get_earnings_dates()` method). Options chains via Polygon for IV readings around each event.
- **Tools:** Python, Polygon API, a spreadsheet for logging expected moves vs actual moves.
- **Capital:** Minimum $30,000 to sell strangles in liquid names with any kind of reasonable sizing. Defined-risk structures (iron condors instead of naked strangles) are strongly recommended and reduce the capital requirement.
- **Knowledge:** Understand the "expected move formula" — the straddle price divided by the stock price gives you an approximate 1-standard-deviation expected move for the event. This is the key number the whole strategy revolves around.

### Step-by-Step: How to Test This Strategy

1. **Build an event database.** Download 2 years of earnings dates for 30–50 liquid names using a combination of yfinance and manual verification. Include the date, the underlying, and the pre-event closing price.

2. **For each event, calculate the expected move.** The week before earnings, look up the price of the at-the-money straddle (call + put at the same strike, same expiration) expiring right after earnings. Divide by the stock price. Example: if AAPL is at $200 and the straddle costs $10, the expected move is 5%.

3. **Record the actual move.** From the day before earnings close to the day after earnings close, how much did the stock actually move? Use absolute value — you don't care about direction, only magnitude.

4. **Calculate the "implied vs actual" ratio** for each event: actual move / expected move. If this is consistently below 1.0 (say, 0.75 on average), the market tends to overprice event vol. If it's above 1.0, the market underprice it. Your historical dataset will show which direction the bias runs for your universe.

5. **Test a simple rule:** Only sell event strangles when the expected move is in the top 30% of its historical range for that stock (i.e., the market is pricing in an unusually large event). This is a filter for selling richness, not just selling blindly.

6. **Simulate the trades.** For each qualifying event, simulate selling a strangle at the strikes just outside the expected move (so if the expected move is 5%, sell the 5.5% OTM call and put). Track premium collected, the final stock move, and whether the strangle expired profitable.

7. **Separate the results** into "sold into high expected move" and "sold into normal expected move." Confirm that your filter adds value.

### Step-by-Step: How to Paper Trade This Strategy

1. **Every Sunday, pull next week's earnings calendar** using Benzinga's free calendar or Earnings Whispers. Identify all events in your universe (your 30–50 liquid names).

2. **For each event, calculate the expected move** using Monday's or Tuesday's straddle price. Log it in your trade journal.

3. **Apply your filter:** only trade events where the expected move is historically elevated for that stock. If AAPL typically has a 4% expected move but this quarter it's 7%, that's a candidate for selling.

4. **Paper trade the strangle or iron condor** by logging the entry strikes, premium, and expiration. Close it the morning after earnings or at 50% of max profit.

5. **Paper trade at least 20–30 events** before going live. Earnings happen quarterly per name, so 30 events across 30 names can accumulate in a few months if you cover enough names.

### What Success Looks Like

- **Win rate:** 60–70% on short event strangles (you're selling premium, so you should win the majority of trades)
- **Average premium captured per trade:** 40–60% of max profit (you won't always capture 100%, but averaging 50% is solid)
- **Sharpe ratio target:** 1.0–1.5 over a full year
- **Key metric to watch:** The "realized/expected move ratio" across your universe. If it averages below 0.85, you have persistent edge in selling. If it's above 1.0, your universe is full of underpriced events.
- **Minimum sample for confidence:** 25 events

### Red Flags and When to Stop

- **Three consecutive events where the stock moved 2x or more the expected move.** You're either picking the wrong stocks or there's a broad market regime shift amplifying individual earnings reactions.
- **Implied vol isn't collapsing after earnings.** The vol crush is part of the thesis; if IV stays elevated post-earnings, something unusual is happening in that name's options market.
- **Your universe is too narrow.** If you're only trading 5–6 names, one bad earnings season wipes you out. Diversify across at least 15–20 events per quarter.
- **Kill switch:** If a single event trade costs you more than 5% of your total account, your position sizing is too aggressive. Scale down immediately.

### When NOT to Use This Strategy

- Don't sell event strangles on meme stocks or heavily shorted names — the actual moves can be many multiples of the implied move, and no model protects you there.
- Avoid binary events (FDA decisions, merger votes) where the outcome is truly binary and the move is either zero or 30%. These are not well-modeled by straddle pricing.
- Don't combine this with aggressive short premium positions in the same names from the IV vs RV strategy — you're doubling your short-vol exposure at exactly the moment the stock is most likely to make a large move.

### Enso Integration Notes

The earnings calendar module is ready to build. Benzinga has a free API tier that gives you the next 7–14 days of earnings with confirmed dates. The expected move calculation is a few lines of Python against a Polygon options chain. The ideal Enso display: a pre-earnings dashboard that shows each upcoming event, the current expected move, the historical average expected move, and the realized/expected ratio over the last 4–8 quarters. This lets you assess richness at a glance without running the calculation manually.

---

## Strategy 8: Vol Risk Premium Harvest

**Difficulty:** Medium | **Phase:** Phase 1 | **Edge Potential:** 7.2/10 | **Enso Fit:** 7.0/10

### What This Strategy Does

This is the systematic, rules-based version of short premium selling. Instead of picking spots intuitively, you have explicit filters — a checklist — that must be satisfied before you sell any options. When all the boxes are checked, you put on a defined-risk short-vol position (a credit spread or iron condor). When they aren't, you do nothing.

Think of it like a pilot's pre-flight checklist. You don't take off just because you feel good about the weather. You check instruments, fuel, wind, and traffic. Here, the instruments are IV/RV ratio, market regime, skew shape, and position concentration.

### Why It Works (The Edge)

The volatility risk premium (VRP) is the difference between what options cost and what markets actually move. Decades of academic research confirm that this gap is persistent and positive — on average, across most markets and most time periods, options are slightly overpriced relative to subsequent realized vol. The challenge is that this edge has catastrophic tail risk: in a crash, short premium positions lose enormous amounts very quickly.

The filter-based approach addresses this: you only harvest the VRP when conditions are favorable (calm regime, IV meaningfully above RV, no major catalysts) and you stay out when conditions are hostile. This doesn't eliminate tail risk, but it reduces the frequency of catastrophic trades.

### What You Need Before You Start

- **Data:** The same IV and HV data you built for the IV vs RV Monitor. You'll add one more signal: the skew reading (the difference in IV between OTM puts and OTM calls, which signals how nervous the market is about downside).
- **Tools:** Python + Polygon, plus your credit spread execution at your broker.
- **Capital:** $30,000–$50,000 minimum to run meaningful defined-risk structures across multiple names. Never sell naked options with this system.
- **Knowledge:** You need to understand how credit spreads work, what your max loss is on each structure, and how to read the options chain to select strikes.

### Step-by-Step: How to Test This Strategy

1. **Define your filter rules explicitly.** Write them down before you look at any data. Example rules:
   - IV/HV20 ratio > 1.25 (options are at least 25% richer than recent realized vol)
   - VIX is below 25 (broad market not in crisis)
   - The 25-delta put skew is not in the top 20% of its 1-year range (not screaming danger)
   - No earnings or major events within 14 days for that name
   - No more than 3 positions open at once

2. **Pull 2 years of historical data** and label each day as "filter pass" or "filter fail" for each ticker in your universe. You'll find that the filter clears maybe 20–40% of days — that's fine. You're looking for quality, not quantity.

3. **Backtest only the filter-pass days.** Simulate selling a credit spread on filter-pass entry dates: a put spread 10–15% below the current price with 20–30 DTE, collecting at least $0.50 per spread (enough to cover commissions). Track the outcomes.

4. **Test the filter's value.** Run the same backtest with all days (no filter) and compare. If the filter-pass days have meaningfully better results (higher win rate, lower drawdown, better Sharpe), the filter is doing its job.

5. **Stress-test against crisis periods.** Look at 2018 (Q4 selloff), 2020 (March COVID crash), and 2022 (rate spike). How would filter-pass trades have performed? The honest answer is: badly during the acute phase of those events, but your VIX filter should have kept you mostly out of the worst days.

6. **Adjust the filter based on what you find.** Don't tune too aggressively — you're looking for broad conditions where the edge is clear, not trying to find perfect parameters that happen to work only in your test window.

### Step-by-Step: How to Paper Trade This Strategy

1. **Every Monday, run your filter checklist** across your target universe. In your spreadsheet, mark each ticker as pass/fail on each criterion.

2. **For filter-pass names, identify the structure.** Select a put credit spread 10–15% OTM with 21–30 DTE. Log the entry strikes, premium received, and max loss.

3. **Set your management rules in advance:** close at 50% of max profit, or close if the position loses 2x the premium received (i.e., the spread is now worth 3x what you collected).

4. **Paper trade for at least 30 positions** across a minimum of 3 months. Markets cycle; a 3-month sample captures at least some variation in regime.

5. **Review your filter performance.** Did filter-pass trades outperform random trades? Was the Sharpe ratio positive? Were your drawdowns manageable? Answer these honestly before going live.

### What Success Looks Like

- **Win rate:** 65–75% on credit spreads (you're selling far OTM — most of the time, the stock doesn't get there)
- **Average return per trade:** 5–15% return on risk
- **Sharpe ratio target:** 0.8–1.2 (VRP harvesting isn't a high-Sharpe strategy by itself — it earns steady small returns with occasional large losses)
- **Max drawdown tolerance:** 15–20% of capital allocated to this strategy over any 6-month period
- **Minimum sample for confidence:** 30 trades

### Red Flags and When to Stop

- **You're winning most trades but still losing money overall.** This means your average loss is much larger than your average win — check your management rules and stop-loss discipline.
- **Your filter is never passing.** If your criteria are too strict (e.g., requiring IV/HV > 1.5 in a low-vol environment), you'll have no trades. Calibrate thresholds to your historical data.
- **VIX keeps rising through your positions.** If VIX moves from 20 to 30 while you have credit spreads open, the underlying vol regime has changed. Tighten your stops and reduce size.
- **Kill switch:** If you lose more than 3x the typical premium collected on a single trade, something went wrong. Either the position size was too large or the filter let a bad setup through. Audit it immediately.

### When NOT to Use This Strategy

- Any environment where VIX is above 28 and trending higher — you're selling into rising fear, which is exactly backwards.
- In the two weeks before expiration for individual stock options around earnings — theta is nice, but gap risk from earnings is catastrophic for short spreads.
- Don't stack this with the IV vs RV Monitor strategy (Strategy 1) on the same names — they're both short-vol, and doubling up means doubling your drawdown if the market spikes.

### Enso Integration Notes

This strategy is a direct extension of the IV vs RV Monitor. Once the IV/HV ratio dashboard is built, adding the VRP filter logic is a checklist layer on top of the existing signal. Enso could display a simple "VRP Scorecard" — five criteria, each showing green or red — alongside each ticker's ratio. When all five are green, the trade is live. The position management rules (50% profit, 2x loss) could also be automated through Enso's alert system.

---

## Strategy 2: Dealer Gamma Regime

**Difficulty:** High | **Phase:** Phase 2 | **Edge Potential:** 9.0/10 | **Enso Fit:** 8.0/10

### What This Strategy Does

Options dealers — the market makers who sell options to everyone else — must hedge their exposure constantly. When they're net long gamma (meaning they've sold more options than they've bought, and they're net hedging by selling into rallies and buying into dips), markets tend to be calmer and mean-reverting. When they're net short gamma, the opposite happens: the market becomes twitchy and directional moves accelerate.

Gamma is the rate at which a delta changes. Think of delta as how much your options position moves when the stock moves $1. Gamma is how fast that delta is changing. When dealers are short gamma, they have to buy more as prices rise and sell more as prices fall — which amplifies moves. When they're long gamma, they do the opposite — which dampens moves.

This strategy classifies which regime you're in and adjusts your trading approach accordingly.

### Why It Works (The Edge)

Dealer hedging flows are mechanical. They're not based on views about the market — they're math-driven risk management. This makes them predictable, at least directionally. During periods of strong positive dealer gamma, you can confidently fade intraday moves back toward key levels. During negative gamma periods, you expect trends to persist and avoid fighting momentum.

The person on the other side isn't really a person — it's the mechanical behavior of dealers managing their books. You're not outsmarting a human; you're understanding a structural flow and positioning around it.

### What You Need Before You Start

- **Data:** GEX (Gamma Exposure) data from SpotGamma or SqueezeMetrics. This is specialized and costs $30–$100/month depending on the tier. There is no good free substitute. Free approximations from public OI data are much noisier.
- **Tools:** SpotGamma's API or manual data download, Python for regime classification.
- **Capital:** This is a regime filter, not a standalone trading strategy. It improves other strategies by telling you which playbook to use. Capital requirements depend on what you're trading through the regime lens.
- **Knowledge:** You need to understand GEX conceptually (covered in the Glossary), and how to convert a GEX reading into an actionable regime label.

### Step-by-Step: How to Test This Strategy

1. **Subscribe to SpotGamma or SqueezeMetrics** at the minimum tier that gives you daily GEX readings for SPX/SPY. Download 1–2 years of historical GEX data.

2. **Build regime labels.** Define "positive gamma" as days where SPX GEX is above zero (typically above the gamma flip level), and "negative gamma" as days where it's below zero. SpotGamma publishes the gamma flip level explicitly.

3. **Describe market behavior in each regime.** For positive gamma days, calculate: average intraday range (ATR-style), average absolute return, frequency of trending vs mean-reverting days. Repeat for negative gamma days. You should see a meaningful difference: positive gamma days have smaller ranges and more mean reversion.

4. **Test a simple strategy in each regime.** For positive gamma: fade the morning move (if the market is up 0.7% by 11am, short a small amount expecting mean reversion). For negative gamma: ride the trend (if the market is up 0.7% by 11am, go with it). Backtest both rules separately in each regime.

5. **Confirm statistical significance.** Run a t-test (or just check the 95% confidence interval) on whether the mean return of your positive-gamma strategy differs meaningfully from the negative-gamma strategy. Your results will vary but the academic literature is very clear: regime matters.

6. **Add this as a filter.** Don't run the test in isolation — layer the regime label onto the strategies you're already testing. Does IV vs RV edge get better when you only trade it in positive gamma regimes? That's the real test.

### Step-by-Step: How to Paper Trade This Strategy

1. **Every morning before market open,** check the SpotGamma dashboard for the current GEX regime label (positive or negative) and the gamma flip level (the price where dealers' hedging behavior changes sign).

2. **Classify the session.** Log the regime label and the day's opening conditions in your journal.

3. **Apply different playbooks.** In positive gamma: favor mean-reversion trades, tighter stops, expect volatility to be dampened. In negative gamma: favor momentum continuation, wider stops, expect moves to be larger than usual.

4. **Track regime accuracy.** Each day, note whether the market behaved as the regime suggested. After 60 trading days, calculate: what percentage of positive-gamma days were actually mean-reverting? What percentage of negative-gamma days showed directional persistence?

5. **Paper trade for 2–3 months** before incorporating this into live decisions. You need to observe the regime working across multiple market cycles.

### What Success Looks Like

- **Regime accuracy:** 60–70% of days should behave as the regime suggests (some days won't — that's noise)
- **Strategy improvement:** Your IV vs RV or S/R strategy should show 10–20% better Sharpe when filtered through the gamma regime
- **Minimum sample for confidence:** 60 trading days

### Red Flags and When to Stop

- **Regime labels aren't predicting behavior at all.** If positive and negative gamma days look statistically identical in your data, your GEX source is noisy or the regime definition is wrong.
- **The gamma flip level keeps getting violated.** If the market repeatedly breaks through the gamma flip without a behavior change, either the data is lagged or the regime is being overridden by a larger macro force (e.g., a Fed announcement).
- **Kill switch:** This is a filter, not a direct trading strategy. If your underlying trades are failing, investigate those first — don't assume the regime label is the problem.

### When NOT to Use This Strategy

- During Fed meeting weeks, major macro announcements, or geopolitical events, the regime label becomes less reliable because macro flows overwhelm dealer hedging flows.
- If GEX data is more than 2 days stale (i.e., you can't get real-time or next-day data), the label is not actionable — GEX shifts daily as new options are traded.

### Enso Integration Notes

A Phase 2 Enso module: a daily regime card on the main dashboard showing "Positive Gamma / Negative Gamma" and the gamma flip level relative to current price. This card changes the color scheme of the entire dashboard — green tones for positive gamma (calm, fade moves), red tones for negative (trend, wider stops). Data source: SpotGamma API. The LLM integration is strongest here — an AI layer can contextualize the regime with news flow and generate a brief plain-English morning summary: "Positive gamma day, flip level at 5,820 SPX, no major catalysts until Thursday."

---

## Strategy 6: Term Structure Carry

**Difficulty:** Medium | **Phase:** Phase 2 | **Edge Potential:** 7.8/10 | **Enso Fit:** 7.0/10

### What This Strategy Does

Volatility has a term structure — like interest rates, short-term vol and long-term vol are almost always different. Most of the time, short-term vol is cheaper than long-term vol (called contango). This is similar to how interest rates work: borrowing for 10 years usually costs more than borrowing for 1 month. As time passes, the short-term contract rolls toward expiration and loses value — a process called "roll yield." This strategy harvests that roll yield systematically.

The simplest proxy: VIX measures 30-day expected vol. VIX futures (contracts on what VIX will be in the future) usually trade higher than spot VIX. When VIX is at 17 and the 3-month VIX future is at 22, that's a steep contango. You short the front-month future and it gradually rolls down toward spot.

### Why It Works (The Edge)

Investors and institutions constantly buy vol as insurance against market crashes. This persistent demand creates a premium — long-dated vol is consistently overpriced relative to what actually happens. When the term structure is in contango and you're short the expensive front, you earn positive carry every day the market doesn't crash.

The risk is obvious: when markets do crash, VIX spikes to 40, 50, or 80, and the trade loses enormous amounts very quickly. The edge is real but so is the tail risk — this is not a free lunch.

### What You Need Before You Start

- **Data:** VIX futures data from CBOE or via continuous VIX ETP proxies (VXX, UVXY). Free VIX futures historical data is available from CBOE's website. `yfinance` can give you VXX and SVXY price history as proxies.
- **Tools:** Python, CBOE data download, a spreadsheet for tracking term structure readings.
- **Capital:** Minimum $50,000 to run this with manageable sizing. The tail risk requires position sizes that can withstand a 50–80% drawdown on the allocated capital in a crisis.
- **Knowledge:** Understand what contango and backwardation mean (both in the Glossary), and why VXX decays over time (it rolls futures from the front month to the next month, always buying expensive and selling cheap).

### Step-by-Step: How to Test This Strategy

1. **Download VIX futures historical data** from the CBOE website (free, monthly CSV files going back to 2004). Load the front-month (VX1) and second-month (VX2) contract data.

2. **Calculate the term structure slope** for each trading day: `slope = (VX2 - VX1) / VX1`. A positive slope means contango; negative means backwardation.

3. **Build regime rules:** "Carry on" when slope > 5% (front month is at least 5% cheaper than second month). "Stand aside" when slope < 0% (backwardation) or when VIX is above 25.

4. **Backtest a simple short-vol strategy.** Simulate being short 1 VX1 contract (or equivalent in VXX/SVXY) on each "carry on" day. Track daily P&L, including the cost of rolling from one contract to the next each month.

5. **Focus on crisis performance.** Pull up 2008, 2010 (flash crash), 2018 (vol spike), and 2020 (March COVID). How bad did the drawdowns get? What was the recovery time? This tells you whether the strategy is survivable with your capital base.

6. **Calculate Sharpe and max drawdown** across the full history. Academic research suggests risk-adjusted returns are positive but come with severe left tails. Your results will reflect this.

### Step-by-Step: How to Paper Trade This Strategy

1. **Every Monday, check the VIX term structure.** Pull spot VIX and the front two VX futures prices. Calculate the slope.

2. **Log the regime (contango/backwardation)** and whether your criteria are met.

3. **Simulate a short-vol position** when criteria are met. Use SVXY (the inverse VIX ETP) as a proxy — log the entry price and track it daily. Size as if it were 5–10% of your portfolio.

4. **Set a mental stop:** if SVXY falls 20% from entry, exit and wait for the regime to reset.

5. **Paper trade for at least 4–6 months.** This strategy requires at least one period of elevated vol to test the risk management rules properly.

### What Success Looks Like

- **Annual return on capital allocated:** 15–30% in calm years (the carry is real and consistent in benign markets)
- **Sharpe ratio target:** 0.8–1.2 (before accounting for tail events — Sharpe will look better in calm periods than in full historical samples)
- **Max drawdown tolerance:** 30–40% on this strategy's allocated capital in crisis periods. You must be psychologically and financially prepared for that.
- **Minimum sample for confidence:** This strategy needs multiple years of data to evaluate fairly, because the tail events are what matter most.

### Red Flags and When to Stop

- **VIX spikes to 25+ and keeps rising.** This is the most important kill signal. When spot VIX rises through the second-month future (backwardation), exit all carry positions immediately.
- **Your loss exceeds 30% of allocated capital.** Risk management is the whole game here. Don't let a single event wipe out years of carry.
- **You're averaging down on short-vol positions in a crisis.** Never do this. The risk is asymmetric and adding to losing short-vol positions in a sell-off has blown up multiple professional funds.
- **Kill switch:** Backwardation = exit. No exceptions. VIX backwardation is the market signaling genuine fear, and the carry thesis has broken down.

### When NOT to Use This Strategy

- When VIX is already at multi-year lows (below 12–13). The carry exists but the asymmetry is unattractive — there's not much to gain and a lot to lose.
- When you're also running heavy short-premium positions in the IV vs RV or VRP strategies. You'll have multiple correlated short-vol bets, and a single market shock will hit all of them simultaneously.
- When you don't have the stomach to watch 30–40% of this strategy's value evaporate temporarily. If that would cause you to make emotional decisions, this strategy is not for you.

### Enso Integration Notes

A Phase 2 addition: a term structure monitor panel showing spot VIX, VX1, VX2, and the contango/backwardation slope. Could also show SVXY and UVXY as proxy instruments. Historical slope data plotted as a time series gives you context for whether the current term structure is steep or flat relative to history. Minimal new data infrastructure — CBOE data is free, and yfinance has SVXY/UVXY history.

---

## Strategy 7: Pinning / 0DTE Dynamics

**Difficulty:** High | **Phase:** Phase 2 | **Edge Potential:** 7.5/10 | **Enso Fit:** 7.5/10

### What This Strategy Does

0DTE options — options that expire the same day they're traded — now account for over half of all SPX options volume. This is an enormous amount of market activity concentrated into a single day, and it creates predictable patterns. One of the most consistent: gamma pinning. When a huge amount of open interest is clustered at a particular strike price — say, 5,800 on SPX — dealers' hedging activity near expiration tends to keep the market glued to that level. The market gets "pinned."

This strategy identifies those high-open-interest strikes and trades the pinning tendency: expect the market to stay near the pin on calm days, and watch for explosive moves when it breaks free.

### Why It Works (The Edge)

When a strike has enormous open interest, dealers are actively delta-hedging millions of dollars of exposure. Near expiration, these hedges become increasingly precise (gamma is highest near expiration for near-the-money options). The mechanical buying and selling creates a magnetic attraction to that strike. When the pin holds, you can fade small moves away from it. When it breaks, the unwind of hedges accelerates the move — making the break itself tradeable.

### What You Need Before You Start

- **Data:** Intraday open interest by strike for SPX/SPY 0DTE options. This is the hard part — intraday OI data is not widely available for free. SpotGamma tracks this; alternatively, scraping the CBOE's free options data on expiration mornings gives you a crude snapshot.
- **Tools:** Python, intraday data from SpotGamma or similar, a fast enough connection to use intraday data meaningfully.
- **Capital:** This is an intraday strategy — positions are opened and closed same-day. Risk per trade should be small (0.5–1% of capital) given the high activity.
- **Knowledge:** Understand how gamma and delta interact near expiration, and what it means for price to be "near a pin."

### Step-by-Step: How to Test This Strategy

1. **On each SPX/SPY expiration day (Monday, Wednesday, Friday),** download the morning's options open interest snapshot. Identify the strike with the highest open interest within 2% of the current price.

2. **Label each expiration as "strong pin" or "weak pin."** Strong: one strike has at least 50% more OI than neighboring strikes. Weak: OI is spread across multiple strikes.

3. **Record what actually happened.** Did the market close near the high-OI strike? Calculate the distance of the close from the max-OI strike for every expiration in your sample.

4. **Run a binomial test.** If pinning is random, closing near the max-OI strike should happen about 30–40% of the time (based on the distribution of price movements). If it happens 55–65% of the time, there's a pattern worth trading.

5. **Backtest a simple pin-fade rule:** on strong pin days, if SPX moves more than 0.4% away from the max-OI strike before noon, fade back toward the pin (buy the dip or sell the rip). Close at the max-OI strike or at end of day. Track results.

6. **Also test pin-break rules:** when SPX moves more than 0.8% away from the max-OI strike and accelerates rather than reverting, ride the break with a small directional trade. Compare this to the fade rule results.

### Step-by-Step: How to Paper Trade This Strategy

1. **Every expiration morning,** identify the high-OI strike and log it before the open.

2. **Watch the first 90 minutes.** Classify the opening move: is the market near the pin or moving away from it?

3. **Apply the fade rule on strong pin days:** if the market moves away, put on a small paper trade back toward the pin, with a stop at 1.5x the move.

4. **Log the outcome.** Did it pin? Did it break? Was your fade profitable?

5. **Paper trade for 3 months** (roughly 36 expirations on a Monday-Wednesday-Friday schedule). This gives you enough sample to see whether the edge is real.

### What Success Looks Like

- **Pin accuracy:** 55–65% of strong-pin days should close within 0.5% of the max-OI strike
- **Win rate on fade trades:** 55–65% (you're betting on a mean-reversion mechanic)
- **Key metric:** Whether strong-pin days have meaningfully smaller intraday ranges than weak-pin or no-pin days
- **Minimum sample for confidence:** 40 expiration days

### Red Flags and When to Stop

- **Pin strikes are getting blown through every session.** Pinning breaks down in high-conviction directional moves (earnings, Fed days, macro shocks). If your sample period contains a lot of these, pinning won't show up.
- **The strategy requires being glued to a screen.** If you can't watch the market intraday, this is not the strategy for you. Pinning dynamics play out over hours, not days.
- **Kill switch:** If your intraday fade trades are losing more than 1% of capital per expiration day, stop and reassess. The moves are exceeding your model's assumptions.

### When NOT to Use This Strategy

- On Fed meeting days, CPI print days, or any major macro event — large institutional flows will overwhelm the pinning mechanic.
- When VIX is above 25 — the market is in a high-vol regime where 0DTE dynamics are overwhelmed by macro fear.
- If you can't dedicate 2–3 hours to monitoring the intraday action. Half-implemented intraday strategies are worse than no strategy.

### Enso Integration Notes

A Phase 2 module: an expiration day dashboard showing the current SPX/SPY open interest by strike as a bar chart, with the max-OI strike highlighted. Overlay the current price in real time. This is a visual tool — it doesn't need to generate trade signals automatically, just give the operator clear visual information. The data source is either SpotGamma's API or a morning snapshot from CBOE free data (which requires a manual or scheduled pull).

---

## Strategy 3: Skew Surface Trading

**Difficulty:** Expert | **Phase:** Phase 3 | **Edge Potential:** 8.8/10 | **Enso Fit:** 6.5/10

### What This Strategy Does

The volatility surface is a 3D map of implied volatility. One axis is the strike price (how far OTM you go), another is time to expiration, and the third axis is the IV itself. Every point on this surface represents the market's price of an option with those specific characteristics.

Skew surface trading finds parts of this map that look out of line — strikes or expirations where the IV seems too high or too low relative to the rest of the surface. You buy what's cheap and sell what's expensive, structuring trades to profit from the surface rebalancing.

This is genuinely hard. It requires a full options surface data feed, a model for what "fair value" looks like, and the ability to execute complex multi-leg structures. Defer this until Phase 1 and Phase 2 are running cleanly.

### Why It Works (The Edge)

Different participants create systematic distortions in the vol surface. Retail investors buy near-the-money puts for protection, inflating that part of the skew. Corporate hedgers buy long-dated downside protection, creating a different distortion. Market makers model the surface differently from each other. These distortions are predictable enough that sophisticated vol desks exploit them systematically.

### What You Need Before You Start

- **Data:** Full options surface data with IV for every strike and expiration — iVolatility, CBOE LiveVol, or similar. Not cheap (typically $500–$1,500/month for professional-quality surface data).
- **Tools:** A vol surface model (e.g., SVI parameterization or SABR). This is genuinely quantitative work.
- **Capital:** Minimum $100,000. Skew trades require multiple options legs and delta-hedging.
- **Knowledge:** You need to understand vol surface parameterization, arbitrage constraints (no-call-spread arbitrage, no-butterfly-spread arbitrage, calendar spread arbitrage), and how to execute delta-neutral structures.

### Steps (Abbreviated — This is Phase 3)

1. Build a full surface data pipeline for your chosen underlyings.
2. Parameterize the surface using SVI or a similar model.
3. Identify deviations: strikes or tenors where market IV differs materially from the model surface.
4. Structure delta-neutral trades (risk reversals, butterflies, calendar spreads) to exploit the deviation.
5. Backtest with realistic transaction costs — this strategy is expensive to execute.
6. Paper trade for at least 50–100 trades before going live.

The testing and paper trading methodology is the same as the general framework in this guide, but the implementation is significantly more complex. Plan 3–6 months of build time before you have a testable system.

### What Success Looks Like and Red Flags

Success: consistent P&L from surface mean-reversion with Sharpe above 1.0. Red flags: trades that require predicting market direction to be profitable (if you need the stock to go up to make money, you have a directional bet, not a surface trade).

### Enso Integration Notes

Deferred to Phase 3. Requires a full surface data subscription and a new vol modeling module. Not connected to the current Enso infrastructure at all — this is a ground-up build.

---

## Strategy 4: Dispersion / Correlation Trades

**Difficulty:** Expert | **Phase:** Phase 4 | **Edge Potential:** 8.5/10 | **Enso Fit:** 5.5/10

### What This Strategy Does

An index like the S&P 500 is made up of individual stocks. Sometimes the options market prices the index (SPX) as if stocks will all move together more than they actually will. This creates a gap between "implied correlation" (what the index options say) and "realized correlation" (how much stocks actually moved together). Dispersion trading sells index vol and buys single-stock vol (or vice versa), profiting from that correlation mispricing.

This is genuinely institutional territory — it requires trading dozens of individual stock options simultaneously alongside index options, maintaining hedges, and actively managing a complex portfolio. It is not suitable for a solo operator without significant infrastructure. Understand it conceptually now; build toward it in Phase 4.

### Why It Works (The Edge)

Index hedging demand persistently inflates index vol relative to single-stock vol. Everyone wants to buy SPX puts to protect their equity book; far fewer people hedge individual stock positions with the same precision. This creates a structural premium in index vol that patient dispersion traders harvest.

### What You Need (Phase 4)

- Full single-name options chains for the top 50–100 SPX members
- Index options data (SPX/SPY)
- Execution infrastructure capable of placing 50–100 simultaneous options orders
- $500,000+ in capital
- Deep understanding of correlation dynamics and hedge ratios

### Enso Integration Notes

Deferred to Phase 4. Placeholder only for now — note in the Enso roadmap that this strategy exists and is a long-term aspiration, but requires capabilities the current system doesn't have.

---

## Strategy 9: Cross-Asset Signal Fusion

**Difficulty:** High | **Phase:** Phase 3 | **Edge Potential:** 6.8/10 | **Enso Fit:** 6.5/10

### What This Strategy Does

No single market tells the whole story. Credit spreads (CDX), interest rate volatility (MOVE index), currency movements, and equity vol all interact and often diverge before they converge. This strategy combines signals from multiple asset classes into a single regime label — "risk-on," "risk-off," or "transition" — and uses that label to filter all the other strategies in this stack.

Think of it as building a control tower that synthesizes all the instruments at once. Individual strategies are like individual dials; this is the system that reads all the dials together and tells you what mode you're in.

### Why It Works (The Edge)

Cross-asset signals catch regime shifts earlier than single-market signals. The 2007–2008 financial crisis showed up in credit markets months before equity vol spiked. The 2018 Q4 selloff was preceded by rising short-term rates. Having an early warning from a different asset class gives you time to reduce risk or position defensively before the primary market reacts.

### What You Need Before You Start

- **Data:** MOVE index (rate vol), CDX (credit spreads), DXY (dollar index), all available free or inexpensively. Macro surprise indices from Citi or Bloomberg are harder to access cheaply.
- **Tools:** Python for data aggregation, an LLM API for narrative-aware regime labeling (this is where AI leverage is highest — 9.5/10).
- **Capital:** This is a filter strategy — capital requirements depend on what you're filtering.
- **Knowledge:** You need to understand what CDX, MOVE, and macro surprise indices measure (all in the Glossary).

### Steps (Phase 3)

1. Download historical daily data for MOVE, CDX IG/HY, DXY, VIX, and a broad equity index.
2. Normalize each into a z-score relative to its 1-year history.
3. Define regime rules: "risk-off" when 3+ of 5 indicators are in the top quartile of stress. "Risk-on" when 3+ are in the bottom quartile. "Transition" otherwise.
4. Backtest any existing strategy both with and without this macro filter. Measure whether the filter improves Sharpe or reduces drawdown.
5. Add an LLM layer: feed the regime label plus today's news headlines into a language model and ask it to assess whether the mechanical label and the news are consistent. If they diverge, the LLM flag is a warning signal.
6. Paper trade the filtered strategy for 3 months.

### Enso Integration Notes

Phase 3. The AI leverage is highest here — the LLM layer for cross-asset narrative synthesis is where the language model genuinely adds value beyond what a simple rule can do. Build this as a "Daily Briefing" module that aggregates the cross-asset signals each morning and produces a plain-English regime assessment.

---

## Strategy Stacking: How to Combine Strategies

### Strategies That Complement Each Other

- **IV vs RV Monitor + VRP Harvest (Strategies 1 and 8):** These naturally pair. The IV/RV monitor tells you the environment; VRP Harvest is the execution layer. Build the monitor first, then add the trading rules on top.
- **Dealer Gamma Regime + Any Phase 1 Strategy:** Gamma regime is a filter for all other strategies. Applying it to IV/RV or Event Vol Strangle makes both more selective and usually more accurate.
- **S/R + Vol Filter + IV vs RV Monitor:** The baseline strategy gets meaningfully better when the vol context is quantified instead of qualitative. These are designed to stack.
- **Cross-Asset Fusion + Everything:** Once built, the macro regime filter applies to every strategy in the stack. It's a top-level override — when cross-asset signals say "risk-off," reduce size across all short-vol strategies.

### Strategies That Conflict

- **VRP Harvest and Term Structure Carry on the same day.** Both are short-vol bets. Combining them doubles your exposure to a sudden vol spike. If VIX jumps 10 points, you get hit twice.
- **Event Vol Strangle (short) and owning long vol for a macro hedge.** If you're short event vol in individual names but long index vol as a hedge, you have a dispersion-like position that requires active management to not blow up.
- **Any short-premium strategy during Fed week.** The gamma regime model becomes unreliable, the vol surface shifts, and unexpected events are more likely. Reduce all short-vol exposure in the 48 hours around major Fed announcements.

### Recommended Starter Stack for Phase 1

1. **S/R + Vol Filter (Baseline):** Keep running and upgrade the vol filter.
2. **IV vs RV Monitor (Strategy 1):** Build the dashboard and start logging the signal. Don't trade yet — just observe.
3. **Event Vol Strangle (Strategy 5):** Paper trade the first 10–15 events while the IV/RV monitor runs in parallel.
4. **VRP Harvest (Strategy 8):** Add this as an overlay to the IV/RV monitor once you've confirmed the signal quality.

This is roughly two strategies running live (S/R and Event Vol) plus two strategies in active paper trading (IV/RV and VRP). That's enough to stay busy and generate meaningful data without overwhelming your monitoring capacity.

### Portfolio-Level Risk When Running Multiple Strategies

The most important rule: **short-vol strategies all lose at the same time.** When markets crash, VRP Harvest, Term Structure Carry, Event Vol Strangle, and IV vs RV shorts all go against you simultaneously. Don't fool yourself into thinking you're diversified just because the strategies have different names.

A rough rule: allocate no more than 25–30% of your total capital to strategies that are net short volatility at any one time. Keep a buffer that can absorb a 30% drawdown on that allocation without forcing you to close positions at the worst time.

---

## The Build Roadmap

### Month 1–2: Phase 1 Foundations

**What to build:**
- Polygon API integration for live and historical options chain data
- HV20 calculator running on your target universe
- IV/HV ratio dashboard panel in Enso
- Earnings calendar data feed with expected move calculation
- Trade logging system (even a simple spreadsheet is fine at this stage)

**What to test:**
- S/R + Vol Filter upgraded with quantified IV readings
- IV vs RV Monitor in observation mode (no trading, just logging)
- Event Vol Strangle paper trading: first 10–15 events

**Infrastructure to build:**
- Clean, modular Python scripts that can be scheduled (daily) to update the ratio dashboard
- Centralized trade log with fields: date, ticker, strategy, entry, exit, outcome, vol context at entry

### Month 3–4: Phase 1 Live + Phase 2 Begins

**What to go live with:**
- IV vs RV Monitor trading (small size, 50% of intended position size)
- Event Vol Strangle live (again, small size — test your execution)

**What to begin building (Phase 2):**
- SpotGamma or SqueezeMetrics subscription and data pipeline
- GEX regime classifier
- VIX futures data download and term structure monitor

**What to paper trade:**
- VRP Harvest with full filter checklist
- Dealer Gamma Regime as a filter on existing live strategies

### Month 5–8: Phase 2 Live, Phase 3 Begins

**What to add to live trading:**
- Dealer Gamma Regime as a regime filter on all strategies
- Term Structure Carry (small allocation, very strict risk management)
- Pinning / 0DTE Dynamics (intraday, small size)

**Phase 3 groundwork:**
- Evaluate full vol surface data costs and vendors
- Begin building cross-asset signal aggregator (MOVE, CDX, DXY data pipeline)
- Design the LLM daily briefing module

### Infrastructure at Each Phase

| Phase | Key Infrastructure |
|---|---|
| Baseline | yfinance, Enso S/R engine, manual trade log |
| Phase 1 | Polygon API, IV/HV calculator, earnings calendar, structured trade log |
| Phase 2 | SpotGamma/SqueezeMetrics GEX, VIX futures data, intraday OI snapshots |
| Phase 3 | Multi-asset data pipeline, LLM API integration, full surface data (optional) |
| Phase 4 | Multi-leg execution infrastructure, high-capital allocation, portfolio management tools |

---

## Backtesting Do's and Don'ts

### The Most Common Backtesting Mistakes (Plain English)

**Lookahead bias.** You accidentally use future information to make past decisions. Example: you calculate "20-day future volatility" and use it to evaluate today's trade — but in real life, you didn't know the next 20 days when you placed the trade. Always calculate your signals using only data that was available *at* the trade date.

**Survivorship bias.** You test only stocks that still exist today. But companies that went bankrupt, got acquired, or got delisted are invisible in your data — and they often had the worst outcomes. Use a data source that includes delisted companies for long-term backtests.

**Ignoring transaction costs.** Options have wide bid-ask spreads, especially for far OTM strikes. A strategy that looks profitable at mid-market prices often loses money when you account for the spread you're crossing. Always model 50–100% of the bid-ask spread as a cost in your backtest.

**Over-optimizing parameters.** You test 500 different parameter combinations (different windows, thresholds, stop levels) and pick the best one. The problem is that the "best" combination is probably just the one that got lucky in your test period. The analogy: if you ask 500 people to flip a coin 10 times, one of them will get heads 9 out of 10 times — not because they're skilled, but because that's what variance looks like.

### Why Walk-Forward Testing Matters

A regular backtest uses all your data at once — you look at the whole picture and find what worked. Walk-forward testing is different: you pretend you're living through the data in sequence. You train your model on the first year of data, test it on the second year (without looking), then move the window forward and do it again.

The analogy: imagine you're studying for an exam. A regular backtest is like studying with the answer key in hand — of course the answers look great. Walk-forward testing is like studying from old exams and then taking this year's exam cold. It's the only honest measure of whether your strategy would have worked in real time.

Always reserve at least 20–30% of your historical data as an out-of-sample test set that you never use during development.

### How to Avoid Overfitting (The "Studying for the Test" Analogy)

Overfitting means your strategy is memorizing the quirks of your test data rather than learning a real pattern. It's like a student who memorizes every question from past exams but can't answer a new question.

Signs you're overfitting:
- Your strategy has more than 5–7 parameters (strike distance, window lengths, thresholds, etc.)
- The backtest performance is dramatically better than any reasonable real-world expectation
- The strategy stops working as soon as you add more data or a different time period

The rule of thumb: a legitimate strategy should have fewer parameters, not more. The simpler the rule, the more likely it reflects a real market structural edge rather than an artifact of your specific data.

### Minimum Data Requirements

| Strategy Type | Minimum History |
|---|---|
| S/R + Vol Filter | 1 year (to see enough S/R touches) |
| IV vs RV Monitor | 2 years (to see both high and low IV environments) |
| Event Vol Strangle | 2 years, 3–4 events per ticker per year minimum |
| Term Structure Carry | 10+ years (to include at least one major crisis) |
| Dispersion / Skew Surface | 5+ years (surface dynamics shift across regimes) |

### When to Trust Results and When to Be Skeptical

**Trust the results when:**
- The edge is consistent across multiple underlyings and time periods, not just one stock in one year
- The logic makes sense (you can explain *why* it works, not just *that* it worked)
- Out-of-sample (walk-forward) results are reasonably close to in-sample results
- The number of trades is at least 50, ideally 100+

**Be skeptical when:**
- The backtest Sharpe is above 2.0 (almost never real; almost always overfitting)
- The strategy only worked in one specific year
- You can't explain the underlying market mechanism
- Removing any single parameter makes the strategy lose money

---

## Glossary

**Implied Volatility (IV):** The market's forward-looking estimate of how much a stock will move, expressed as an annualized percentage. If a stock's IV is 30%, options traders expect roughly a 1.7% daily move (30% ÷ √252). IV is extracted from the options price using a model (usually Black-Scholes).

**Realized Volatility (RV) / Historical Volatility (HV):** How much the stock actually moved over a past period. Calculated by taking the standard deviation of daily log returns and annualizing by multiplying by √252.

**Volatility Risk Premium (VRP):** The systematic gap between IV and subsequent RV. IV tends to run about 2–4 percentage points above RV on average, representing the "insurance premium" that option sellers earn.

**Delta:** How much an option's price changes when the stock moves $1. A 50-delta call gains $0.50 when the stock rises $1. Delta ranges from 0 (far out of the money) to 1 (deep in the money).

**Gamma:** How fast delta changes. High gamma means a small move in the stock causes a large change in delta. Near expiration and near the money, gamma is highest.

**GEX (Gamma Exposure):** The total gamma exposure of options dealers across all outstanding contracts, expressed in dollar terms. Positive GEX means dealers are collectively long gamma and hedge by selling into rallies / buying into dips. Negative GEX means dealers are short gamma and must buy into rallies / sell into dips, amplifying moves.

**Skew:** The difference in implied volatility between OTM puts and OTM calls. A steep put skew means downside protection is expensive relative to upside calls. Skew reflects the market's asymmetric fear of downside moves.

**Vol Surface:** The full 3D map of implied volatilities across all strikes and expirations. Each point represents the market's price for options at that specific strike and tenor.

**Term Structure:** The relationship between IV at different expiration dates. Normally upward-sloping (longer-dated options have higher IV) — called contango. When short-dated IV exceeds long-dated IV, it's called backwardation.

**Contango:** When nearer-term futures or options are cheaper than longer-dated ones. In VIX, contango means spot VIX is below VIX futures — the normal, calm-market state.

**Backwardation:** When nearer-term futures or options are more expensive than longer-dated ones. In VIX, backwardation signals genuine current fear — the market expects vol to decline, meaning it's currently elevated.

**Sharpe Ratio:** Annual return divided by annual volatility of returns. A Sharpe of 1.0 means you earned 1% of excess return for every 1% of risk. Industry standard for "decent" is 0.8+; "good" is 1.5+; "suspicious" is above 2.5.

**Drawdown:** The peak-to-trough loss in an account or strategy. A 20% drawdown means the account fell 20% from its high-water mark at some point. Max drawdown is the largest such drop in the history of the strategy.

**Walk-Forward Testing:** A backtesting method where you train on early data and test on later data in sequence — mimicking real-world operation. More honest than testing on the entire dataset at once.

**Dispersion:** The spread between individual stock returns within an index. High dispersion means stocks are moving differently from each other; low dispersion means they're moving together.

**Correlation:** How much assets move together. Correlation of 1.0 means they move in lockstep; 0 means no relationship; -1.0 means they move in opposite directions.

**0DTE:** Zero days to expiration. Options that expire the same day they're traded. SPX now offers 0DTE contracts Monday through Friday.

**Pinning:** The tendency for a stock or index to close near a large open-interest strike price on expiration day, due to dealer hedging flows creating a gravitational effect.

**Credit Spread:** Selling one option and buying another option at a different strike, with the same expiration, on the same underlying. You collect a net credit (cash in). Maximum profit is the credit; maximum loss is the spread width minus the credit.

**Debit Spread:** Buying one option and selling another option at a different strike, same expiration. You pay a net debit (cash out). Maximum profit is the spread width minus the debit; maximum loss is the debit paid.

**Strangle:** Buying or selling a call and a put on the same underlying with the same expiration but at different strikes (the call above the current price, the put below). Profitable for sellers when the stock doesn't move much; profitable for buyers when the stock moves a lot.

**Straddle:** Buying or selling a call and a put on the same underlying, same expiration, same strike (usually at the money). The most direct way to express a view on whether vol is cheap or expensive.

**Iron Condor:** Selling a strangle and buying a wider strangle around it. Four legs total, defined risk. The classic retail-friendly short-vol structure.

**Butterfly:** Three options at three different strikes. The standard butterfly is long one call at a low strike, short two calls at the middle strike, and long one call at the high strike (or the same with puts). Profits if the stock pins the middle strike.

**Risk Reversal:** Simultaneously buying a call and selling a put (or vice versa) at equidistant strikes. A quick way to express a directional view with limited or no net premium. The skew of a risk reversal reflects how expensive downside protection is relative to upside.

**CDX:** The credit default swap index — a measure of credit market stress. Rising CDX means the market is increasingly concerned about corporate defaults. Often leads equity vol spikes by days or weeks.

**MOVE Index:** The Merrill Lynch Option Volatility Estimate — essentially the VIX equivalent for U.S. Treasury bonds. Rising MOVE signals stress in the rates market, which often spills into equity markets.

---

*Guide version 1.0 — April 2026. Based on strategy rankings from Enso Institutional Options Strategy Rankings v1.0. Build phases, difficulty ratings, and Enso fit scores sourced from strategy-rankings.json.*
