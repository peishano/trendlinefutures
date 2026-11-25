"""Cost decomposition and random-entry baseline (same engine, same exits, same session, same stop logic)."""
import os, sys, dataclasses
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from tl.data import load, SPECS, atr, TF_MIN
from tl.trendlines import build
from tl.engine import Cfg, run
OUT = os.path.join(os.path.dirname(__file__), '..', 'reports')
MICRO = {'NQ': 'MNQ', 'ES': 'MES', 'YM': 'MYM', 'RTY': 'M2K'}
rows = []
for tf, sym in [('1h','NQ'),('1h','ES'),('15m','NQ'),('15m','ES'),('5m','NQ'),('5m','ES'),('1m','NQ'),('1m','ES')]:
    df = load(sym, tf); a = atr(df)
    sp = SPECS[MICRO[sym]]; sp0 = dataclasses.replace(sp, rt_cost=0.0)
    for k in (1, 2):
        L = build(df.high.values, df.low.values, df.close.values, a, k=k)
        for strat in 'ABC':
            base = Cfg(strat=strat, k=k, risk_engine=False)
            net = run(df, sp, base, L, a)
            gross = run(df, sp0, dataclasses.replace(base, slip=0), L, a)
            # random entries: same per-bar entry rate inside the session, same stop/exit engine
            n_sess = ((df.close_min >= 570) & (df.close_min <= 930)).sum()
            p = len(net) / max(n_sess, 1)
            rnd = [run(df, sp, Cfg(strat='R', k=k, risk_engine=False, rand_p=p * 1.3, seed=s), L, a) for s in range(60)]
            rR = np.array([r.R.mean() for r in rnd if len(r) > 5])
            rows.append(dict(tf=tf, sym=MICRO[sym], k=k, strat=strat, trades=len(net),
                             gross_R=gross.R.mean(), net_R=net.R.mean(), cost_R=gross.R.mean() - net.R.mean(),
                             gross_usd=gross.pnl.sum(), net_usd=net.pnl.sum(),
                             rand_R_mean=rR.mean(), rand_R_p95=np.percentile(rR, 95),
                             pctile_vs_random=(rR < net.R.mean()).mean()))
    print(tf, sym, flush=True)
r = pd.DataFrame(rows); r.to_csv(os.path.join(OUT, 'costs_random.csv'), index=False)
pd.set_option('display.width', 220); print(r.round(3).to_string())
