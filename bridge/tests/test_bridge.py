import datetime as dt, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from bridge.risk import RiskEngine, RiskLimits, Position, ET
from bridge.server import Bridge

class Clock:
    def __init__(self, t): self.t = t
    def __call__(self): return self.t

def mk(t='2026-11-24 10:00'):
    clk = Clock(dt.datetime.fromisoformat(t).replace(tzinfo=ET))
    cfg = dict(secret='s', admin_token='a', db=tempfile.mktemp(suffix='.db'), limits={})
    return Bridge(cfg, now_fn=clk), clk

def entry(i, side='buy', stop=19990.0, qty=5):
    return dict(secret='s', bot='T', id=f't{i}', action='entry', side=side, symbol='MNQ', qty=qty, stop=stop, ref_price=20000.0)

def test_rejects_bad_secret_and_duplicates():
    b, _ = mk()
    assert b.handle({**entry(1), 'secret': 'x'})[0] == 401
    assert b.handle(entry(1))[1]['ok'] is True
    assert b.handle(entry(1))[1].get('duplicate') is True

def test_requires_stop_and_caps_size():
    b, _ = mk()
    assert b.handle({**entry(1), 'stop': 20010.0})[1]['rejected'] == 'missing or invalid protective stop'
    r = b.handle(entry(2, qty=40))[1]          # 10pt stop on MNQ = $20/contract + costs -> max ~6 at $150
    assert r['ok'] and r['qty'] <= 6

def test_correlated_and_trade_count():
    b, _ = mk()
    assert b.handle(entry(1))[1]['ok']
    assert b.handle(entry(2))[1]['rejected'] == 'correlated position already open'

def test_daily_loss_halts_and_flattens():
    b, _ = mk()
    b.handle(entry(1, qty=6))
    b.tick({'MNQ': 19989.0})                    # stopped out -> realised loss
    assert not b.risk.positions and b.risk.realized < 0
    b.risk.realized = -560; b.risk._evaluate()
    assert b.risk.halted
    assert b.handle(entry(3))[1]['rejected'].startswith('halted')

def test_consecutive_losses_and_window():
    b, clk = mk()
    for i in range(3):
        b.risk.on_open(Position(f'p{i}', 'MNQ', 1, 1, 20000, 19990)); b.risk.on_close(f'p{i}', -20)
    assert b.handle(entry(9))[1]['rejected'].startswith('halted')
    b2, clk2 = mk('2026-11-24 16:10')
    assert b2.handle(entry(1))[1]['rejected'] == 'outside entry window'

def test_stop_only_tightens_and_time_flat():
    b, clk = mk()
    b.handle(entry(1))
    assert b.handle(dict(secret='s', bot='T', id='t1', action='modify_stop', stop=19980.0))[1]['rejected'] == 'stop widening rejected'
    assert b.handle(dict(secret='s', bot='T', id='t1', action='modify_stop', stop=19995.0))[1]['ok']
    clk.t = clk.t.replace(hour=15, minute=59); b.tick({'MNQ': 20003.0})
    assert not b.risk.positions

def test_day_rolls_at_18_et():
    b, clk = mk()
    b.risk.realized = -600; b.risk._evaluate(); assert b.risk.halted
    clk.t = clk.t.replace(hour=18, minute=1); b.risk._roll()
    assert not b.risk.halted and b.risk.realized == 0
