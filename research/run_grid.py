"""Stage 3/4 core grid: strategy x timeframe x instrument x pivot x exit (intraday mode).

Raw-edge run: risk engine OFF (so daily limits don't mask the signal), $100 risk per
trade sized on micros, costs + 1 tick slippage per side. Output: reports/grid.csv
"""
import itertools, os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from tl.data import load, SPECS, atr, TF_MIN
from tl.trendlines import build
from tl.engine import Cfg, run
from tl.metrics import summarize

OUT = os.path.join(os.path.dirname(__file__), '..', 'reports'); os.makedirs(OUT, exist_ok=True)
MICRO = {'NQ': 'MNQ', 'ES': 'MES', 'YM': 'MYM', 'RTY': 'M2K'}
DATA = {'1h': ['NQ', 'ES', 'YM', 'RTY'], '15m': ['NQ', 'ES', 'YM', 'RTY'], '5m': ['NQ', 'ES'], '1m': ['NQ', 'ES']}
EXITS = {
    'tl_trail': dict(exit='tl'),
    'fixed_2R': dict(exit='fixed', target_r=2.0),
    'fixed_1R': dict(exit='fixed', target_r=1.0),
    'atr_trail': dict(exit='atr', trail_atr=2.0),
    'tl_trail_BE': dict(exit='be'),
    'partial_1R+tl': dict(exit='partial'),
    'time_8bars': dict(exit='tl', max_hold=8),
}
rows = []
for tf, syms in DATA.items():
    for sym in syms:
        df = load(sym, tf); a = atr(df); nd = df[df.open_min.between(570, 960)].tday.nunique()
        for k in (1, 2, 3):
            L = build(df.high.values, df.low.values, df.close.values, a, k=k)
            for strat, (ename, ex) in itertools.product('ABCD', EXITS.items()):
                cfg = Cfg(strat=strat, k=k, risk_engine=False, **ex)
                tr = run(df, SPECS[MICRO[sym]], cfg, L=L, atr=a)
                rows.append(summarize(tr, nd, TF_MIN[tf], dict(tf=tf, sym=MICRO[sym], strat=strat, k=k, exit=ename,
                                                                 long_R=tr[tr.dir > 0].R.mean() if len(tr) else None,
                                                                 short_R=tr[tr.dir < 0].R.mean() if len(tr) else None,
                                                                 start=str(df.tday.iloc[0]), end=str(df.tday.iloc[-1]))))
        print(tf, sym, 'done', flush=True)
pd.DataFrame(rows).to_csv(os.path.join(OUT, 'grid.csv'), index=False)
