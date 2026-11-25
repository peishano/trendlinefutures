# Stage 2 — IQ Capital 50K DLL ("DDL Promo") rule verification

**Status: NOT VERIFIED AGAINST OFFICIAL DOCUMENTATION.**

* This environment's network policy blocked IQ Capital's site (iqcapital.io) and the review sites, so the official help centre could not be fetched.
* Web search (2026‑11‑25) returned only third‑party summaries, and these conflict with each other.
* Every value below is third‑party‑sourced or UNKNOWN. **Confirm each one in writing with IQ Capital before trading.**

| Rule | What sources say (2026‑11‑25) | Status | Value used by the risk engine |
|---|---|---|---|
| Daily loss limit (50K DLL) | $1,000 (2%). One source lists $1,300 for the Flex plan | Third‑party | Internal $700 hard / $550 shutdown (stricter) |
| Breach type | Accounts bought on/after 9 Nov 2026: positions closed and trading locked for the rest of the day; the account stays open ("soft breach"). Older accounts reportedly allowed one violation | Third‑party | Treat as hard; internal limits trigger first |
| Max drawdown | $2,000 **end‑of‑day trailing**, based on the highest EOD balance; stops trailing once it reaches the starting balance | Third‑party | Used in the survival simulation |
| Unrealised P&L counts? | Not stated | **UNKNOWN** | Assumed yes (engine counts realised + open) |
| Commissions count toward drawdown? | Not stated | **UNKNOWN** | Assumed yes (all P&L is net of costs) |
| Daily reset time / timezone | Not stated; flat‑time sources say 4:45 PM ET or 5:00 PM ET | **UNKNOWN** | Day rolls 18:00 ET; flat by 15:55–15:58 ET (earlier than both) |
| Max contracts | 5 minis / 50 micros (50K); cannot hold minis and micros together | Third‑party | 50‑micro cap; MNQ only |
| Permitted instruments | CME equity index futures listed generally; per‑symbol list not found | **UNKNOWN** | MNQ only |
| News trading | "Permitted" (stated for the Rapid plan) | Third‑party (different plan) | No news filter in the strategy; consider pausing around FOMC/CPI |
| Overnight / weekend holding | Intraday only; no overnight or weekend holds | Third‑party | Forced flat every session |
| Hedging | Prohibited | Third‑party | Bridge blocks simultaneous correlated positions |
| Consistency rule | Evaluation: none. Funded: 30% or 40% best‑day rule (conflicting) | Third‑party, conflicting | Not modelled. The strategy's best day ($1,614) is ~33% of total P&L over 3.9 years — check against the actual rule |
| Profit target, min days, payout split | Not found for the DLL 50K | **UNKNOWN** | $3,000 target assumed in the simulation |
| Platform / data | DLL variants on Tradovate; other plans dxFeed (NinjaTrader, Quantower, ATAS, DeepCharts, TradingView) | Third‑party | Tradovate adapter (untested) |
| **Automated trading / bots / copy trading** | "Automated trading (EAs/Bots) and Copy trading are strictly prohibited"; "Bots and copy trading are prohibited" | Third‑party, **not officially confirmed** | **BLOCKER** — no live automation without written permission |
| Promo‑specific rules ("DDL Promo") | No promo‑specific terms found | **UNKNOWN** | — |

**Questions to send IQ Capital (copy/paste):**

1. For the 50K Core DLL account bought on [date]:
   * What is the exact daily loss limit?
   * Is it balance‑ or equity‑based, and does it include open P&L and commissions?
   * What is the reset time and timezone?
2. What is the drawdown type and amount, and at what balance does it stop trailing?
3. What is the latest time positions must be flat each day?
4. What are the contract limits and the list of permitted products?
5. Is fully automated trading permitted? Specifically: TradingView alerts → webhook → my own server → Tradovate API orders, with my own risk controls. Is Tradovate API access available on this account?
6. What are the consistency rules and the profit target for the evaluation and funded stages?
7. Are there any restrictions around news releases?

**Sources consulted (third‑party, accessed 2026‑11‑25 via web search snippets; not read in full):**

* [PropFirmMap — IQ Capital review](https://propfirmmap.com/firms/iqcapital)
* [PropFirmMap blog](https://propfirmmap.com/blog/iqcapital-review)
* [ProFuturesTrading](https://profuturestrading.de/prop-firms/iq-capital/)
* [propfirm.compare](https://propfirm.compare/propfirm/iq-capital)
* [propfirm.compare Core 50K](https://propfirm.compare/propfirm/iq-capital/core/50k)
* [propfirm.compare Rapid 50K](https://propfirm.compare/propfirm/iq-capital/rapid/50k)
* [PropFirmsRadar](https://propfirmsradar.com/prop-firm/iqcapital)
* [propfirm-discounts](https://propfirm-discounts.com/iq-capital-review/)
* [JoinProp](https://joinprop.com/prop-firm/iq-capital/)
* [DamnPropFirms](https://damnpropfirms.com/futures-prop-firms/iq-capital/)
* [funded.now Core‑DLL 50K](https://funded.now/propfirm/iq-capital/futures-core-dll-50000)
* [funded.now Flex 50K](https://funded.now/propfirm/iq-capital/futures-flex-50000)
* [Consistry](https://www.consistry.com/prop-firm-rules/iq-capital)
* [H2T Funding](https://h2tfunding.com/reviews/iq-capital/)
* [Kagels Trading](https://kagels-trading.com/blog/iq-capital-review/)
* [OnlyPropFirms](https://onlypropfirms.com/articles/iq-capital-prop-firm-review)
* [FundingCodes](https://fundingcodes.com/blog/iq-capital-review/)
* [SaveOnPropFirms](https://saveonpropfirms.com/prop-firms/iq-capital/rules)
* Official homepage (not readable from here): [iqcapital.io](https://www.iqcapital.io/)
