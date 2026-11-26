"""MNQ 1H, 4H trendline-direction filter, INTRADAY (signal-bar close 09:30-15:30 ET, flat by 15:55 ET), $100 risk,
full risk engine ($550 shutdown / $700 hard / 4 trades / 3 consecutive losses). Tori-style setups A and A+B,
plus the A+B+C hybrid. Random benchmark: same filter, exits, stops, sizing, calibrated trade count."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from tl.data import load, SPECS, atr
from tl.trendlines import build
from tl.engine import Cfg, run, htf_direction, align_htf
from tl.metrics import summarize
OUT = os.path.join(os.path.dirname(__file__), '..', 'reports'); pd.set_option('display.width', 250)
df = load('NQ', '1h'); a = atr(df); h4 = load('NQ', '4h')
days = sorted(df[df.open_min.between(570, 960)].tday.unique()); nd = len(days); weeks = nd / 5
rows, yr = [], []
for k in (1, 2):
    L = build(df.high.values, df.low.values, df.close.values, a, k=k)
    hd = htf_direction(h4, build(h4.high.values, h4.low.values, h4.close.values, atr(h4), k=k)).reset_index(); hd.columns = ['close_ts', 'dir']
    f4 = pd.merge_asof(df[['close_ts']], hd, on='close_ts', direction='backward', allow_exact_matches=False).dir.fillna(0).values  # Pine timing
    for strat in ('A', 'AB', 'ABC'):
        cfg = Cfg(strat=strat, k=k, risk=100)
        tr = run(df, SPECS['MNQ'], cfg, L, a, htf=[f4])
        p = 0.02
        for _ in range(8):
            cnt = np.mean([len(run(df, SPECS['MNQ'], Cfg(strat='R', k=k, risk=100, rand_p=p, seed=s), L, a, htf=[f4])) for s in range(4)])
            p *= len(tr) / max(cnt, 1)
        rnd = np.array([run(df, SPECS['MNQ'], Cfg(strat='R', k=k, risk=100, rand_p=p, seed=900 + s), L, a, htf=[f4]).pnl.sum() for s in range(150)])
        s = summarize(tr, nd, 60, dict(k=k, setups=strat))
        w = tr.groupby(pd.to_datetime(tr.tday).dt.to_period('W')).pnl.sum()
        s.update(weekly_avg=tr.pnl.sum() / weeks, weeks_pos=int((w > 0).sum()), weeks_neg=int((w < 0).sum()),
                 random_mean=rnd.mean(), pct_random_beaten=(rnd < tr.pnl.sum()).mean())
        rows.append(s)
        for y, g in tr.groupby(pd.to_datetime(tr.tday).dt.year):
            yr.append(dict(k=k, setups=strat, year=y, trades=len(g), pnl=g.pnl.sum()))
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, 'mnq_1h_intraday_4h.csv'), index=False)
Y = pd.DataFrame(yr); Y.to_csv(os.path.join(OUT, 'mnq_1h_intraday_4h_yearly.csv'), index=False)
print(R[['k', 'setups', 'trades', 'trades_day', 'win_rate', 'pf', 'net', 'weekly_avg', 'exp_R', 'max_dd', 'worst_day', 'best_day',
         'max_losing_streak', 'weeks_pos', 'weeks_neg', 'days_le_550', 'random_mean', 'pct_random_beaten']].round(2).to_string())
print(Y.pivot_table(index='year', columns=['k', 'setups'], values='pnl').round(0).to_string())
print('weeks in sample', round(weeks), 'days', nd)
