"""Stage 4/5: consolidated timeframe comparison (same rules everywhere) + final candidate with full risk engine,
cost sensitivity, monthly table. Writes reports/timeframe_comparison.csv, reports/final_*.csv"""
import os, sys, dataclasses
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from tl.data import load, SPECS, atr, TF_MIN
from tl.trendlines import build
from tl.engine import Cfg, run, htf_direction, align_htf
from tl.metrics import summarize, monthly
OUT = os.path.join(os.path.dirname(__file__), '..', 'reports'); pd.set_option('display.width', 250)
MICRO = {'NQ': 'MNQ', 'ES': 'MES'}
cache = {}
def P(sym, tf, k=1):
    if (sym, tf, k) not in cache:
        df = load(sym, tf); a = atr(df); cache[(sym, tf, k)] = (df, a, build(df.high.values, df.low.values, df.close.values, a, k=k))
    return cache[(sym, tf, k)]
def H(sym, ltf, htfs, k=1):
    df = P(sym, ltf, k)[0]
    return [align_htf(df, htf_direction(P(sym, h, k)[0], P(sym, h, k)[2])) for h in htfs]
rows = []
SETS = [('1h', ['4h']), ('15m', ['1h']), ('5m', ['1h', '15m']), ('5m', ['15m']), ('1m', ['15m', '5m']), ('1m', ['5m'])]
for sym in ('NQ', 'ES'):
    for ltf, htfs in SETS:
        df, a, L = P(sym, ltf)
        days = sorted(df[df.open_min.between(570, 960)].tday.unique())
        for strat in ('A', 'ABC'):
            cfg = Cfg(strat=strat, k=1, risk=100, risk_engine=True, max_trades=4, max_consec=3)
            tr = run(df, SPECS[MICRO[sym]], cfg, L, a, htf=H(sym, ltf, htfs))
            gross = run(df, dataclasses.replace(SPECS[MICRO[sym]], rt_cost=0), dataclasses.replace(cfg, slip=0), L, a, htf=H(sym, ltf, htfs))
            slip2 = run(df, SPECS[MICRO[sym]], dataclasses.replace(cfg, slip=2), L, a, htf=H(sym, ltf, htfs))
            s = summarize(tr, len(days), TF_MIN[ltf], dict(sym=MICRO[sym], exec=ltf, htf='+'.join(htfs), strat=strat,
                                                           period=f'{days[0]}..{days[-1]}', days=len(days)))
            s.update(commission_usd=len(tr) and float((tr.qty * SPECS[MICRO[sym]].rt_cost).sum()),
                     gross_net=gross.pnl.sum(), net_slip2=slip2.pnl.sum(),
                     shutdown_days=int((tr.groupby('tday').pnl.sum() <= -400).sum()) if len(tr) else 0)
            rows.append(s)
T = pd.DataFrame(rows); T.to_csv(os.path.join(OUT, 'timeframe_comparison.csv'), index=False)
c = ['sym', 'exec', 'htf', 'strat', 'days', 'trades', 'trades_day', 'win_rate', 'pf', 'exp', 'exp_R', 'net', 'gross_net', 'net_slip2',
     'commission_usd', 'max_dd', 'hold_min', 'max_losing_streak', 'prof_days', 'd250', 'd500', 'd1000', 'sharpe']
print(T[c].round(3).to_string())
# final candidate details
df, a, L = P('NQ', '1h'); hd = H('NQ', '1h', ['4h'])
cfg = Cfg(strat='ABC', k=1, risk=100, risk_engine=True, max_trades=4, max_consec=3)
tr = run(df, SPECS['MNQ'], cfg, L, a, htf=hd); tr.to_csv(os.path.join(OUT, 'final_trades.csv'), index=False)
m = monthly(tr); m.to_csv(os.path.join(OUT, 'final_monthly.csv'))
print('months', len(m), 'positive', (m > 0).sum(), 'mean', round(m.mean(), 1))
print(m.groupby(m.index.year).agg(['sum', 'count', lambda x: (x > 0).sum()]))
