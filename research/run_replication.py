"""Transcript-2 replication: always-in stop-and-reverse trendline breakout, trail stop on opposite line,
no target, overnight holding allowed, 1 mini contract, costs. 4h (2019-06..2026-11) and 1h (2023..2026)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from tl.data import load, SPECS, atr
from tl.trendlines import build
from tl.engine import Cfg, run
OUT = os.path.join(os.path.dirname(__file__), '..', 'reports')
rows, yearly = [], []
for tf in ('4h', '1h'):
    for sym in ('NQ', 'ES', 'YM', 'RTY'):
        df = load(sym, tf); a = atr(df); sp = SPECS[sym]
        bh = (df.close.iloc[-1] - df.open.iloc[0]) * sp.pv
        for k in (1, 2):
            L = build(df.high.values, df.low.values, df.close.values, a, k=k)
            cfg = Cfg(strat='A', k=k, reverse=True, sess=None, flat_min=None, risk_engine=False,
                      fixed_qty=1, max_stop_atr=1e9, min_stop_ticks=1)
            tr = run(df, sp, cfg, L, a)
            # random: same number of entries at random bars, random side, same trendline exit/reverse engine
            p = len(tr) / len(df)
            rnd = np.array([run(df, sp, Cfg(strat='R', k=k, reverse=True, sess=None, flat_min=None, risk_engine=False,
                                            fixed_qty=1, max_stop_atr=1e9, min_stop_ticks=1, rand_p=p, seed=s), L, a).pnl.sum()
                            for s in range(100)])
            eq = tr.pnl.cumsum().values
            mdd = (np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max()
            # buy & hold max drawdown in $ for 1 contract
            bhc = (df.close - df.open.iloc[0]).values * sp.pv
            bh_mdd = (np.maximum.accumulate(bhc) - bhc).max()
            rows.append(dict(tf=tf, sym=sym, k=k, pivot=f'{2*k+1}-candle', trades=len(tr), net=tr.pnl.sum(),
                             win_rate=(tr.pnl > 0).mean(), pf=tr.pnl[tr.pnl > 0].sum() / -tr.pnl[tr.pnl < 0].sum(),
                             max_dd=mdd, long_net=tr[tr.dir > 0].pnl.sum(), short_net=tr[tr.dir < 0].pnl.sum(),
                             buy_hold=bh, bh_max_dd=bh_mdd, rand_mean=rnd.mean(), pct_random_beating=(rnd >= tr.pnl.sum()).mean(),
                             start=str(df.tday.iloc[0]), end=str(df.tday.iloc[-1])))
            yr = pd.to_datetime(tr.exit_ts).dt.year
            bhy = df.groupby(df.ts.dt.year).apply(lambda g: (g.close.iloc[-1] - g.open.iloc[0]) * sp.pv)
            for y, v in tr.groupby(yr).pnl.sum().items():
                yearly.append(dict(tf=tf, sym=sym, k=k, year=y, strat=v, buy_hold=bhy.get(y, np.nan)))
        print(tf, sym, flush=True)
r = pd.DataFrame(rows); r.to_csv(os.path.join(OUT, 'replication.csv'), index=False)
y = pd.DataFrame(yearly); y.to_csv(os.path.join(OUT, 'replication_yearly.csv'), index=False)
pd.set_option('display.width', 250)
print(r.drop(columns=['start', 'end']).round(2).to_string())
print(y[(y.k == 1)].pivot_table(index=['tf', 'year'], columns='sym', values=['strat', 'buy_hold']).round(0).to_string())
