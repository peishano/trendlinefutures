"""Stage 4: risk engine, daily objectives, profit locks and prop-firm survival for the candidate.

Prop model (THIRD-PARTY-SOURCED, unverified with IQ Capital): $2,000 end-of-day trailing max drawdown
(trailing stops at starting balance), $1,000 daily loss limit. Evaluation profit target ASSUMED $3,000.
Survival = probability of reaching +$3,000 before the EOD trailing floor is breached (block bootstrap of daily P&L).
"""
import itertools, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from tl.data import load, SPECS, atr
from tl.trendlines import build
from tl.engine import Cfg, run, htf_direction, align_htf
from tl.metrics import summarize
OUT = os.path.join(os.path.dirname(__file__), '..', 'reports')
pd.set_option('display.width', 250)

def prep(sym, tf, htf, k=1):
    df = load(sym, tf); a = atr(df); L = build(df.high.values, df.low.values, df.close.values, a, k=k)
    h = load(sym, htf); hL = build(h.high.values, h.low.values, h.close.values, atr(h), k=k)
    return df, a, L, align_htf(df, htf_direction(h, hL))

def prop_survival(daily, target=3000., trail=2000., dll=1000., sims=4000, horizon=500, block=5, seed=1):
    rng = np.random.default_rng(seed); d = daily.values; n = len(d)
    passed = failed = 0; days = []
    for _ in range(sims):
        bal = hwm = 0.0
        for i in range(horizon // block):
            st = rng.integers(0, n - block)
            done = False
            for v in d[st:st + block]:
                v = max(v, -dll)
                bal += v
                hwm = min(max(hwm, bal), trail)  # EOD trailing floor stops at starting balance
                if bal >= target: passed += 1; days.append(i * block); done = True; break
                if bal <= hwm - trail: failed += 1; done = True; break
            if done: break
    return passed / sims, failed / sims, (np.median(days) if days else np.nan)

rows = []
for (sym, tf, htf, strat) in [('NQ', '1h', '4h', 'ABC'), ('NQ', '1h', '4h', 'A'), ('NQ', '5m', '1h', 'A'), ('NQ', '15m', '1h', 'A')]:
    df, a, L, hd = prep(sym, tf, htf)
    days = sorted(df[df.open_min.between(570, 960)].tday.unique())
    for risk, lock in itertools.product((50, 100, 150, 250, 350), (0, 250, 500, 1000)):
        cfg = Cfg(strat=strat, k=1, risk=risk, profit_lock=lock, risk_engine=True, daily_shutdown=550, daily_max_loss=700,
                  max_trades=4, max_consec=3)
        tr = run(df, SPECS['MNQ'], cfg, L, a, htf=[hd])
        s = summarize(tr, len(days), 0, dict(sym='MNQ', tf=tf, htf=htf, strat=strat, risk=risk, lock=lock))
        d = tr.groupby('tday').pnl.sum().reindex(days, fill_value=0.0)
        p, f, md = prop_survival(d)
        s.update(prop_pass=p, prop_fail=f, prop_median_days=md, avg_month=d.sum() / (len(days) / 21))
        rows.append(s)
    print(sym, tf, strat, flush=True)
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, 'risk_engine.csv'), index=False)
c = ['tf', 'strat', 'risk', 'lock', 'trades', 'net', 'avg_month', 'pf', 'max_dd', 'worst_day', 'days_le_550', 'd250', 'd500', 'd1000', 'prop_pass', 'prop_fail', 'prop_median_days']
print(R[c].round(3).to_string())
