"""Event-driven bar backtester for the trendline strategy family.

Execution model (no look-ahead):
* Signals are evaluated on the CLOSE of bar t using only lines known at t-1
  (breaks) or after t (stops for the next bar); orders fill at the OPEN of t+1.
* Stop orders: fill at stop price (or the open if it gapped through), minus
  `slip` ticks of adverse slippage. Limit targets fill only if price trades
  THROUGH the target by one tick, no slippage. If stop and target are both
  inside one bar the stop is assumed to fill first (pessimistic).
* Costs: round-turn commission per contract + slippage on every market/stop fill.
* Risk engine (independent of signals): per-trade $ risk sizing, max daily
  trades, consecutive-loss shutdown, "a new trade may not be able to take the
  day below -shutdown", hard intraday equity stop (realised + open) at
  -daily_max_loss, optional daily profit lock, cooldown after a loss.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from .data import Spec, atr as calc_atr
from .trendlines import build, Lines


@dataclass
class Cfg:
    strat: str = 'A'                 # A breakout, B bounce, C retest, D fan bounce, R random
    k: int = 2                       # pivot half-width (1=3-candle, 2=5-candle, 3=7-candle)
    tol: float = 0.25                # touch tolerance in ATR
    disp: float = 0.0                # breakout displacement in ATR
    min_touch: int = 2               # minimum touches for a line to be traded (bounce types)
    exit: str = 'tl'                 # tl | fixed | atr | partial | be | time
    stop_mode: str = 'tl'            # for breakouts: tl (opposite trendline) | atr | pivot
    stop_atr: float = 1.5
    target_r: float = 2.0
    trail_atr: float = 2.0
    max_hold: int = 0                # bars; 0 = unlimited (subject to session flat)
    max_stop_atr: float = 4.0        # skip setups with wider stops
    min_stop_ticks: int = 4
    retest_win: int = 10
    sess: tuple | None = (9 * 60 + 30, 15 * 60 + 30)   # signal-bar close window (ET minutes); None = 24h
    flat_min: int | None = 15 * 60 + 55                # force flat on first bar closing >= this; None = hold overnight
    reverse: bool = False            # stop-and-reverse (transcript-2 replication)
    long_only: bool = False
    short_only: bool = False
    # sizing / risk
    fixed_qty: int = 0               # >0 = trade fixed contracts, ignore $ risk sizing
    risk: float = 100.0
    slip: int = 1                    # ticks per market/stop fill
    daily_shutdown: float = 550.0
    daily_max_loss: float = 700.0
    max_trades: int = 6
    max_consec: int = 3
    profit_lock: float = 0.0         # stop new entries once day P&L >= this (0 = off)
    cooldown: int = 0                # bars to wait after a losing trade
    risk_engine: bool = True
    seed: int = 0                    # for random entries
    rand_p: float = 0.0              # per-bar entry probability for strat R


def htf_direction(df_htf: pd.DataFrame, L: Lines) -> pd.Series:
    """+1 after a resistance break, -1 after a support break (persisting), per HTF bar."""
    d = np.zeros(len(df_htf))
    cur = 0
    for i in range(len(df_htf)):
        if L.r_break[i]:
            cur = 1
        if L.s_break[i]:
            cur = -1
        d[i] = cur
    return pd.Series(d, index=df_htf.close_ts)


def align_htf(df: pd.DataFrame, htf_dir: pd.Series) -> np.ndarray:
    """Value of the last COMPLETED HTF bar at each LTF bar close (no look-ahead)."""
    h = htf_dir.reset_index(); h.columns = ['close_ts', 'dir']
    m = pd.merge_asof(df[['close_ts']].sort_values('close_ts'), h.sort_values('close_ts'),
                      on='close_ts', direction='backward')
    return m.dir.fillna(0).values


def run(df: pd.DataFrame, spec: Spec, cfg: Cfg, L: Lines | None = None, atr: np.ndarray | None = None,
        htf: list[np.ndarray] | None = None) -> pd.DataFrame:
    o, h, l, c = (df[x].values for x in ('open', 'high', 'low', 'close'))
    n = len(c)
    if atr is None:
        atr = calc_atr(df)
    if L is None:
        L = build(h, l, c, atr, cfg.k, cfg.tol, cfg.disp, 2)
    tick, pv = spec.tick, spec.pv
    slip = cfg.slip * tick
    tday = df.tday.values
    cmin = df.close_min.values
    ts = df.ts.values
    rng = np.random.default_rng(cfg.seed)

    trades = []
    pos = 0; qty = 0; entry = 0.0; stop = np.nan; target = np.nan; ebar = 0; risk_pts = 0.0
    part_done = False; qty_open = 0; realized_trade = 0.0; mae = 0.0
    pend = None          # pending entry: (dir, stop, qty) to fill at next open
    pend_exit = None     # pending market exit reason at next open
    retest_long = None; retest_short = None
    day = None; day_pnl = 0.0; day_trades = 0; consec = 0; halted = False; cool_until = -1

    def close_trade(px, reason, t):
        nonlocal pos, qty_open, day_pnl, consec, cool_until, realized_trade
        pnl = realized_trade + pos * (px - entry) * pv * qty_open - spec.rt_cost * qty_open
        trades.append((ts[ebar], ts[t], pos, qty, entry, px, pnl, pnl / (risk_pts * pv * qty) if risk_pts > 0 else np.nan,
                       t - ebar + 1, reason, tday[ebar], df.open_min.values[ebar], mae))
        day_pnl += pnl
        if pnl < 0:
            consec += 1; cool_until = t + cfg.cooldown
        else:
            consec = 0
        pos = 0; qty_open = 0; realized_trade = 0.0

    def in_sess(t):
        if cfg.sess is None:
            return True
        a, b = cfg.sess
        return a <= cmin[t] <= b

    for t in range(1, n):
        # ---- new trading day: reset daily counters
        if tday[t] != day:
            day = tday[t]; day_pnl = 0.0; day_trades = 0; consec = 0; halted = False
        # ---- fills at the open of bar t
        if pend_exit is not None and pos != 0:
            close_trade(o[t] - pos * slip, pend_exit, t)
            pend_exit = None
        if pend is not None:
            d, st, q = pend; pend = None
            if pos != 0:  # reverse: flatten first
                close_trade(o[t] - pos * slip, 'reverse', t)
            px = o[t] + d * slip
            if (d > 0 and st < px) or (d < 0 and st > px):
                pos = d; qty = q; qty_open = q; entry = px; stop = st; ebar = t
                risk_pts = abs(px - st); part_done = False; realized_trade = 0.0; mae = 0.0
                target = px + d * cfg.target_r * risk_pts if cfg.exit in ('fixed',) else np.nan
                if cfg.exit == 'partial':
                    target = px + d * 1.0 * risk_pts
                day_trades += 1
        # ---- intrabar exits
        if pos != 0:
            adverse = l[t] if pos > 0 else h[t]
            mae = min(mae, pos * (adverse - entry))
            # hard daily equity stop (realised + open, incl. costs)
            if cfg.risk_engine:
                worst = day_pnl + realized_trade + pos * (adverse - entry) * pv * qty_open - spec.rt_cost * qty_open
                if worst <= -cfg.daily_max_loss:
                    px_lim = entry + pos * ((-cfg.daily_max_loss - day_pnl - realized_trade + spec.rt_cost * qty_open) / (pv * qty_open))
                    hit_stop = (pos > 0 and l[t] <= stop) or (pos < 0 and h[t] >= stop)
                    if not (hit_stop and pos * (stop - px_lim) >= 0):
                        fill = o[t] if pos * (o[t] - px_lim) <= 0 else px_lim
                        close_trade(fill - pos * slip, 'daily_max_loss', t); halted = True
                        continue
            if pos > 0 and l[t] <= stop:
                close_trade(min(o[t], stop) - slip, 'stop', t)
            elif pos < 0 and h[t] >= stop:
                close_trade(max(o[t], stop) + slip, 'stop', t)
            elif not np.isnan(target) and ((pos > 0 and h[t] >= target + tick) or (pos < 0 and l[t] <= target - tick)):
                if cfg.exit == 'partial' and not part_done and qty_open >= 2:
                    half = qty_open // 2
                    realized_trade += pos * (target - entry) * pv * half
                    qty_open -= half; part_done = True; target = np.nan
                    stop = entry if pos > 0 else entry  # breakeven on remainder
                    stop = max(stop, entry) if pos > 0 else min(stop, entry)
                else:
                    close_trade(target, 'target', t)
        # ---- end-of-bar management
        if pos != 0:
            if cfg.flat_min is not None and (cmin[t] >= cfg.flat_min or (t + 1 < n and tday[t + 1] != tday[t])):
                close_trade(c[t] - pos * slip, 'session_flat', t)
            elif cfg.max_hold and t - ebar + 1 >= cfg.max_hold:
                pend_exit = 'time'
            else:
                # trail for next bar
                if cfg.exit in ('tl', 'be', 'partial'):
                    if pos > 0 and L.s_ok[t]:
                        v = L.s_val(t, t + 1) - tick
                        if v < c[t]:
                            stop = max(stop, v)
                    if pos < 0 and L.r_ok[t]:
                        v = L.r_val(t, t + 1) + tick
                        if v > c[t]:
                            stop = min(stop, v)
                    if cfg.exit == 'be' and pos * (c[t] - entry) >= risk_pts:
                        stop = max(stop, entry) if pos > 0 else min(stop, entry)
                elif cfg.exit == 'atr':
                    v = c[t] - pos * cfg.trail_atr * atr[t]
                    stop = max(stop, v) if pos > 0 else min(stop, v)
        # ---- signals at close of bar t
        sig = 0; st = np.nan
        s_prev_ok = L.s_ok[t - 1]; r_prev_ok = L.r_ok[t - 1]
        if 'A' in cfg.strat:
            if L.r_break[t]:
                sig = 1
            elif L.s_break[t]:
                sig = -1
        if sig == 0 and ('B' in cfg.strat or 'D' in cfg.strat):
            mg = 2 if 'D' in cfg.strat and 'B' not in cfg.strat else 1
            if s_prev_ok and L.s_touch[t - 1] >= cfg.min_touch and L.s_gen[t - 1] >= mg:
                v = L.s_val(t - 1, t)
                if l[t] <= v + cfg.tol * atr[t] and c[t] > v and c[t] > o[t]:
                    sig = 1; st = min(l[t], L.s_val(t - 1, t + 1)) - 0.1 * atr[t]
            if sig == 0 and r_prev_ok and L.r_touch[t - 1] >= cfg.min_touch and L.r_gen[t - 1] >= mg:
                v = L.r_val(t - 1, t)
                if h[t] >= v - cfg.tol * atr[t] and c[t] < v and c[t] < o[t]:
                    sig = -1; st = max(h[t], L.r_val(t - 1, t + 1)) + 0.1 * atr[t]
        if 'C' in cfg.strat:
            if L.r_break[t]:
                retest_long = (L.rb_idx[t], L.rb_px[t], L.rb_slope[t], t); retest_short = None
            if L.s_break[t]:
                retest_short = (L.sb_idx[t], L.sb_px[t], L.sb_slope[t], t); retest_long = None
            if sig == 0 and retest_long is not None and t > retest_long[3]:
                ai, ap, sl, bt = retest_long
                v = ap + sl * (t - ai)
                if t - bt > cfg.retest_win or c[t] < v - 0.5 * atr[t]:
                    retest_long = None
                elif l[t] <= v + cfg.tol * atr[t] and c[t] > v and c[t] > o[t]:
                    sig = 1; st = min(l[t], v) - 0.1 * atr[t]; retest_long = None
            if sig == 0 and retest_short is not None and t > retest_short[3]:
                ai, ap, sl, bt = retest_short
                v = ap + sl * (t - ai)
                if t - bt > cfg.retest_win or c[t] > v + 0.5 * atr[t]:
                    retest_short = None
                elif h[t] >= v - cfg.tol * atr[t] and c[t] < v and c[t] < o[t]:
                    sig = -1; st = max(h[t], v) + 0.1 * atr[t]; retest_short = None
        if cfg.strat == 'R':
            if rng.random() < cfg.rand_p:
                sig = 1 if rng.random() < 0.5 else -1
        if sig == 0:
            continue
        if (cfg.long_only and sig < 0) or (cfg.short_only and sig > 0):
            continue
        if htf is not None and any(hd[t] != sig for hd in htf):
            continue
        if not in_sess(t):
            continue
        if cfg.flat_min is not None and t + 1 < n and tday[t + 1] != tday[t]:
            continue
        if pos == sig:
            continue
        if pos != 0 and not cfg.reverse:
            continue
        # stop for breakout / random entries
        if np.isnan(st):
            if cfg.stop_mode == 'tl' or cfg.strat == 'R' and cfg.stop_mode == 'tl':
                if sig > 0:
                    st = L.s_val(t, t + 1) - tick if L.s_ok[t] and L.s_val(t, t + 1) < c[t] else L.last_pl[t] - tick
                else:
                    st = L.r_val(t, t + 1) + tick if L.r_ok[t] and L.r_val(t, t + 1) > c[t] else L.last_ph[t] + tick
            elif cfg.stop_mode == 'pivot':
                st = (L.last_pl[t] - tick) if sig > 0 else (L.last_ph[t] + tick)
            else:
                st = c[t] - sig * cfg.stop_atr * atr[t]
        if np.isnan(st):
            continue
        st = round(st / tick) * tick
        dist = sig * (c[t] - st)
        if dist < cfg.min_stop_ticks * tick or dist > cfg.max_stop_atr * atr[t]:
            continue
        # sizing + risk engine gate
        if cfg.fixed_qty:
            q = cfg.fixed_qty
        else:
            per = dist * pv + spec.rt_cost + 2 * slip * pv
            q = min(int(cfg.risk // per), spec.max_qty)
            if q < 1:
                continue
        if cfg.risk_engine:
            if halted or day_trades >= cfg.max_trades or consec >= cfg.max_consec or t < cool_until:
                continue
            trade_risk = q * (dist * pv + spec.rt_cost + 2 * slip * pv)
            if day_pnl - trade_risk < -cfg.daily_shutdown:
                continue
            if cfg.profit_lock and day_pnl >= cfg.profit_lock:
                continue
        pend = (sig, st, q)

    cols = ['entry_ts', 'exit_ts', 'dir', 'qty', 'entry', 'exit', 'pnl', 'R', 'bars', 'reason', 'tday', 'entry_min', 'mae_pts']
    return pd.DataFrame(trades, columns=cols)
