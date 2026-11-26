"""1H backtest 'like Tori used to trade': 1H execution, overnight/weekend holding allowed, breakout (A) and
breakout+bounce (AB), stop beyond the opposite/own trendline, trailed, no target, 1% risk ($500) in micros.
Top-down filter options: none, 4H trendline direction, daily trendline direction (previous completed bar only).
Data: 1H 2023-01 -> 2026-11."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from tl.data import load, SPECS, atr
from tl.trendlines import build
from tl.engine import Cfg, run, htf_direction, align_htf
from tl.metrics import summarize
OUT = os.path.join(os.path.dirname(__file__), '..', 'reports'); pd.set_option('display.width', 250)
MICRO = {'NQ': 'MNQ', 'ES': 'MES', 'YM': 'MYM', 'RTY': 'M2K'}

def daily_from(df):
    g = df.groupby('tday')
    return pd.DataFrame({'open': g.open.first(), 'high': g.high.max(), 'low': g.low.min(), 'close': g.close.last(),
                         'close_ts': g.close_ts.last()}).reset_index()

rows, yearly = [], []
for sym in ('NQ', 'ES', 'YM', 'RTY'):
    df = load(sym, '1h'); a = atr(df); ndays = df.tday.nunique()
    h4 = load(sym, '4h'); d = daily_from(h4)
    for k in (1, 2):
        L = build(df.high.values, df.low.values, df.close.values, a, k=k)
        f4 = align_htf(df, htf_direction(h4, build(h4.high.values, h4.low.values, h4.close.values, atr(h4), k=k)))
        fd = align_htf(df, htf_direction(d, build(d.high.values, d.low.values, d.close.values, atr(d), k=k)))
        for strat in ('A', 'AB'):
            for fname, filt in (('none', None), ('4H', [f4]), ('daily', [fd])):
                base = dict(k=k, sess=None, flat_min=None, risk_engine=False, risk=500, max_stop_atr=1e9, min_stop_ticks=4)
                tr = run(df, SPECS[MICRO[sym]], Cfg(strat=strat, **base), L, a, htf=filt)
                p = len(tr) / len(df)
                rnd = np.array([run(df, SPECS[MICRO[sym]], Cfg(strat='R', rand_p=p * 1.15, seed=s, **base), L, a, htf=filt).pnl.sum()
                                for s in range(40)])
                s = summarize(tr, ndays, 60, dict(sym=MICRO[sym], k=k, setups=strat, filter=fname))
                s.update(weekly_avg=tr.pnl.sum() / (ndays / 5), avg_hold_h=tr.bars.mean(), random_mean=rnd.mean(),
                         pct_random_beaten=(rnd < tr.pnl.sum()).mean())
                rows.append(s)
                if k == 1 and strat == 'A' and fname == 'none':
                    for y, v in tr.groupby(pd.to_datetime(tr.exit_ts).dt.year).pnl.sum().items():
                        yearly.append(dict(sym=MICRO[sym], year=y, pnl=v))
    print(sym, flush=True)
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, 'tori_1h.csv'), index=False)
Y = pd.DataFrame(yearly).pivot(index='year', columns='sym', values='pnl'); Y.to_csv(os.path.join(OUT, 'tori_1h_yearly.csv'))
c = ['sym', 'k', 'setups', 'filter', 'trades', 'win_rate', 'pf', 'net', 'weekly_avg', 'max_dd', 'avg_hold_h', 'max_losing_streak',
     'worst_day', 'random_mean', 'pct_random_beaten']
print(R[c].round(2).to_string()); print(Y.round(0).to_string())
