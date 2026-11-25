# Trendline Futures Strategy — Research Report (Stages 1, 3, 4, 5, 8)

Prepared 2026‑11‑25. Every number here comes from the code in `research/`, run on the data in `data/raw/`.
Labels used throughout:

* **[T1]** — what Tori Trades explicitly teaches (transcript 1)
* **[T2‑claim]** — what the second presenter *claims* (transcript 2); these are not verified facts
* **[VERIFIED]** — independently reproduced in this project's backtests
* **[PROPOSED]** — a new rule or improvement from this project
* **[ASSUMPTION]** / **[UNKNOWN]** — not verified

---

## 0. Executive summary (read this first)

1. **The transcript‑2 critique largely replicates [VERIFIED].** The always‑in‑market trendline breakout made about +$266k per NQ mini on 4H (2019‑06 → 2026‑11). It lost money on ES (‑$37k) and RTY (‑$16k) and roughly broke even on YM. On 1H it was negative on ES, YM and RTY. Results change a lot between 3‑candle and 5‑candle pivots (NQ 4H: +$266k vs +$85k). In 2022 it made money (NQ +$65k, ES +$72k) while buy‑and‑hold lost heavily. That makes it work like crash insurance, not like a general edge.
2. **Lower timeframes do not rescue it [VERIFIED].**
   * **15M and 5M:** after commissions and 1 tick of slippage, every family (breakout, bounce, retest, fan) has negative average expectancy on all four index micros. Only 0–17% of parameter combinations reached profit factor (PF) above 1. Costs alone take 0.05–0.16R per trade.
   * **1M:** only ~9–12 days of data were available, which is too little to judge. Results were mixed, and MNQ was negative. **Rejected.**
3. **The only setup that held up is Configuration 1: 4H trendline direction with 1H trendline entries, on MNQ only.** With the risk engine at $100 per trade (2023‑01 → 2026‑11):
   * 174 trades, PF 1.65, +0.36R per trade, net **+$4,849**.
   * Max drawdown $1,244, worst day ‑$170, 0.17 trades per day.
   * Walk‑forward out‑of‑sample: 36 trades, +0.58R per trade, PF 1.96.
4. **That edge is weak, and most of it comes from the 4H direction, not from the trendline entry.**
   * It beats 90% of random entries with the same exits, but only **75%** of random entries taken in the 4H direction. That is not significant at the 95% level.
   * Performance faded: 2023 +$2.2k, 2024 +$2.8k, 2025 +$0.15k, 2026 ‑$0.25k.
   * It does **not** carry over to MES (negative), and it breaks with 7‑candle pivots.
5. **A $1,000 daily target is not realistic.** At $100 risk, only 1.9% of trading days reached +$1,000. The expected result is about **+$100 per month**. Raising risk to reach bigger numbers sharply raises the chance of breaking the (third‑party‑reported) $2,000 trailing drawdown. At $250 per trade, the simulated failure rate was 40%.
6. **Automation may be against the prop‑firm rules.** Two third‑party reviews state that IQ Capital *prohibits automated trading and bots*. I could not reach IQ Capital's own rule pages from this environment. **Get written confirmation from IQ Capital before connecting any automation to the account.** See `docs/PROP_RULES.md`.

**Recommendation:** Do not trade the $50K evaluation with this system yet.
* Compile the Pine script and match its trades against the Python engine.
* Paper‑trade it through the bridge for at least 3 months; it only makes about 3–4 trades a month.
* If you go live, keep risk at **$100 per trade** with a 4‑trade, 3‑loss, $550/$700 daily cap.
* **Do not use a daily profit target.**

---

## 1. Data actually used

Source: TradingView continuous front‑month futures (CME_MINI:NQ1!, ES1!, CBOT_MINI:YM1!, CME_MINI:RTY1!), full electronic session. Prices are *not* back‑adjusted for rolls.

| TF | Instruments | Period | Bars per symbol |
|---|---|---|---|
| 4H | NQ ES YM RTY | 2019‑06‑02 → 2026‑11‑25 | ~11,540 |
| 1H | NQ ES YM RTY | 2023‑01‑02 → 2026‑11‑25 | ~23,000 |
| 15M | NQ ES YM RTY | 2026‑01‑01 → 2026‑11‑25 | ~21,360 |
| 5M | NQ ES | 2026‑08‑09 → 2026‑11‑25 (~77 RTH days) | ~21,360 |
| 1M | NQ, ES | NQ 2026‑11‑01→11‑12 (9 days), ES 2026‑11‑05→11‑25 with gaps (12 days) | 12–16k |

**Limitations (material):**
* The TradingView plan's intraday depth limits how far back the lower timeframes go. The 5M and 1M samples are too short to be conclusive. The 15M sample covers a single year (2026).
* YM and RTY 5M/1M and the 4H data before 2019 were not downloaded: the TradingView daily API quota ran out during collection.
* There is no tick or bid/ask data, so slippage is modelled at 1 tick per side (2‑tick sensitivity also reported).
* Unadjusted continuous contracts contain roll gaps. These distort buy‑and‑hold and lines that span a roll. Intraday strategies that are flat at the close are barely affected.
* The micro contracts (MNQ/MES/MYM/M2K) are priced off the mini data (identical index points). Only the dollar point value differs.

---

## 2. Stage 1 — Transcript analysis

### 2.1 Transcript 1 ("How to trade trendlines in under 17 minutes") — what is explicitly taught [T1]

| Element | Rule as taught | Objective? |
|---|---|---|
| Line types | Up trendline connects higher lows; down trendline connects lower highs | Yes |
| Tool | TradingView **Ray** (extends right indefinitely) | Yes |
| Point A (first up line) | Lowest point on the screen | Partly (depends on the visible window) |
| Point B | "A higher low where price has not yet intersected", dragged to the **most recent** touch point | Mostly |
| Fan | "Each new line uses the previous Point B as its new Point A"; draw progressively steeper lines | Yes, once swing points are defined |
| Top‑down | Monthly → weekly → daily → 4H → 1H; stop at the timeframe you committed to; "I don't jump time frames… looking for sooner entries" | Process, not a filter |
| Bounce trade | At a line, trade continuation; stop on the other side of the line; optional take profit (TP) at prior support/resistance; preferred exit = trail the stop along the line, exit when it breaks | Mostly |
| Breakout trade ("my all‑time favourite") | Enter when price breaks a line (reversal); stop on the other side of the opposite/new line; trail; optional TP at support/resistance | Mostly |
| Higher‑TF lines | "Drawn in a higher time frame so it holds a little bit more weight" | Qualitative |
| Risk | 1–2% of account per trade; for a 128k paper account $1,000–$2,500 | Yes |
| Maintenance | Adjust lines regularly to new Point A/B as price crosses them | Yes |
| Live example | Crude oil short on an up‑line break, stop beyond the down line, risk $8,900, TP at support, +$27,600 (3.11R) | Anecdote |

**Missing or ambiguous in T1:** what counts as a swing point; whether a break needs a candle *close*; how many touches are required (transcript 2 shows her counting six touches as "two"); what "intersected" means (wick or close); session rules; what to do when no opposite line exists; position sizing when the stop is far away; any statistics.

### 2.2 Transcript 2 ("I tested her strategy") — claims [T2‑claim] and what this project found

| # | Claim | This project's finding |
|---|---|---|
| 1 | "Take every trend line break… close to break‑even" — Tori's own words | **[VERIFIED in spirit]** 1H, all 4 markets, 3‑candle: NQ +$165k; ES ‑$63k, YM ‑$66k, RTY ‑$43k per mini. Only NQ is positive, and only 78% of random runs fall below it (not significant) |
| 2 | 1H: random entries do as well ~1 in 6 | Similar: 7–22% of random runs beat it on NQ; on ES/YM/RTY 25–97% of random runs beat it |
| 3 | 4H: $348k, only 2% of random entries kept up (10 markets) | **[PARTLY VERIFIED]** On 4 index markets the total is ≈ +$228k. On NQ 4H (3‑candle) only **5%** of random runs matched it |
| 4 | NQ contributed $224k | NQ 4H: **+$266k** (1 mini, 2019‑06→2026‑11) |
| 5 | S&P lost $28k | ES 4H: **‑$37k** (3‑candle), ‑$23k (5‑candle) |
| 6 | 3→5‑candle swings: random‑beat share rises from 15% to 30% (fragile) | **[VERIFIED]** NQ 4H drops from +$266k to +$85k; random beats it 32% of the time with 5‑candle pivots |
| 7 | Buy & hold beat it | **[VERIFIED]** NQ B&H +$369k vs +$266k, but with a similar max drawdown (~$125k vs ~$119k per mini) |
| 8 | 2022: B&H lost $251k, rule made $13k | **[VERIFIED direction]** 2022 4H: NQ +$64.6k, ES +$72.0k, RTY +$24.9k, YM +$1.0k vs B&H ‑$106k/‑$45k/‑$24k/‑$15k |
| 9 | Her A+ 2024 (17 trades, 76% wins, +180%) arises by chance ~3 in 10,000 | Not testable — her discretionary filter is not specified (cannot be coded) |
| 10 | Over‑risking: 12% risk on one trade, 40 contracts, removed stop, ‑$250k drawdown | Anecdote; this is the reason the bridge forbids stop widening and enforces size caps |

### 2.3 Strengths and weaknesses

* **Strengths:** the method can be fully systematised (pivots → rays → break/trail). The trailing exit lets winners run, and the method turns short in sustained declines (2022). It needs no indicators.
* **Weaknesses:** the edge is concentrated in one market (NQ) and one regime (2023–2024 trend). It is sensitive to swing definition. Win rate is low (28–37%) with long losing streaks (7–23). The opposite‑line stop is often very wide (median 37 MNQ points at 1H), so small accounts skip many trades. The edge disappears below 1H once costs are included.
* **Missing information:** swing definition, touch counting, break confirmation, session rules, sizing, statistics.

### 2.4 Improvements proposed and tested [PROPOSED]

Close‑based break confirmation (used). Breakout displacement (tested: **hurts**). Retest entry (C). Fan‑only bounces (D). Higher‑timeframe direction filter (E, **helps on MNQ**). Stop cap in ATR. $‑risk sizing. Intraday session window plus forced flat. An independent risk engine.

---

## 3. The objective trendline algorithm (Stage 3 / §5 of the brief)

Implemented in `research/tl/trendlines.py` and mirrored in the Pine script.

1. **Swing pivots:** a pivot high at bar *i* is the highest high of bars *i−k … i+k* and strictly higher than the *k* bars on its left. *k*=1/2/3 corresponds to the 3/5/7‑candle definitions. **A pivot is only used at bar i+k** (its confirmation bar), so there is no backdating.
2. **Resistance line:** Point B = the newly confirmed pivot high. Point A = the most recent earlier pivot high that is *higher* than B (searching back up to 12 pivots, at most 600 bars) such that:
   * no high between A and B pierces the ray by more than `tol`×ATR(14) (default 0.25), and
   * no close between B and the confirmation bar is above the ray.

   Searching from the most recent pivot backwards reproduces the "previous B becomes new A" fan. The counter `gen` tracks how many fan steps the line has taken.
3. **Support line:** the mirror image using pivot lows.
4. **Break:** a bar *close* beyond the line by more than `disp`×ATR (default 0). A broken line is deactivated and remembered for the retest logic.
5. **Replacement:** a newly built line replaces the active line on the same side ("adjust to the most recent touch point").
6. **No look‑ahead:** signals are evaluated on bar close with lines known at the previous bar, and orders fill at the next bar's open. `research/tests/test_no_lookahead.py` checks that truncating the data never changes earlier line states or completed trades. It passes.

**Strategy variants:**
* **A** — breakout: close through the opposite line. The stop is the other active line, or the last pivot if there is none.
* **B** — bounce: wick into the active line within `tol`×ATR, close back on the trend side with a candle in that direction. The stop sits beyond the line or the bar extreme.
* **C** — retest: after a break, price returns to the broken line within 10 bars and rejects it.
* **D** — bounce restricted to fan lines with `gen` ≥ 2.
* **E** — A/B/C restricted to the direction of the higher‑timeframe trendline (the direction of the last HTF line break, taken from the last *completed* HTF bar).
* **F** — hybrid of A, B and C with the E filter.

**Exits tested:**
* trendline trail (a stop order on the opposite line, ratcheting only)
* trendline trail plus break‑even after 1R
* ATR(2×) trail
* fixed 1R and 2R targets
* partial exit at 1R, then trail
* time stop (8 bars)
* forced flat on the first bar closing at or after 15:55 ET

**Execution model:**
* Stop fills include 1 tick of slippage and fill at the open if price gaps through.
* Targets must trade one tick through to fill.
* If the stop and the target are both hit in one bar, the stop is assumed to fill first.
* Commissions: $1.50 round turn (RT) for micros, $5.00 RT for minis.

---

## 4. Stage 4 — Backtest results

### 4.1 Raw edge by timeframe and strategy (intraday mode, $100 risk on micros, costs included, risk engine off)

From `reports/grid.csv`: 4 strategies × 3 pivot lengths × 7 exits × instruments.

| Exec TF | Mean expectancy (R per trade) A / B / C / D | Share of configs with PF > 1 (A) |
|---|---|---|
| 1H (2023–26) | +0.032 / ‑0.021 / +0.008 / ‑0.089 | 48% |
| 15M (2026) | ‑0.112 / ‑0.142 / ‑0.141 / ‑0.170 | 7% |
| 5M (Aug–Nov 2026) | ‑0.097 / ‑0.157 / ‑0.223 / ‑0.170 | 17% |
| 1M (9–12 days) | ‑0.084 / ‑0.077 / ‑0.051 / ‑0.095 | 10% |

* **Exits:** trendline trail, trail plus break‑even, ATR trail and the 8‑bar time stop all perform about the same (‑0.07 to ‑0.08R on average). Fixed targets are worse (1R: ‑0.14R; 2R: ‑0.11R). **The trailing exit beats fixed targets**, which supports transcript 1's preference.
* **By instrument (1H):** MNQ +0.028R, M2K +0.003R, MES ‑0.049R, MYM ‑0.052R. **Nasdaq‑specific**, as transcript 2 argued.

### 4.2 Costs and random entries (`reports/costs_random.csv`)

The random benchmark uses identical session, stop logic, sizing gates and exits, with only the entry bar and side randomised (60 runs).

* **Cost per trade:** 0.03–0.10R on 1H, 0.05–0.12R on 15M, 0.06–0.16R on 5M, 0.08–0.19R on 1M. MES is hit hardest because its stops are small relative to the $1.25 tick.
* **Gross vs net:** on 15M/5M, MES was gross‑negative or barely positive in every family. On MNQ 5M, breakout k=1 was gross +0.21R and net +0.13R, but over only 77 days.

### 4.3 Multi‑timeframe configurations 1–6 (`reports/mtf.csv`)

Average expectancy across instruments, k ∈ {1,2} and A/B/C, with vs without the HTF filter:

| Config | Bias → setup → execution | Without filter | With filter |
|---|---|---|---|
| 1 | 4H → 1H → 1H | +0.080R | **+0.155R** (63% of combos PF>1) |
| 2 | 1H → 15M → 15M | ‑0.121R | ‑0.097R |
| 3 | 1H + 15M → 5M | ‑0.165R | ‑0.084R |
| 4 | 15M → 5M → 5M | ‑0.165R | ‑0.162R |
| 5 | 15M + 5M → 1M | ‑0.041R | +0.040R (≈ 9–12 days; meaningless) |
| 6 | 5M → 1M | ‑0.041R | ‑0.031R |

**Your preferred 1H/15M/5M stack (config 3) is negative on average.** MNQ breakout‑only was +0.24R over 77 days, but MES was ‑0.09R and the sample is far too short. **It is not recommended for live trading.** It is worth forward‑testing in parallel only as a research item.

### 4.4 Consolidated timeframe comparison — same rules, risk engine on, $100 per trade (`reports/timeframe_comparison.csv`)

Strategy A with the HTF filter, MNQ. Days = RTH sessions in sample.

| Exec / HTF | Days | Trades/day | Win % | PF | Exp $ | Exp R | Net | Gross (no costs) | Net @2‑tick slip | Max DD | Avg hold | Longest loss streak | Profitable days | Days ≥ $250 / $500 / $1k |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1H / 4H | 1004 | 0.06 | 31% | 2.40 | 65 | 1.02 | 3,982 | 5,953 | 3,964 | 836 | 119 min | 8 | 31% | 9.8% / 3.3% / 3.3% |
| 1H / 4H (A+B+C) | 1004 | 0.17 | 37% | 1.65 | 28 | 0.36 | 4,849 | 6,015 | 4,764 | 1,244 | 126 min | 7 | 39% | 6.9% / 2.5% / 1.9% |
| 15M / 1H | 232 | 0.61 | 29% | 1.28 | 13 | 0.18 | 1,861 | 3,472 | 1,126 | 2,767 | 46 min | 13 | 33% | 4.5% / 2.7% / 1.8% |
| 5M / 1H+15M | 77 | 1.70 | 28% | 1.39 | 16 | 0.24 | 2,119 | 2,854 | 1,953 | 2,150 | 25 min | 13 | 30% | 8.2% / 4.9% / 3.3% |
| 5M / 15M | 77 | 2.64 | 27% | 1.25 | 11 | 0.15 | 2,174 | 3,065 | 2,356 | 3,131 | 24 min | 14 | 29% | 12% / 6.8% / 2.7% |
| 1M / 5M | 9 | 3.44 | 13% | 0.31 | ‑40 | ‑0.49 | ‑1,252 | ‑1,376 | ‑1,242 | 1,430 | 3 min | 10 | 22% | 0 |

The same table for MES is negative on every timeframe except 1M (42–44 trades over 12 days, which is noise).

* Lower timeframes do produce more trades per session and shorter holds. They also bring a higher commission share, longer losing streaks and **larger drawdowns per dollar of profit**.
* No timeframe produced a daily‑loss‑limit breach, because the risk engine caps each day.

**Ranking** (out‑of‑sample expectancy → drawdown → survival → consistency → net after costs → execution → frequency):

1. **1H execution / 4H bias.** It is the only configuration positive across multiple years with walk‑forward support, and has the lowest drawdown.
2. 15M / 1H. Positive on MNQ only, in one year; MES negative; drawdown is 3× that of 1H.
3. 5M / 1H+15M. Positive on MNQ over 77 days only; MES negative.
4. 4H as executed by Tori (overnight holding). It is the best raw P&L per contract, but holding overnight is not allowed on the prop account, and the per‑mini drawdown (about $119k) is incompatible with a $2,000 trailing drawdown.
5. **1M — rejected:** negative after costs on MNQ, the sample is insufficient, and the cost share is high.

**Adaptive timeframe selection** (switching between 15M, 5M and 1M by regime) was **not implemented**. None of the lower timeframes has a positive, stable base edge to switch into, so any switching rule would be curve‑fitting.

### 4.5 Final candidate deep‑dive: MNQ, 1H A+B+C, 4H filter, k=1 (`reports/cand_*.csv`, `final_*.csv`)

* **Robustness (MNQ, HTF on, 216 parameter combinations):**
  * Pivot length: k=1 +0.28R (76% PF>1); k=2 +0.22R (58%); **k=3 ‑0.22R (19%)**. Fragile to long pivots.
  * Touch tolerance 0.15/0.25/0.40: +0.05/+0.11/+0.12R. Insensitive above 0.25.
  * Breakout displacement 0/0.1/0.25 ATR: +0.18/+0.12/‑0.02R. Displacement **hurts**.
  * Exit: trendline trail +0.19R, break‑even +0.19R, fixed 2R ‑0.10R.
  * Other instruments with the same filter: MES ‑0.095R, MYM +0.007R, M2K ‑0.021R. **It does not generalise.**
* **Walk‑forward** (12‑month in‑sample → 6‑month out‑of‑sample, rolling, choosing among 48 configurations by in‑sample R): 5 of 6 OOS windows positive; OOS total 36 trades, **+0.58R per trade, PF 1.96, +$1,468**. The parameter choice moved between windows (k 1↔2, A/B/C), and the trade counts are tiny.
* **Random benchmark** (500 runs, trade count calibrated to 164–171 trades):
  * Unfiltered random entries: mean +0.03R, 95th percentile +0.47R. The strategy's +0.36R **beats 90.2%**.
  * Random entries in the 4H direction: mean +0.18R, 95th percentile +0.65R. The strategy **beats only 75.2%**.

  So the 4H direction contributes about half the edge, and the 1H trendline trigger adds roughly another +0.18R that is **not statistically significant**.
* **Long vs short:** long 85 trades +0.37R; short 89 trades +0.35R. Symmetric, which is good.
* **By year:** 2023 +0.45R (+$2,174); 2024 +0.56R (+$2,778); 2025 +0.12R (+$150); 2026 ‑0.28R (‑$253, 11 trades). **The edge is decaying.** 18 of 41 months were positive.
* **Session buckets (entry time):** 10:00–11:30 +0.14R (72 trades); 11:30–13:00 +1.02R (20); 13:00–14:30 +0.37R (54); 14:30–16:00 +0.43R (28). There are no 09:30 entries, because the first 1H bar closes at 10:00. The morning bucket is the weakest, but the buckets are too small to justify a filter. **No session filter beyond 10:00–15:30 is adopted.**
* **Exits:** 101 stop‑outs (‑0.87R average) and 73 session‑flat exits (+2.06R average). The edge comes from riding intraday trends to the close.
* **Risk per trade as a hidden filter:** with $100 risk, only setups whose stop is ≤ ~47 MNQ points are taken (median 37 points, almost always 1 contract). At $150 and $250 more wide‑stop setups are admitted, and PF falls to 1.33 and 1.31. **Keep the risk per trade at $100–$150.**

### 4.6 Risk engine, daily objectives and prop survival (`reports/risk_engine.csv`)

**Prop model (third‑party‑reported, see PROP_RULES.md):** $2,000 end‑of‑day trailing drawdown (it stops trailing at the starting balance) and a $1,000 daily loss limit. The **$3,000 evaluation target is an [ASSUMPTION].** The simulation is a 5‑day block bootstrap of daily P&L, 4,000 paths, with a 500‑trading‑day horizon.

| Config | Risk/trade | Net | PF | Max DD | Pass | Fail | Median days to pass |
|---|---|---|---|---|---|---|---|
| 1H A+B+C | $100 | $4,849 | 1.65 | $1,244 | 40% | **1.4%** | 315 |
| 1H A+B+C | $150 | $5,934 | 1.33 | $2,239 | 55% | 21% | 250 |
| 1H A+B+C | $250 | $13,748 | 1.31 | $3,562 | 60% | 40% | 105 |
| 1H A only | $150 | $7,978 | 2.26 | $1,587 | 48% | 3.8% | 230 |
| 15M A (1H filter) | $100 | $1,861 | 1.28 | $2,767 | 49% | **50%** | 100 |
| 5M A (1H filter) | $100 | $2,754 | 1.32 | $1,921 | 64% | 36% | 45 (77‑day sample, unreliable) |

The remainder of each "Pass + Fail" row is paths still open at 500 days.

* **Daily profit objectives:** at the recommended $100 risk, days reaching $250 / $500 / $750 / $1,000 = **6.9% / 2.5% / 2.5% / 1.9%**. Not one day breached the $550 or $700 internal limits. The design guarantees this, apart from gaps.
* **Profit lock** ($250 / $500 / $1,000): no measurable effect at 1H, because there are almost never two trades in a day. On 5M a $250 lock *reduced* net profit by 47%. **No profit lock.**
* **Conclusion:** the $1,000 daily objective is roughly 10× the realistic *monthly* expectation at safe size. **Recommended daily objective: none.** Use a monthly expectation of about $100–$150 at $100 risk, and judge the system on 50+ trades, not on days.

---

## 5. Stage 5 — Final strategy design

**Selected:** Configuration 1 + Strategy F (hybrid A+B+C with the E filter) on **MNQ**, 1H execution, 4H direction.

* **Why selected:**
  * It is the only configuration that is positive in 2023, 2024 and 2025 and in walk‑forward OOS.
  * It has the lowest drawdown per dollar.
  * It has the lowest simulated prop failure rate (1.4% at $100).
  * Costs are a small share (~19% of gross).
  * Long and short sides are symmetric.
* **What makes it profitable (to the extent it is):**
  * Trading only in the direction of the last 4H trendline break captures Nasdaq's intraday trend persistence.
  * Holding winners to the 15:55 flat produces large session‑flat winners (+2.1R average) against ‑0.87R stop‑outs.
* **Weaknesses:**
  * Low frequency (~1 trade a week).
  * Instrument‑specific (fails on MES).
  * Decaying 2025–26 results.
  * Sensitive to pivot length (k=3 fails).
  * The trendline trigger itself adds little over a random entry in the 4H direction.
  * 1H bars cannot enter before 10:00 ET.
* **Optimal hours:** signal‑bar close between 10:00 and 15:30 ET; forced flat at the bar closing ≥ 15:55 ET.
* **Instrument:** MNQ (micro). NQ minis would need stops ≤ ~4.5 points at $100 risk, so nearly every setup would be skipped.
* **Position sizing:** contracts = floor($risk ÷ (stop points × $2 + $1.50 + 2 ticks × $0.50)), capped at 50 micros. Skip the trade if the result is < 1. Never widen the stop.
* **Expected frequency:** ~0.17 trades per day (≈3–4 per month).
* **Daily risk limits:**
  * No new trade if a full stop‑out could take the day below ‑$550.
  * Hard flatten at ‑$700 realised + open.
  * At most 4 trades per day; stop after 3 consecutive losses.
  * The prop‑reported $1,000 daily loss limit and $2,000 trailing drawdown sit outside these internal limits.

---

## 8. Stage 8 — Final operating parameters

| Parameter | Final recommendation |
|---|---|
| Futures instrument | **MNQ** (Micro E‑mini Nasdaq‑100). One instrument at a time; no MES/MYM/M2K alongside it |
| Account size | $50,000 (IQ Capital 50K DLL, rules per PROP_RULES.md) |
| Execution timeframe | **1 hour** |
| Higher timeframe | **4 hour** trendline‑break direction (previous completed 4H bar) |
| Trading session | Signal‑bar close 10:00–15:30 ET; flat by the bar closing ≥ 15:55 ET; no overnight or weekend positions |
| Entry methodology | 3‑candle pivots (k=1), deterministic fan trendlines, touch tolerance 0.25 ATR, no displacement. Enter on (A) close through a line, (B) bounce off the active line, or (C) retest of a broken line — only in the 4H direction. Fill at the next bar open |
| Stop‑loss methodology | A: opposite active trendline (else last swing) ± 1 tick. B/C: beyond the line or bar extreme by 0.1 ATR. Skip if the stop is > 4 ATR or < 4 ticks |
| Take‑profit methodology | **None** (fixed targets tested worse); session flat |
| Trailing‑stop methodology | Stop order on the active opposite trendline, recomputed each bar, ratchet‑only |
| Risk per trade | **$100** (max $150). Do not raise to "make more trades" — wider stops lower expectancy |
| Maximum daily loss | **$700** hard flatten (internal); prop DLL $1,000 per third‑party sources — verify |
| Internal shutdown | **$550** (no trade that could breach it) |
| Daily profit objective | **None.** Realistic expectation ≈ $100–150/month at $100 risk. $1,000/day rejected |
| Maximum trades per day | **4** (the strategy averages 0.17) |
| Maximum consecutive losses | **3** per day, then halt for the day |
| Automation platform | TradingView `alert()` webhooks → self‑hosted bridge (`bridge/`) with independent risk engine → Tradovate API → IQ Capital account. **Blocked until IQ Capital confirms automation and API access in writing** |

---

## 9. Reproducing everything

```bash
pip install pandas numpy pytest
cd research
python3 run_grid.py            # 4.1  strategy x TF x instrument x pivot x exit
python3 run_costs.py           # 4.2  cost decomposition + random baseline
python3 run_replication.py     # 2.2  transcript-2 replication, 4H/1H, B&H, by year
python3 run_mtf.py             # 4.3  multi-timeframe configs 1-6
python3 run_candidate.py       # 4.5  sensitivity, walk-forward, breakdowns
python3 run_random_cal.py      # 4.5  calibrated random benchmark
python3 run_risk.py            # 4.6  risk engine, daily objectives, prop survival
python3 run_final.py           # 4.4  consolidated timeframe table + final trades
python3 -m pytest -q tests ../bridge/tests
```

To extend the data (for example more 5M/1M history, or YM/RTY lower timeframes), pull bars with TradingView `get_ohlcv` and save them as JSON dumps. Then run `research/ingest.py <dir>`; it de‑duplicates and merges into `data/raw/{SYM}_{TF}.csv` (columns t,o,h,l,c,v; t = bar‑open unix seconds UTC).
