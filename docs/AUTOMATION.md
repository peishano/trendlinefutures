# Stages 6–7 — Pine Script strategy, alerts, webhook bridge, deployment

> **Compliance gate:**
> * Third‑party reviews state that IQ Capital prohibits bots and automated trading, and its official policy could not be read from this environment (see `PROP_RULES.md`).
> * Prop accounts also often lack Tradovate API access.
> * **Do not connect the bridge to the IQ Capital account until IQ Capital has confirmed both in writing.**
> * Until then, use the bridge only with `PaperBroker` or a personal Tradovate demo account.

## 6. Pine Script v6 strategy

File: `pine/TrendlineFan_Prop_v1.pine`.

**Compile status: COMPILES, 0 errors, 0 warnings in the trading logic** (TradingView validator, 2026‑11‑26).
The only remaining note is TradingView's standard reminder that `barstate.islast` is evaluated on confirmed bars; it only affects the status table.

**TradingView backtest (Deep Backtesting, CME_MINI:MNQ1! 1H, 2023‑01‑03 → 2026‑11‑25, default inputs):**

| | Python engine (Pine's 4H timing) | TradingView |
|---|---|---|
| Trades | 169 | 178 |
| Net profit | +$4,277 | +$3,440 |
| Profit factor | 1.59 | 1.45 |
| Win rate | — | 33.7% |
| Max drawdown | $1,260 | $1,375 |
| Long / short net | — | +$785 / +$2,656 |

The two engines agree within ~5% on trade count. The remaining P&L gap comes from:
* fill and rounding details,
* ATR seeding,
* MNQ1! vs NQ1! roll handling.

With the Python engine's own HTF timing (which uses the 4H bar that has just closed), the result is +$4,849 / PF 1.65. The Pine script deliberately uses the one‑bar‑more‑conservative, non‑repainting timing.

**Required setting: margin 0%.** The strategy declares `margin_long = 0, margin_short = 0`. With TradingView's default 100% margin, 2–3 MNQ contracts (about $72k notional) exceed the $50k equity. TradingView then silently caps size at 1 contract, skips trades, and issues false "margin call" exits; the first compile run showed only +$652 for this reason. Futures margin is enforced by the broker or prop firm, not by the backtester.

### Add it to TradingView

1. Open a **MNQ1!** chart on the **1 hour** timeframe, using exchange time (America/New_York) and the ETH session.
2. Open the Pine Editor, create a new strategy, replace its contents with the file, and click **Save** then **Add to chart**.
3. Open the Strategy Tester.
   * In **Properties**: initial capital 50,000; commission $0.75 per contract per side (that is, $1.50 per round turn); slippage 1 tick.
   * Leave "Recalculate on every tick" **off**.
4. Default inputs equal the researched configuration:
   * k=1, tolerance 0.25, displacement 0
   * setups A, B and C on, 4H filter on
   * Trendline‑trail exit
   * session 10:00–15:30, flat at 15:55
   * risk $100, shutdown $550, hard daily loss $700, 4 trades per day, 3 consecutive losses
5. **Parity check:** export the List of Trades for 2023‑01‑01 → today and compare it with `reports/final_trades.csv`. You should see similar counts (~170), a similar long/short split and PF in the 1.4–1.9 range.

   Known, deliberate differences:
   * The Pine HTF filter uses the previous *completed* 4H bar through the `lookahead_on` + `[1]` idiom. On the last 1H bar of each 4H block, that is one bar more conservative than the Python engine.
   * The session flat fills at the next bar's open in Pine, but at the bar close in Python.
   * TradingView's own continuous‑contract roll handling may differ.

### What the script does

* **Trendlines:** pivots confirmed `k` bars late, so there is no repainting. The fan lines are drawn: active rays plus the last 6 replaced lines per side.
* **Signals and orders:** A/B/C signals are evaluated on bar close. Orders fill at the next open. Stops are maintained with `strategy.exit` on the opposite trendline and are ratchet‑only.
* **Risk:**
  * Sizing from $ risk, tick value and costs; the trade is skipped if it comes to fewer than 1 contract.
  * `strategy.risk.max_intraday_loss(700)`.
  * An internal $550 shutdown gate.
  * Trade‑count and consecutive‑loss limits.
  * Forced session flat.
* **Status table:** HTF direction, day P&L, trades, consecutive losses, open risk, shutdown status, risk per trade, and line generation.
* **Webhook messages:** emitted with `alert()` (JSON), described in §7.2.

## 7. Automation architecture

```
TradingView (MNQ1! 1H, strategy on bar close)
   └─ alert(): JSON  ──HTTPS POST──►  reverse proxy (TLS, port 443; allow TradingView IPs only)
                                         └─► bridge/server.py  (/webhook)
                                               ├─ secret check, schema check, idempotency (SQLite)
                                               ├─ RiskEngine  (independent veto; bridge/risk.py)
                                               ├─ Broker adapter: PaperBroker | TradovateBroker
                                               │      └─► Tradovate API (market + OSO stop) ─► IQ Capital account
                                               └─ watchdog (every 2 s): mark P&L, hard daily loss, 15:58 flat,
                                                  heartbeat-loss flatten, kill switch
```

TradingView webhooks need a paid plan with 2FA enabled, and are sent only to ports 80/443. TradingView publishes the IP addresses its webhooks come from; allow‑list those at the proxy, and check the current list in TradingView's documentation.

### 7.1 Alert configuration

1. Strategy on the chart → **Create Alert**.
2. Condition: *Trendline Fan Prop v1* → **"alert() function calls only"**.
3. Expiration: open‑ended (renew it where your plan requires).
4. Webhook URL: `https://<your-domain>/webhook`.
5. Message: leave it empty. The script supplies the JSON.
6. Set the `secret` input in the script to the same value as `secret` in the bridge config.

The `secret` is visible to anyone who can see your chart inputs. Keep the chart private and rotate the secret if you share it.

### 7.2 Webhook message templates (produced by the script)

```json
{"secret":"…","bot":"TLFAN1","id":"TLFAN1-1764090000000-L","action":"entry","side":"buy","symbol":"MNQ",
 "qty":1,"stop":21234.25,"target":null,"risk_usd":96.0,"bar_time":1764086400000}
{"secret":"…","bot":"TLFAN1","id":"TLFAN1-1764090000000-L","action":"modify_stop","side":"buy","symbol":"MNQ",
 "qty":1,"stop":21251.5,"target":null,"risk_usd":0,"bar_time":1764090000000}
{"secret":"…","bot":"TLFAN1","id":"TLFAN1-1764090000000-L","action":"flatten","side":"none","symbol":"MNQ",
 "qty":0,"stop":null,"target":null,"risk_usd":0,"bar_time":1764100800000}
{"secret":"…","bot":"TLFAN1","action":"sync","symbol":"MNQ","position":1,"stop":21251.5,"day_pnl":42.5,
 "halted":false,"bar_time":1764090000000}
```

* **Unique trade ID:** `bot-<bar close ms>-<L|S>`. Idempotency key: `bot|id|action|stop`. A repeated alert is acknowledged but not executed.
* **Order type:** market entry, which in practice fills at the next bar's open. It is immediately protected by a broker‑side **stop‑market** order (an OSO bracket). There is no limit target.
* **Contract selection:** the bridge maps the root `MNQ` to the front month (configure `symbol_map`, e.g. `MNQZ6`), and must roll it before the roll date, the Thursday before expiry week.
* **Reference price:** add `"ref_price":{{close}}` to the alert message if you use `PaperBroker` without a price feed.

### 7.3 Risk controls enforced by the bridge (independent of TradingView)

`bridge/risk.py` defaults, with values in `bridge/config.example.json`:

| Control | Setting |
|---|---|
| Hard daily loss (realised + open, net of costs) | $700 → flatten all and halt for the day |
| Internal shutdown | Rejects any entry whose full stop‑out could take the day below ‑$550; halts at ‑$550 realised |
| Max risk per trade | $150 (size is capped, and the entry is rejected if 1 contract exceeds it) |
| Max open risk | $150 (only one position at a time) |
| Max trades per day / consecutive losses | 4 / 3 |
| Correlated instruments | MNQ, NQ, MES, ES, MYM and M2K count as one bucket: no second position |
| Entry window / forced flat | 09:30–15:35 ET / 15:58 ET; the day rolls at 18:00 ET |
| Stop required, stop direction | Entry rejected without a valid stop; stop modifications can only **tighten** |
| Allowed instruments | `["MNQ"]` |
| Duplicate protection | SQLite idempotency table survives restarts |
| Connection failure / rejection | A broker exception means no position is assumed. Errors are journaled, and after 3 errors the kill switch engages |
| Heartbeat | If no `sync` arrives within 90 minutes while a position is open, everything is flattened |
| Emergency shutdown | `POST /admin/flatten {"token":…}` flattens everything and engages the kill switch; `POST /admin/kill` toggles it. A broker‑side daily loss limit in Tradovate's risk settings is a second, independent layer — set it as well |

Tests: `python3 -m pytest -q bridge/tests` (7 tests).

### 7.4 Deployment

1. Use a small Linux VPS (US‑East), Python ≥ 3.10, with no extra packages. Put Caddy or nginx in front for TLS on port 443, allow‑list TradingView's IPs, and forward to `127.0.0.1:8080`.
2. `cp bridge/config.example.json bridge/config.json`, then set long random values for `secret` and `admin_token`. Never commit this file.
3. Run it as a systemd service: `python3 -m bridge.server --config bridge/config.json`. Use `Restart=always`, and log to journald plus the SQLite journal.
4. **Paper mode first** (`PaperBroker`). For Tradovate, construct `TradovateBroker` with API credentials and an account ID **only after** IQ Capital approval. This adapter is untested against a live endpoint.
5. Monitoring: poll `GET /health` from an uptime checker and send an alert if the process is down or `halted=true`.
6. Fill feedback is not implemented: real fills and P&L must come from the Tradovate websocket (`user/syncrequest`). Implement that before going live.

### 7.5 Paper‑trading validation procedure

1. **Backtest parity:** the TradingView Strategy Tester and `reports/final_trades.csv` agree, as described in §6 step 5.
2. **Signal parity, live:** run the strategy on MNQ1! 1H with alerts going to the bridge in `PaperBroker` mode. Every Friday, compare the bridge journal against the TradingView List of Trades: entries, stops, exits and session flats.
3. **Fault drills:**
   * Kill the bridge mid‑position: the broker‑side stop must still protect the position.
   * Send a duplicate alert: it must be ignored.
   * Send a wide‑stop or out‑of‑hours entry: it must be rejected.
   * Force a ‑$700 open loss: it must flatten.
   * Lose the heartbeat: it must flatten.
4. **Demo broker:** run 4–8 weeks on a Tradovate demo account with `TradovateBroker`. Compare fills against TradingView bar opens to measure real slippage; it should average ≤ 1 tick per fill.
5. **Go/no‑go:** at least 30 forward trades (about 2 months at 3–4 per month; realistically 3 months or more).
   * Forward expectancy > 0.
   * No risk‑rule violation.
   * Average slippage ≤ 1 tick.
   * Written approval from IQ Capital for automation.

   If any of these fails, stop and re‑evaluate.
