# trendlinefutures

Research, backtest and automation package for a systematic trendline futures strategy. It was built from two transcripts: Tori Trades' trendline method, and a third‑party test of that method. The target is a $50K IQ Capital DLL prop account.

**Bottom line:**
* The transcript‑2 critique replicates.
* 15M, 5M and 1M trendline strategies lose money after costs.
* The only configuration that holds up is **MNQ, 1H trendline entries in the 4H trendline direction**. It is a modest edge: about 0.36R per trade and about 3–4 trades a month, and weakening in 2025–26.
* $1,000 a day is not realistic.
* IQ Capital may prohibit automation (unverified), so confirm before going live.

| Path | Contents |
|---|---|
| `docs/RESEARCH_REPORT.md` | Stages 1, 3, 4, 5, 8 — transcript analysis, algorithm, all backtests, final spec |
| `docs/PROP_RULES.md` | Stage 2 — prop‑firm rules (third‑party‑sourced, unverified), questions for IQ Capital |
| `docs/NEXT_STEPS.md` | Goal feasibility (2 trades/day, $700/week), audit, next approach, paper-test setup |
| `docs/AUTOMATION.md` | Stages 6–7 — Pine setup, alerts, webhook templates, bridge, deployment, paper‑trading plan |
| `pine/TrendlineFan_Prop_v1.pine` | Production Pine Script v6 strategy (compiles; TradingView backtest PF 1.45 vs Python 1.59 — see AUTOMATION.md) |
| `research/` | Python backtester (`tl/`), experiment scripts (`run_*.py`), no‑look‑ahead tests |
| `bridge/` | Webhook execution bridge with an independent risk engine + tests |
| `reports/` | CSV outputs of every experiment |
| `data/raw/` | TradingView OHLCV (NQ/ES/YM/RTY; 4H, 1H, 15M, 5M, 1M), bar-open unix seconds UTC |
