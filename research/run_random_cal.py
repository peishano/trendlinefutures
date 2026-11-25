"""Random-entry benchmark with trade-count calibration (random entries pass the same session, stop-distance,
sizing and HTF gates and use the identical trendline-trailing exit)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from tl.data import load, SPECS, atr
from tl.trendlines import build
from tl.engine import Cfg, run, htf_direction, align_htf
OUT = os.path.join(os.path.dirname(__file__), '..', 'reports')
df = load('NQ', '1h'); a = atr(df); L = build(df.high.values, df.low.values, df.close.values, a, k=1)
h = load('NQ', '4h'); hL = build(h.high.values, h.low.values, h.close.values, atr(h), k=1); hd = align_htf(df, htf_direction(h, hL))
tr = run(df, SPECS['MNQ'], Cfg(strat='ABC', k=1, risk_engine=False), L, a, htf=[hd])
N = len(tr); print('strategy trades', N, 'expR', round(tr.R.mean(), 3), 'net', round(tr.pnl.sum()))
rows = []
for filt in (False, True):
    p = 0.02
    for _ in range(12):   # calibrate per-bar probability to match trade count
        cnt = np.mean([len(run(df, SPECS['MNQ'], Cfg(strat='R', k=1, risk_engine=False, rand_p=p, seed=s), L, a, htf=[hd] if filt else None)) for s in range(5)])
        p *= N / max(cnt, 1)
    for s in range(500):
        r = run(df, SPECS['MNQ'], Cfg(strat='R', k=1, risk_engine=False, rand_p=p, seed=5000 + s), L, a, htf=[hd] if filt else None)
        rows.append(dict(htf=filt, trades=len(r), expR=r.R.mean(), net=r.pnl.sum(), pf=r.pnl[r.pnl > 0].sum() / max(-r.pnl[r.pnl < 0].sum(), 1e-9)))
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, 'cand_random_calibrated.csv'), index=False)
for filt, g in R.groupby('htf'):
    print(f'random htf={filt}: trades {g.trades.mean():.0f}  expR mean {g.expR.mean():.3f}  p50 {g.expR.median():.3f}  p95 {g.expR.quantile(.95):.3f}  '
          f'net mean {g.net.mean():.0f}  -> strategy beats {100*(g.expR < tr.R.mean()).mean():.1f}% (R), {100*(g.net < tr.pnl.sum()).mean():.1f}% (net $)')
