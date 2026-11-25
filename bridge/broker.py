"""Broker adapters.

PaperBroker  — fully simulated; use for the paper-trading validation stage.
TradovateBroker — REST skeleton for Tradovate (the platform third-party sources say IQ Capital's
                  DLL plans use). UNTESTED: requires Tradovate API access for the funded/eval account,
                  which prop firms frequently do NOT grant, and IQ Capital's automation policy is UNKNOWN /
                  reportedly prohibits bots. Do not enable without written permission from IQ Capital.
"""
from __future__ import annotations
import json, logging, time, urllib.request
from dataclasses import dataclass

log = logging.getLogger('broker')


@dataclass
class Fill:
    trade_id: str
    price: float
    qty: int


class Broker:
    def place_bracket(self, trade_id, root, side, qty, stop, target=None) -> Fill: ...
    def modify_stop(self, trade_id, new_stop) -> None: ...
    def flatten(self, trade_id=None) -> list[tuple[str, float]]: ...   # returns [(trade_id, pnl_usd)]
    def open_pnl(self) -> float: ...
    def positions(self) -> dict: ...


class PaperBroker(Broker):
    """Market orders fill at the last price supplied by `mark()` (or the webhook's reference price) +/- slippage."""

    def __init__(self, contracts, slippage_ticks=1):
        self.C = contracts; self.slip = slippage_ticks
        self.last = {}; self.pos = {}

    def mark(self, root, price):
        self.last[root] = price
        out = []
        for tid, p in list(self.pos.items()):   # simulate resting stop/target orders
            if p['root'] != root:
                continue
            hit_stop = (p['side'] > 0 and price <= p['stop']) or (p['side'] < 0 and price >= p['stop'])
            hit_tgt = p['target'] is not None and ((p['side'] > 0 and price >= p['target']) or (p['side'] < 0 and price <= p['target']))
            if hit_stop or hit_tgt:
                out.append((tid, self._close(tid, p['stop'] if hit_stop else p['target'], slip=hit_stop)))
        return out

    def place_bracket(self, trade_id, root, side, qty, stop, target=None, ref_price=None):
        c = self.C[root]
        px = (ref_price if ref_price is not None else self.last[root]) + side * self.slip * c.tick
        self.pos[trade_id] = dict(root=root, side=side, qty=qty, entry=px, stop=stop, target=target)
        log.info('PAPER fill %s %s %+d x%d @ %.2f stop %.2f', trade_id, root, side, qty, px, stop)
        return Fill(trade_id, px, qty)

    def modify_stop(self, trade_id, new_stop):
        if trade_id in self.pos:
            self.pos[trade_id]['stop'] = new_stop

    def _close(self, tid, px, slip=True):
        p = self.pos.pop(tid); c = self.C[p['root']]
        px = px - p['side'] * (self.slip * c.tick if slip else 0)
        pnl = p['side'] * (px - p['entry']) * c.point_value * p['qty'] - c.rt_cost * p['qty']
        log.info('PAPER close %s @ %.2f pnl %.2f', tid, px, pnl)
        return pnl

    def flatten(self, trade_id=None):
        ids = [trade_id] if trade_id else list(self.pos)
        return [(t, self._close(t, self.last[self.pos[t]['root']])) for t in ids if t in self.pos]

    def open_pnl(self):
        return sum(p['side'] * (self.last.get(p['root'], p['entry']) - p['entry']) * self.C[p['root']].point_value * p['qty']
                   for p in self.pos.values())

    def positions(self):
        return dict(self.pos)


class TradovateBroker(Broker):  # pragma: no cover - requires live credentials
    """Minimal Tradovate REST client (https://api.tradovate.com). Endpoints used:
    POST /auth/accesstokenrequest, GET /contract/find, POST /order/placeOSO, POST /order/modifyorder,
    POST /order/liquidateposition, GET /position/list, GET /cashBalance/getcashbalancesnapshot.
    Bracket = market entry + OSO stop (+ optional limit). Front-month symbol resolution must be configured.
    """

    def __init__(self, base_url, username, password, app_id, app_version, cid, sec, account_spec, account_id, symbol_map):
        self.base = base_url.rstrip('/'); self.creds = dict(name=username, password=password, appId=app_id,
                                                           appVersion=app_version, cid=cid, sec=sec)
        self.account_spec, self.account_id, self.symbol_map = account_spec, account_id, symbol_map
        self.token = None; self.token_exp = 0; self.stop_orders = {}

    def _req(self, path, body=None, method='POST'):
        if not self.token or time.time() > self.token_exp - 60:
            self._auth()
        r = urllib.request.Request(self.base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                   headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.token}'})
        with urllib.request.urlopen(r, timeout=5) as resp:
            return json.loads(resp.read() or b'null')

    def _auth(self):
        r = urllib.request.Request(self.base + '/auth/accesstokenrequest', method='POST', data=json.dumps(self.creds).encode(),
                                   headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(r, timeout=5) as resp:
            d = json.loads(resp.read())
        if 'accessToken' not in d:
            raise RuntimeError(f'Tradovate auth failed: {d.get("errorText")}')
        self.token = d['accessToken']; self.token_exp = time.time() + 75 * 60

    def place_bracket(self, trade_id, root, side, qty, stop, target=None, ref_price=None):
        sym = self.symbol_map[root]
        action = 'Buy' if side > 0 else 'Sell'; opp = 'Sell' if side > 0 else 'Buy'
        body = dict(accountSpec=self.account_spec, accountId=self.account_id, action=action, symbol=sym, orderQty=qty,
                    orderType='Market', isAutomated=True, clOrdId=trade_id,
                    bracket1=dict(action=opp, orderType='Stop', stopPrice=stop))
        if target is not None:
            body['bracket2'] = dict(action=opp, orderType='Limit', price=target)
        d = self._req('/order/placeOSO', body)
        if d.get('failureReason') or d.get('errorText'):
            raise RuntimeError(f'order rejected: {d}')
        self.stop_orders[trade_id] = d.get('oso1Id')
        return Fill(trade_id, float('nan'), qty)   # real fill price arrives via /fill or websocket

    def modify_stop(self, trade_id, new_stop):
        oid = self.stop_orders.get(trade_id)
        if oid:
            self._req('/order/modifyorder', dict(orderId=oid, orderQty=None, orderType='Stop', stopPrice=new_stop, isAutomated=True))

    def flatten(self, trade_id=None):
        for p in self._req('/position/list', method='GET') or []:
            if p.get('netPos'):
                self._req('/order/liquidateposition', dict(accountId=self.account_id, contractId=p['contractId'], admin=False))
        return []

    def open_pnl(self):
        d = self._req('/cashBalance/getcashbalancesnapshot', dict(accountId=self.account_id))
        return float(d.get('openPnL', 0.0))

    def positions(self):
        return {p['contractId']: p for p in (self._req('/position/list', method='GET') or []) if p.get('netPos')}
