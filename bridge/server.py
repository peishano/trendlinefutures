"""TradingView webhook -> risk engine -> broker execution bridge (stdlib only).

Run (paper mode):   python -m bridge.server --config bridge/config.example.json
Endpoints:
  POST /webhook          TradingView alert body (JSON produced by pine/TrendlineFan_Prop_v1.pine)
  POST /admin/flatten    {"token": ...}  flatten everything + engage kill switch
  POST /admin/kill       {"token": ..., "on": true|false}
  GET  /health           status JSON
Safety properties:
  * shared-secret check, JSON schema check, idempotency on (bot,id,action,stop) persisted in SQLite
  * every entry re-validated by RiskEngine (stop required, size capped, daily limits, correlation, window)
  * stops may only tighten; a stop-modify for an unknown trade is rejected
  * a background watchdog marks P&L, enforces the hard daily loss and the time-based flat, and
    flattens if no TradingView heartbeat ("sync") arrives for `heartbeat_timeout_s` while in a position
  * any broker exception on entry -> no position assumed, error logged, kill switch engaged after N errors
"""
from __future__ import annotations
import argparse, datetime as dt, hmac, json, logging, sqlite3, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .risk import RiskEngine, RiskLimits, Position, CONTRACTS, ET
from .broker import PaperBroker

log = logging.getLogger('bridge')


class Bridge:
    def __init__(self, cfg: dict, broker=None, now_fn=None):
        self.cfg = cfg
        lim = RiskLimits(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in cfg.get('limits', {}).items()})
        self.risk = RiskEngine(lim, now_fn)
        self.broker = broker or PaperBroker(CONTRACTS, lim.slippage_ticks)
        self.db = sqlite3.connect(cfg.get('db', 'bridge_state.sqlite'), check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS seen (key TEXT PRIMARY KEY, ts TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS journal (ts TEXT, kind TEXT, body TEXT)')
        self.lock = threading.Lock()
        self.last_sync = time.time()
        self.errors = 0

    # ------------------------------------------------------------ helpers
    def _journal(self, kind, body):
        self.db.execute('INSERT INTO journal VALUES (?,?,?)', (dt.datetime.now(ET).isoformat(), kind, json.dumps(body)))
        self.db.commit()

    def _seen(self, key) -> bool:
        try:
            self.db.execute('INSERT INTO seen VALUES (?,?)', (key, dt.datetime.now(ET).isoformat())); self.db.commit()
            return False
        except sqlite3.IntegrityError:
            return True

    def _flatten_all(self, reason):
        for tid, pnl in self.broker.flatten():
            self.risk.on_close(tid, pnl)
        for tid in list(self.risk.positions):   # broker without per-trade P&L: clear local book
            self.risk.positions.pop(tid, None)
        self._journal('flatten', {'reason': reason})
        log.warning('FLATTEN ALL: %s', reason)

    # ------------------------------------------------------------ webhook
    def handle(self, msg: dict) -> tuple[int, dict]:
        if not hmac.compare_digest(str(msg.get('secret', '')), self.cfg['secret']):
            return 401, {'error': 'bad secret'}
        action = msg.get('action')
        with self.lock:
            self._journal('in', {k: v for k, v in msg.items() if k != 'secret'})
            if action == 'sync':
                self.last_sync = time.time()
                return 200, {'ok': True}
            key = f"{msg.get('bot')}|{msg.get('id')}|{action}|{msg.get('stop')}"
            if self._seen(key):
                return 200, {'ok': True, 'duplicate': True}
            root = msg.get('symbol')
            if action == 'entry':
                side = 1 if msg.get('side') == 'buy' else -1 if msg.get('side') == 'sell' else 0
                try:
                    qty = int(msg['qty']); stop = float(msg['stop'])
                    ref = float(msg.get('ref_price') or self.broker.last.get(root)) if hasattr(self.broker, 'last') else None
                except (KeyError, TypeError, ValueError):
                    return 400, {'error': 'bad entry payload'}
                if side == 0 or ref is None:
                    return 400, {'error': 'missing side or reference price'}
                d = self.risk.check_entry(root, side, qty, ref, stop)
                if not d.ok:
                    self._journal('reject', {'id': msg.get('id'), 'reason': d.reason})
                    return 200, {'ok': False, 'rejected': d.reason}
                try:
                    f = self.broker.place_bracket(msg['id'], root, side, d.qty, stop, msg.get('target'), ref_price=ref)
                except Exception as e:  # rejected / connection failure: assume NOT filled, verify via positions()
                    self.errors += 1
                    if self.errors >= self.cfg.get('max_broker_errors', 3):
                        self.risk.kill_switch = True
                    self._journal('broker_error', {'id': msg.get('id'), 'err': str(e)})
                    return 502, {'error': str(e)}
                self.risk.on_open(Position(msg['id'], root, side, d.qty, f.price, stop, msg.get('target')))
                return 200, {'ok': True, 'qty': d.qty, 'note': d.reason}
            if action == 'modify_stop':
                d = self.risk.check_stop_modify(msg.get('id'), float(msg.get('stop')))
                if not d.ok:
                    return 200, {'ok': False, 'rejected': d.reason}
                self.broker.modify_stop(msg['id'], float(msg['stop'])); self.risk.positions[msg['id']].stop = float(msg['stop'])
                return 200, {'ok': True}
            if action == 'flatten':
                self._flatten_all('strategy flatten'); return 200, {'ok': True}
            return 400, {'error': f'unknown action {action}'}

    # ------------------------------------------------------------ watchdog
    def tick(self, prices: dict | None = None):
        with self.lock:
            if prices and isinstance(self.broker, PaperBroker):
                for root, px in prices.items():
                    for tid, pnl in self.broker.mark(root, px):
                        self.risk.on_close(tid, pnl)
            if self.risk.update_open_pnl(self.broker.open_pnl()):
                self._flatten_all(f'hard daily loss {self.risk.day_pnl:.2f}')
            if self.risk.must_flatten_for_time():
                self._flatten_all('session flat time')
            if self.risk.positions and time.time() - self.last_sync > self.cfg.get('heartbeat_timeout_s', 5400):
                self._flatten_all('TradingView heartbeat lost')


def serve(cfg_path):
    cfg = json.load(open(cfg_path)); br = Bridge(cfg)

    class H(BaseHTTPRequestHandler):
        def _send(self, code, body):
            b = json.dumps(body).encode(); self.send_response(code)
            self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == '/health':
                r = br.risk
                self._send(200, dict(day=str(r.day), day_pnl=r.day_pnl, trades=r.trades, consec=r.consec, halted=r.halted,
                                     reason=r.halt_reason, kill=r.kill_switch, positions=list(r.positions)))
            else:
                self._send(404, {})

        def do_POST(self):
            n = int(self.headers.get('Content-Length', 0))
            try:
                body = json.loads(self.rfile.read(n) or b'{}')
            except json.JSONDecodeError:
                return self._send(400, {'error': 'invalid json'})
            if self.path == '/webhook':
                return self._send(*br.handle(body))
            if self.path.startswith('/admin/') and hmac.compare_digest(str(body.get('token', '')), cfg['admin_token']):
                if self.path == '/admin/flatten':
                    with br.lock:
                        br._flatten_all('manual'); br.risk.kill_switch = True
                    return self._send(200, {'ok': True})
                if self.path == '/admin/kill':
                    br.risk.kill_switch = bool(body.get('on', True)); return self._send(200, {'kill': br.risk.kill_switch})
            self._send(403, {'error': 'forbidden'})

    def loop():
        while True:
            try:
                br.tick()
            except Exception:
                log.exception('watchdog')
            time.sleep(cfg.get('watchdog_s', 2))
    threading.Thread(target=loop, daemon=True).start()
    ThreadingHTTPServer((cfg.get('host', '127.0.0.1'), cfg.get('port', 8080)), H).serve_forever()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    ap = argparse.ArgumentParser(); ap.add_argument('--config', required=True)
    serve(ap.parse_args().config)
