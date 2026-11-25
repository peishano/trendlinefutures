"""Lines at bar t must be identical whether or not bars after t exist (no repainting)."""
import sys, os, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tl.data import load, atr
from tl.trendlines import build
from tl.engine import Cfg, run
from tl.data import SPECS

def test_lines_do_not_repaint():
    df = load('NQ', '1h').iloc[:3000].reset_index(drop=True)
    a = atr(df)
    full = build(df.high.values, df.low.values, df.close.values, a, k=2)
    for T in (500, 1234, 2000, 2999):
        part = build(df.high.values[:T+1], df.low.values[:T+1], df.close.values[:T+1], a[:T+1], k=2)
        for name in ('r_ok', 'r_idx', 'r_px', 'r_slope', 's_ok', 's_idx', 's_px', 's_slope', 'r_break', 's_break'):
            np.testing.assert_array_equal(getattr(full, name)[:T+1], getattr(part, name), err_msg=f'{name} T={T}')

def test_trades_do_not_depend_on_future():
    df = load('NQ', '1h').iloc[:4000].reset_index(drop=True)
    tr_full = run(df, SPECS['MNQ'], Cfg(strat='A', sess=None, flat_min=None, risk_engine=False, fixed_qty=1))
    cut = 3000
    tr_part = run(df.iloc[:cut].reset_index(drop=True), SPECS['MNQ'], Cfg(strat='A', sess=None, flat_min=None, risk_engine=False, fixed_qty=1))
    done = tr_full[tr_full.exit_ts < df.ts.values[cut - 1]]
    assert len(done) > 20
    np.testing.assert_allclose(done.pnl.values, tr_part.pnl.values[:len(done)])

if __name__ == '__main__':
    test_lines_do_not_repaint(); test_trades_do_not_depend_on_future(); print('OK')
