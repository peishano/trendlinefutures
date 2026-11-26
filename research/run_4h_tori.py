"""4H backtest 'like Tori trades': 4H execution, overnight/weekend holding allowed, breakout (her favourite)
and bounce entries, stop beyond the opposite/own trendline, trailed along the line, no fixed target,
risk 1% of a $50k account per trade ($500) sized in micros. Optional top-down filter: daily trendline
direction (daily bars built from the 4H bars, previous completed day only)."""
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
    d = pd.DataFrame({'open': g.open.first(), 'high': g.high.max(), 'low': g.low.min(), 'close': g.close.last(),
                      'close_ts': g.close_ts.last()}).reset_index()
    return d

rows, yearly, weekly = [], [], []
for sym in ('NQ', 'ES', 'YM', 'RTY'):
    df = load(sym, '4h'); a = atr(df)
    d = daily_from(df); da = atr(d)
    ndays = df.tday.nunique()
    for k in (1, 2):
        L = build(df.high.values, df.low.values, df.close.values, a, k=k)
        dL = build(d.high.values, d.low.values, d.close.values, da, k=k)
        ddir = align_htf(df, htf_direction(d.assign(close_ts=d.close_ts), dL))
        for strat in ('A', 'AB'):
            for filt in (False, True):
                cfg = Cfg(strat=strat, k=k, sess=None, flat_min=None, risk_engine=False, risk=500,
                          max_stop_atr=1e9, min_stop_ticks=4)
                tr = run(df, SPECS[MICRO[sym]], cfg, L, a, htf=[ddir] if filt else None)
                # random entries, same exits/stops/sizing, same trade count (approx)
                p = len(tr) / len(df)
                rnd = np.array([run(df, SPECS[MICRO[sym]], Cfg(strat='R', k=k, sess=None, flat_min=None, risk_engine=False,
                                risk=500, max_stop_atr=1e9, min_stop_ticks=4, rand_p=p * 1.15, seed=s), L, a,
                                htf=[ddir] if filt else None).pnl.sum() for s in range(60)])
                s = summarize(tr, ndays, 240, dict(sym=MICRO[sym], k=k, setups=strat, daily_filter=filt))
                s['weekly_avg'] = tr.pnl.sum() / (ndays / 5)
                s['random_mean'] = rnd.mean(); s['pct_random_beaten'] = (rnd < tr.pnl.sum()).mean()
                s['avg_hold_days'] = tr.bars.mean() * 4 / 23
                rows.append(s)
                if k == 1 and strat == 'A' and not filt:
                    for y, v in tr.groupby(pd.to_datetime(tr.exit_ts).dt.year).pnl.sum().items():
                        yearly.append(dict(sym=MICRO[sym], year=y, pnl=v))
    print(sym, flush=True)
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, 'tori_4h.csv'), index=False)
Y = pd.DataFrame(yearly).pivot(index='year', columns='sym', values='pnl'); Y.to_csv(os.path.join(OUT, 'tori_4h_yearly.csv'))
c = ['sym', 'k', 'setups', 'daily_filter', 'trades', 'win_rate', 'pf', 'net', 'weekly_avg', 'max_dd', 'exp_R', 'avg_hold_days',
     'max_losing_streak', 'worst_day', 'random_mean', 'pct_random_beaten']
print(R[c].round(2).to_string())
print(Y.round(0).to_string())
