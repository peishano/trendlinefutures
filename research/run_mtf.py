"""Stage 3: multi-timeframe configurations 1-6 (Strategy E = LTF setup filtered by HTF trendline-break direction)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from tl.data import load, SPECS, atr, TF_MIN
from tl.trendlines import build
from tl.engine import Cfg, run, htf_direction, align_htf
from tl.metrics import summarize
OUT = os.path.join(os.path.dirname(__file__), '..', 'reports')
MICRO = {'NQ': 'MNQ', 'ES': 'MES', 'YM': 'MYM', 'RTY': 'M2K'}
CONFIGS = {1: ('1h', ['4h']), 2: ('15m', ['1h']), 3: ('5m', ['1h', '15m']), 4: ('5m', ['15m']), 5: ('1m', ['15m', '5m']), 6: ('1m', ['5m'])}
SYMS = {1: ['NQ', 'ES', 'YM', 'RTY'], 2: ['NQ', 'ES', 'YM', 'RTY'], 3: ['NQ', 'ES'], 4: ['NQ', 'ES'], 5: ['NQ', 'ES'], 6: ['NQ', 'ES']}
rows = []
cache = {}
def lines(sym, tf, k):
    key = (sym, tf, k)
    if key not in cache:
        df = load(sym, tf); a = atr(df)
        cache[key] = (df, a, build(df.high.values, df.low.values, df.close.values, a, k=k))
    return cache[key]
for cid, (ltf, htfs) in CONFIGS.items():
    for sym in SYMS[cid]:
        for k in (1, 2):
            df, a, L = lines(sym, ltf, k)
            nd = df[df.open_min.between(570, 960)].tday.nunique()
            filt = []
            for h in htfs:
                hdf, ha, hL = lines(sym, h, k)
                filt.append(align_htf(df, htf_direction(hdf, hL)))
            for strat in 'ABC':
                for use in (False, True):
                    cfg = Cfg(strat=strat, k=k, risk_engine=False)
                    tr = run(df, SPECS[MICRO[sym]], cfg, L, a, htf=filt if use else None)
                    rows.append(summarize(tr, nd, TF_MIN[ltf], dict(config=cid, exec=ltf, htf='+'.join(htfs) if use else 'none',
                                                                     sym=MICRO[sym], k=k, strat=strat)))
    print('config', cid, flush=True)
r = pd.DataFrame(rows); r.to_csv(os.path.join(OUT, 'mtf.csv'), index=False)
pd.set_option('display.width', 250)
p = r.pivot_table(index=['config', 'exec', 'sym', 'k', 'strat'], columns=r.htf.eq('none').map({True: 'no_filter', False: 'htf_filter'}),
                  values=['exp_R', 'trades', 'pf'])
print(p.round(3).to_string())
print(r.groupby(['config', r.htf.eq('none')]).agg(expR=('exp_R', 'mean'), pf_gt1=('pf', lambda x: (x > 1).mean()), trades=('trades', 'sum')).round(3))
