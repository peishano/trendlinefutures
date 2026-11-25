"""Stage 4 deep-dive on the leading configuration (Config 1: 4H trendline direction -> 1H trendline execution).

1. Parameter sensitivity (k, tol, disp, exit, session, stop cap) on all four micros.
2. Walk-forward (12m in-sample -> 6m out-of-sample, rolling) on MNQ.
3. Random-entry benchmark (same session, same exits, same stops, with and without the 4H filter).
4. Long/short, yearly, session-bucket breakdown.
"""
import itertools, os, sys, dataclasses
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from tl.data import load, SPECS, atr
from tl.trendlines import build
from tl.engine import Cfg, run, htf_direction, align_htf
from tl.metrics import summarize, monthly
OUT = os.path.join(os.path.dirname(__file__), '..', 'reports')
MICRO = {'NQ': 'MNQ', 'ES': 'MES', 'YM': 'MYM', 'RTY': 'M2K'}
pd.set_option('display.width', 250)

cache = {}
def prep(sym, k, tol=0.25, disp=0.0):
    key = (sym, k, tol, disp)
    if key not in cache:
        df = load(sym, '1h'); a = atr(df)
        L = build(df.high.values, df.low.values, df.close.values, a, k=k, tol=tol, disp=disp)
        h = load(sym, '4h'); ha = atr(h)
        hL = build(h.high.values, h.low.values, h.close.values, ha, k=k, tol=tol, disp=disp)
        cache[key] = (df, a, L, align_htf(df, htf_direction(h, hL)))
    return cache[key]

EX = {'tl': dict(exit='tl'), 'be': dict(exit='be'), 'atr': dict(exit='atr'), 'fixed2R': dict(exit='fixed', target_r=2.0),
      'fixed3R': dict(exit='fixed', target_r=3.0), 'partial': dict(exit='partial')}

# ---------------------------------------------------------------- 1. sensitivity
rows = []
for sym in ('NQ', 'ES', 'YM', 'RTY'):
    for k, tol, disp, strat, ex, filt in itertools.product((1, 2, 3), (0.15, 0.25, 0.4), (0.0, 0.1, 0.25), ('A', 'B', 'C', 'ABC'),
                                                          ('tl', 'be', 'fixed2R'), (True, False)):
        df, a, L, hd = prep(sym, k, tol, disp)
        nd = df[df.open_min.between(570, 960)].tday.nunique()
        tr = run(df, SPECS[MICRO[sym]], Cfg(strat=strat, k=k, tol=tol, disp=disp, risk_engine=False, **EX[ex]), L, a,
                 htf=[hd] if filt else None)
        rows.append(summarize(tr, nd, 60, dict(sym=MICRO[sym], k=k, tol=tol, disp=disp, strat=strat, exit=ex, htf=filt)))
    print('sens', sym, flush=True)
S = pd.DataFrame(rows); S.to_csv(os.path.join(OUT, 'cand_sensitivity.csv'), index=False)
print(S.groupby(['sym', 'htf']).agg(expR=('exp_R', 'mean'), median_expR=('exp_R', 'median'),
                                    pf_gt1=('pf', lambda x: (x > 1).mean()), trades=('trades', 'mean')).round(3))
print(S[S.sym == 'MNQ'].groupby(['htf', 'strat']).agg(expR=('exp_R', 'mean'), pf_gt1=('pf', lambda x: (x > 1).mean()), trades=('trades', 'mean')).round(3))
print(S[(S.sym == 'MNQ') & S.htf].groupby('k').agg(expR=('exp_R', 'mean'), pf_gt1=('pf', lambda x: (x > 1).mean())).round(3))
print(S[(S.sym == 'MNQ') & S.htf].groupby('tol').agg(expR=('exp_R', 'mean'), pf_gt1=('pf', lambda x: (x > 1).mean())).round(3))
print(S[(S.sym == 'MNQ') & S.htf].groupby('disp').agg(expR=('exp_R', 'mean'), pf_gt1=('pf', lambda x: (x > 1).mean())).round(3))
print(S[(S.sym == 'MNQ') & S.htf].groupby('exit').agg(expR=('exp_R', 'mean'), pf_gt1=('pf', lambda x: (x > 1).mean())).round(3))

# ---------------------------------------------------------------- 2. walk-forward (MNQ)
grid = list(itertools.product((1, 2), ('A', 'B', 'C', 'ABC'), ('tl', 'be', 'fixed2R'), (True, False)))
df0 = load('NQ', '1h')
months = pd.period_range(pd.Timestamp(df0.tday.iloc[0]).to_period('M'), pd.Timestamp(df0.tday.iloc[-1]).to_period('M'), freq='M')
res = {}
for k, strat, ex, filt in grid:
    df, a, L, hd = prep('NQ', k)
    res[(k, strat, ex, filt)] = run(df, SPECS['MNQ'], Cfg(strat=strat, k=k, risk_engine=False, **EX[ex]), L, a, htf=[hd] if filt else None)
wf, oos_trades = [], []
start = 0
while True:
    is_m = months[start:start + 12]; oos_m = months[start + 12:start + 18]
    if len(oos_m) == 0:
        break
    best, bscore = None, -9
    for key, tr in res.items():
        m = pd.to_datetime(tr.tday).dt.to_period('M')
        t_is = tr[m.isin(is_m)]
        if len(t_is) < 15:
            continue
        score = t_is.R.mean()
        if score > bscore:
            best, bscore = key, score
    tr = res[best]; m = pd.to_datetime(tr.tday).dt.to_period('M'); t_oos = tr[m.isin(oos_m)]
    oos_trades.append(t_oos)
    wf.append(dict(is_from=str(is_m[0]), is_to=str(is_m[-1]), oos_from=str(oos_m[0]), oos_to=str(oos_m[-1]), chosen=str(best),
                   is_expR=bscore, oos_trades=len(t_oos), oos_expR=t_oos.R.mean(), oos_net=t_oos.pnl.sum()))
    start += 6
WF = pd.DataFrame(wf); WF.to_csv(os.path.join(OUT, 'cand_walkforward.csv'), index=False)
O = pd.concat(oos_trades)
print(WF.round(3).to_string())
print('WF OOS total: trades', len(O), 'expR', round(O.R.mean(), 3), 'net', round(O.pnl.sum(), 1),
      'PF', round(O.pnl[O.pnl > 0].sum() / -O.pnl[O.pnl < 0].sum(), 2))

# ---------------------------------------------------------------- 3. fixed candidate + random benchmark
CAND = dict(sym='NQ', k=1, strat='ABC', ex='tl')
df, a, L, hd = prep('NQ', 1)
nd = df[df.open_min.between(570, 960)].tday.nunique()
cfg = Cfg(strat='ABC', k=1, risk_engine=False, **EX['tl'])
tr = run(df, SPECS['MNQ'], cfg, L, a, htf=[hd])
tr.to_csv(os.path.join(OUT, 'cand_trades_raw.csv'), index=False)
print('CANDIDATE', summarize(tr, nd, 60))
n_sess = ((df.close_min >= 570) & (df.close_min <= 930)).sum()
out = []
for filt in (False, True):
    for s in range(300):
        p = (len(tr) / n_sess) * (2.0 if filt else 1.0)
        r = run(df, SPECS['MNQ'], Cfg(strat='R', k=1, risk_engine=False, rand_p=p, seed=1000 + s, **EX['tl']), L, a,
                htf=[hd] if filt else None)
        out.append(dict(htf=filt, seed=s, trades=len(r), expR=r.R.mean(), net=r.pnl.sum()))
RB = pd.DataFrame(out); RB.to_csv(os.path.join(OUT, 'cand_random.csv'), index=False)
for filt, g in RB.groupby('htf'):
    print(f'random (htf={filt}): trades~{g.trades.mean():.0f} expR mean {g.expR.mean():.3f} p95 {g.expR.quantile(.95):.3f}; '
          f'strategy expR {tr.R.mean():.3f} beats {100*(g.expR < tr.R.mean()).mean():.1f}% of random runs')

# ---------------------------------------------------------------- 4. breakdowns
tr['year'] = pd.to_datetime(tr.tday).dt.year
tr['bucket'] = pd.cut(tr.entry_min, [0, 600, 690, 780, 870, 960, 1440],
                      labels=['09:30-10:00 open', '10:00-11:30 morning', '11:30-13:00 lunch', '13:00-14:30 afternoon', '14:30-16:00 last', 'other'],
                      right=False)
print(tr.groupby('dir').agg(n=('R', 'size'), expR=('R', 'mean'), net=('pnl', 'sum')).round(3))
print(tr.groupby('year').agg(n=('R', 'size'), expR=('R', 'mean'), net=('pnl', 'sum')).round(3))
print(tr.groupby('bucket', observed=True).agg(n=('R', 'size'), expR=('R', 'mean'), net=('pnl', 'sum'), win=('pnl', lambda x: (x > 0).mean())).round(3))
print(tr.groupby('reason').agg(n=('R', 'size'), expR=('R', 'mean')).round(3))
tr.groupby(['year']).agg(n=('R', 'size'), expR=('R', 'mean'), net=('pnl', 'sum')).to_csv(os.path.join(OUT, 'cand_yearly.csv'))
