# Goal check (2 trades/day, $700/week), audit, and next approach — 2026‑11‑27

## 1. Is "2 trades a day and $700 a week" reachable with what we have?

$700/week ≈ $140 per trading day. At 2 trades/day (10 per week) that is **$70 expectancy per trade**.

Scaling each tested MNQ variant linearly to $700/week (`reports/mnq_1h_intraday_4h.csv`, `reports/timeframe_comparison.csv`):

| Variant | Trades/day | $/week @ $100 risk | Exp R | Risk/trade needed | Max DD at that risk | Verdict |
|---|---|---|---|---|---|---|
| 1H, 4H filter, A+B+C (current Pine) | 0.17 | $21 | 0.32 | ~$3,300 | ~$41,000 | Frequency far too low; DD 20× the $2k trailing limit |
| 15M, 1H filter, breakout | 0.61 | $40 | 0.17 | ~$1,750 | ~$48,000 | One year of data; MES negative |
| 5M, 1H+15M filter, breakout | 1.70 | $138 | 0.24 | ~$510 | ~$10,900 | **Only variant near 2/day**, but 77 days of data; MES negative |
| 5M, 15M filter, breakout | 2.64 | $141 | 0.15 | ~$500 | ~$15,500 | Same caveats |
| 1M (any) | 3.3–3.6 | negative | <0 | — | — | Rejected |

**Conclusion: not reachable safely with the current model.**
* $700/week on a $50K account is about 1.4% a week, or roughly 70% a year.
* Even the best‑looking high‑frequency variant would need about $500 risk per trade. Its drawdown would then be about $11k, against a reported $2,000 trailing limit. Two average losing days in a row would breach the account.
* For $700/week to be safe, the system needs about **2 trades/day at ≥ 0.35R expectancy with ≤ $150 risk**. That is roughly double the best edge found, at 10× the frequency. Nothing tested so far does this.

**Realistic, account‑safe target with the evidence in hand: $20–$140 per week.** The low end is the 1H model, which is validated over four years. The high end is the 5M model, which has only 77 days of data and is unvalidated.

## 2. Audit

### What is solid
* No look‑ahead: a test truncates the data and checks that earlier lines and trades are unchanged.
* Costs and slippage are included, and fills are pessimistic.
* There is a random‑entry benchmark and walk‑forward testing.
* The Pine script matches the Python engine on TradingView's own backtest (178 vs 169 trades; PF 1.45 vs 1.59).
* The risk engine is independent of the strategy.

### Weaknesses found

| # | Issue | Impact | Fix |
|---|---|---|---|
| 1 | Lower‑TF data is short: 5M is only 77 days, 1M only 9–12 days | Cannot validate the only high‑frequency candidates | Buy or download ≥ 2 years of 1M/5M MNQ/MES (Databento, FirstRate Data, Kinetick, or the TradingView Premium export) |
| 2 | Profit concentrated in a few trend days (one day = 85% of breakout‑only profit) | Fragile; one missed day erases the year | Judge by median week and trimmed P&L, not net |
| 3 | 2025–26 performance is flat or negative in every 1H variant | Edge may be gone (regime change) | Forward‑test before risking capital; add a regime filter |
| 4 | Multiple testing: about 1,500 configurations tried | Best results are inflated | Keep a sealed holdout (e.g. 2026) and test the final pick once |
| 5 | Only the 4H filter carries the edge; the trendline trigger adds ~0.18R that is not significant | The "trendline" part may be decoration | Test simpler triggers under the same filter (§3) |
| 6 | Prop rules are unverified; IQ Capital reportedly forbids bots | Possible rule breach | Get written confirmation |
| 7 | Pine 4H timing is one bar more conservative than Python | Small P&L difference (−12%) | Documented, accepted (it is the non‑repainting choice) |
| 8 | The bridge has no real fill feedback (Tradovate websocket) and the Tradovate adapter is untested | Live P&L tracking would be wrong | Implement before any live use |
| 9 | Unadjusted continuous contracts (roll gaps) | Minor for intraday | Use back‑adjusted data in the next study |
| 10 | Webhook alerts can't be created through the TradingView API (2FA requirement) | The paper test must be set up by hand on tradingview.com | See §4 |

## 3. Next approach (in order)

1. **Get proper intraday data.** At least 2–3 years of 1M MNQ/MES, so 5M/15M ideas can be validated across 2023–2026 instead of 77 days. Every high‑frequency idea depends on this.
2. **Keep the part that works (the higher‑timeframe trend filter); test better intraday triggers for 1–2 trades/day:**
   * Opening‑range breakout (first 15/30 min) in the 4H/daily trend direction, one trade per side per day.
   * Pullback to VWAP or the 20‑EMA in the trend direction on 5M.
   * 5M trendline breakout (the current best: 1.7/day, +0.24R) restricted to 09:45–11:30 and 13:30–15:30.

   Rule for adopting any of these: it must beat random entries taken in the trend direction at the 95% level, out of sample.
3. **Add a regime filter.** Trade only when the daily ATR percentile and the trend‑efficiency ratio show a trending market. This targets the big trend days that produce all the profit, and skips chop such as 2025–26.
4. **Diversify instead of increasing size.** Add one low‑correlation market (crude oil MCL or gold MGC, which Tori also trades), one position at a time. This raises frequency without stacking correlated index risk.
5. **Size by drawdown budget, not by income target.** With a $2,000 trailing drawdown, keep risk ≤ $150/trade and ≤ $450/day. Raise it only after the account has built a buffer above the trailing floor.
6. **Seal 2026 as the holdout.** Fit on 2023–2025 only and test once.
7. **Paper‑trade for 4–8 weeks** (§4) before the evaluation account.

## 4. TradingView paper test

* **TradingView connection:** working (`list_alerts` → connected).
* **Script:** saved to your account as **"Trendline Fan Prop v1 (paper test)"** (`USER;1a3a3a8ff1974a288368c419bb85c81d`); it compiles.
* **Important:** TradingView does **not** route strategy orders into its Paper Trading broker automatically. Strategy orders appear only in the Strategy Tester and the alert log. Two options:
  * **A — forward test in TradingView (no code).** Open an MNQ1! 1H chart, add the strategy, and leave it running. New trades appear in the Strategy Tester's *List of Trades* as bars close. Optionally create an alert on the strategy ("alert() function calls only", no webhook) so every signal is logged and pushed to your phone. Then place matching orders by hand on the *Paper Trading* broker if you want broker‑side fills.
  * **B — automated paper test.** Create the alert with webhook → `bridge/` running in PaperBroker mode on a VPS. This needs 2FA on TradingView and a public HTTPS endpoint.
* **Timing:** Friday 2026‑11‑27 is the post‑Thanksgiving half day (CME equity futures close early, about 13:15 ET). The market is closed this weekend and reopens Sunday at 18:00 ET. The strategy only enters 10:00–15:30 ET, so **no trade can occur tonight or over the weekend**. The first possible signal is Monday 2026‑11‑30 after the 10:00 ET bar closes.

## 5. Step 1 results (2026‑11‑27): longer data + new intraday entries

**Data:** 5‑minute MNQ, 2022‑12‑26 → 2026‑11‑25 (277k bars).
* Built from Tradovate demo history: 15 quarterly contracts, rolled on the Thursday before expiry week, unadjusted. This is `data/raw/MNQ_5m_tv.csv`.
* Extended with TradingView NQ1! 5m after 2026‑08‑25. The combined series is `data/raw/MNQ_5m_long.csv`.
* The overlap check against TradingView shows a mean |close diff| of 0.47 pt. The only gaps are exchange holidays.

**Test design (`research/run_intraday_entries.py`, `reports/intraday_entries.csv`):**
* 2023–2025 in‑sample; 2026 out‑of‑sample, sealed.
* $100 risk, MNQ, intraday, costs included.
* 4 trades/day max, 3 consecutive losses, $550/$700 daily limits.
* 10 entry families × 3 trend filters (none/4H/daily) × 3–4 exits = 66 configurations.

**Entry families:** ORB 15/30 min (stop at the range, the midpoint or 1 ATR), VWAP pullback, EMA20 pullback, 5m trendline breakout in the morning and afternoon windows.

**Best configurations that trade ≥ 0.5/day (in‑sample ranked):**

| Entry | Filter | Exit | Trades/day | IS exp R | IS $/week | 2023 / 2024 / 2025 | 2026 OOS exp R | 2026 $/week |
|---|---|---|---|---|---|---|---|---|
| ORB15, 1‑ATR stop | none | ATR trail | 1.11 | +0.11 | +$39 | +3.0k / +0.6k / +3.7k | −0.01 | −$14 |
| ORB30, 1‑ATR stop | none | ATR trail | 0.90 | +0.08 | +$24 | +3.4k / +2.3k / +2.5k | +0.07 | +$12 |
| ORB15, 1‑ATR stop | 4H | ATR trail | 0.54 | +0.05 | +$12 | +3.1k / +0.9k / −0.5k | −0.16 | −$21 |
| EMA20 pullback | daily | ATR trail | 1.77 | +0.04 | +$31 | +6.0k / +6.0k / −6.9k | +0.01 | +$5 |
| 5m trendline (windows) | daily | ATR trail | 2.19 | +0.03 | +$20 | +6.7k / +1.7k / −5.2k | +0.11 | +$103 |
| VWAP pullback | daily | ATR trail | 1.08 | +0.03 | +$12 | +0.8k / +1.5k / −0.7k | −0.11 | −$25 |

**Every other configuration is ≤ 0R in‑sample.** The ORB variants with very high R (ORB30, range stop) took only 7–12 trades in three years, because the range stop is usually too wide for $100.

**Verdict:**
* None of the new entries produces a usable edge.
* At 1–2 trades/day the best in‑sample expectancy is about +0.1R. That is roughly the size of costs (0.05–0.15R) and within random noise, and none holds up in both the in‑sample years and 2026.
* **$700/week at 2 trades/day would need ~0.7R per trade at $100 risk.** That is about 7× the best result here, and higher size makes the drawdowns proportionally larger.
* The 2‑trades‑a‑day, $700‑a‑week goal is **not supported** by any tested trendline, ORB, VWAP or EMA entry on MNQ.

**What remains worth trying** (lower expectations):
1. A regime filter that trades only on high‑range trend days (daily ATR percentile plus opening drive). All the families make money on a handful of trend days and bleed on the rest.
2. The same tests on MES/M2K/MCL/MGC, to diversify frequency rather than force it from one market.
3. Accepting a lower, realistic target: ~$20–40/week at $100 risk, or a proportionally larger target only once the account has a buffer above its trailing drawdown.
