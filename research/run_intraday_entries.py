"""Step 1 of NEXT_STEPS: new intraday entries on 5-minute MNQ, 2023-01 -> 2026-11 (Tradovate + TradingView data).

Development (in-sample) = 2023-2025. 2026 is a sealed out-of-sample year, reported separately.
All signals use only completed bars (evaluated on the bar close, filled next bar open).

Entries
  ORB15 / ORB30 : first 5m close beyond the 09:30 opening range (15 or 30 min), up to 11:30 ET, once per side per day;
                  stop = opposite side of the range (skipped if wider than max_stop_atr * ATR)
  VWAP          : pullback to session VWAP in the trend direction: price above VWAP on the previous bar, this bar's low
                  tags VWAP (+0.1 ATR), closes back above VWAP as an up-bar; 10:00-15:00; stop = bar low/VWAP - 0.2 ATR
  EMA20         : same pullback logic on the 5m EMA(20), EMA rising/falling
  TL5           : 5m trendline breakout (built-in strategy A, 3-candle pivots) restricted to 09:45-11:30 and 13:30-15:30
Higher-timeframe direction: none | 4H trendline | daily trendline (previous completed bar only)
Exits: fixed 1.5R, fixed 2R, ATR(2x) trail, (TL5 also trendline trail); always flat by 15:55 ET
Risk engine on: $100 risk, max 4 trades/day, 3 consecutive losses, $550 shutdown, $700 hard stop.
"""
import itertools, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from tl.data import load, SPECS, atr as calc_atr, RAW
from tl.trendlines import build
from tl.engine import Cfg, run, htf_direction
from tl.metrics import summarize

OUT = os.path.join(os.path.dirname(__file__), '..', 'reports'); pd.set_option('display.width', 250)
SP = SPECS['MNQ']
df = load('MNQ', '5m', os.path.join(RAW, 'MNQ_5m_long.csv'))
A = calc_atr(df)
o, h, l, c, v = (df[x].values for x in ('open', 'high', 'low', 'close', 'volume'))
om, cm, td = df.open_min.values, df.close_min.values, df.tday.values
n = len(df)
year = pd.to_datetime(df.tday).dt.year.values


def align(dir_series):
    hd = dir_series.reset_index(); hd.columns = ['close_ts', 'dir']
    return pd.merge_asof(df[['close_ts']], hd.sort_values('close_ts'), on='close_ts', direction='backward',
                         allow_exact_matches=False).dir.fillna(0).values


h4 = load('NQ', '4h')
F4 = align(htf_direction(h4, build(h4.high.values, h4.low.values, h4.close.values, calc_atr(h4), k=1)))
g = h4.groupby('tday')
dly = pd.DataFrame({'open': g.open.first(), 'high': g.high.max(), 'low': g.low.min(), 'close': g.close.last(),
                    'close_ts': g.close_ts.last()}).reset_index()
FD = align(htf_direction(dly, build(dly.high.values, dly.low.values, dly.close.values, calc_atr(dly), k=1)))
FILTERS = {'none': None, '4H': [F4], 'daily': [FD]}


def orb(minutes, last_entry=690, max_stop_atr=3.0, stop='range'):
    sig = np.zeros(n, int); stp = np.full(n, np.nan)
    hi = lo = None; day = None; done_l = done_s = False
    for t in range(n):
        if td[t] != day:
            day = td[t]; hi = lo = None; done_l = done_s = False
        if 570 <= om[t] < 570 + minutes:
            hi = h[t] if hi is None else max(hi, h[t]); lo = l[t] if lo is None else min(lo, l[t]); continue
        if hi is None or cm[t] < 570 + minutes or cm[t] > last_entry:
            continue
        if not done_l and c[t] > hi:
            done_l = True
            sl = {'range': lo, 'mid': (hi + lo) / 2, 'atr1': c[t] - A[t]}[stop]
            if c[t] - sl <= max_stop_atr * A[t]:
                sig[t], stp[t] = 1, sl - SP.tick
        elif not done_s and c[t] < lo:
            done_s = True
            sl = {'range': hi, 'mid': (hi + lo) / 2, 'atr1': c[t] + A[t]}[stop]
            if sl - c[t] <= max_stop_atr * A[t]:
                sig[t], stp[t] = -1, sl + SP.tick
    return sig, stp


def pullback(line):
    sig = np.zeros(n, int); stp = np.full(n, np.nan)
    for t in range(1, n):
        if not (600 <= cm[t] <= 900) or td[t] != td[t - 1] or np.isnan(line[t]):
            continue
        L, a = line[t], A[t]
        if c[t - 1] > line[t - 1] and l[t] <= L + 0.1 * a and c[t] > L and c[t] > o[t]:
            sig[t], stp[t] = 1, min(l[t], L) - 0.2 * a
        elif c[t - 1] < line[t - 1] and h[t] >= L - 0.1 * a and c[t] < L and c[t] < o[t]:
            sig[t], stp[t] = -1, max(h[t], L) + 0.2 * a
    return sig, stp


def session_vwap():
    out = np.full(n, np.nan); pv = vv = 0.0; day = None
    tp = (h + l + c) / 3
    for t in range(n):
        if td[t] != day:
            day = td[t]; pv = vv = 0.0
        if om[t] >= 570 and cm[t] <= 960:
            pv += tp[t] * max(v[t], 1); vv += max(v[t], 1); out[t] = pv / vv
    return out


ema = pd.Series(c).ewm(span=20, adjust=False).mean().values
ema_slope_ok = np.r_[0, np.sign(np.diff(ema))]
vw = session_vwap()
s_vw, st_vw = pullback(vw)
s_em, st_em = pullback(ema)
s_em[(s_em != 0) & (s_em != ema_slope_ok)] = 0
SIGNALS = {'ORB15': orb(15), 'ORB30': orb(30), 'ORB15mid': orb(15, stop='mid'), 'ORB30mid': orb(30, stop='mid'),
           'ORB15atr': orb(15, stop='atr1'), 'ORB30atr': orb(30, stop='atr1'), 'VWAP': (s_vw, st_vw), 'EMA20': (s_em, st_em)}
EXITS = {'fixed1.5R': dict(exit='fixed', target_r=1.5), 'fixed2R': dict(exit='fixed', target_r=2.0), 'atr_trail': dict(exit='atr', trail_atr=2.0)}
L5 = build(h, l, c, A, k=1)
days_is = sorted(set(td[(year <= 2025) & (om >= 570) & (om < 960)])); days_oos = sorted(set(td[(year == 2026) & (om >= 570) & (om < 960)]))


def evaluate(tr, label):
    yrs = pd.to_datetime(tr.tday).dt.year if len(tr) else pd.Series(dtype=int)
    ti, to = tr[yrs <= 2025], tr[yrs == 2026]
    s = summarize(ti, len(days_is), 5, label)
    s['weekly_is'] = ti.pnl.sum() / (len(days_is) / 5) if len(ti) else 0
    s['oos_trades'] = len(to); s['oos_expR'] = to.R.mean() if len(to) else np.nan
    s['oos_net'] = to.pnl.sum(); s['weekly_oos'] = to.pnl.sum() / (len(days_oos) / 5)
    s['oos_pf'] = to.pnl[to.pnl > 0].sum() / -to.pnl[to.pnl < 0].sum() if (to.pnl < 0).any() else np.inf
    for y in (2023, 2024, 2025, 2026):
        s[f'net_{y}'] = tr[yrs == y].pnl.sum()
    return s


rows = []
base = dict(k=1, risk=100, max_trades=4, max_consec=3, sess=(570, 915))
for (name, (sg, st)), (fname, filt), (ename, ex) in itertools.product(SIGNALS.items(), FILTERS.items(), EXITS.items()):
    tr = run(df, SP, Cfg(strat='X', max_stop_atr=3.0, **base, **ex), L5, A, htf=filt, ext_sig=sg, ext_stop=st)
    rows.append(evaluate(tr, dict(entry=name, htf=fname, exit=ename)))
for (fname, filt), (ename, ex) in itertools.product(FILTERS.items(), {**EXITS, 'tl_trail': dict(exit='tl')}.items()):
    parts = [run(df, SP, Cfg(strat='A', **{**base, 'sess': w}, **ex), L5, A, htf=filt) for w in ((585, 690), (810, 930))]
    tr = pd.concat(parts).sort_values('entry_ts')
    rows.append(evaluate(tr, dict(entry='TL5', htf=fname, exit=ename)))
    print('TL5', fname, ename, flush=True)
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, 'intraday_entries.csv'), index=False)
cols = ['entry', 'htf', 'exit', 'trades', 'trades_day', 'win_rate', 'pf', 'exp_R', 'weekly_is', 'max_dd', 'net_2023', 'net_2024',
        'net_2025', 'oos_trades', 'oos_expR', 'oos_pf', 'weekly_oos']
print(R[cols].sort_values('exp_R', ascending=False).round(2).to_string())
