"""Account-level risk engine for the execution bridge.

Independent of TradingView: every order request is checked here, and the engine
can veto it even if the strategy sent it. All money values are USD.

State is per trading day (CME day rolls at 18:00 America/New_York by default).
Realised P&L comes from broker fills (the bridge reports them via on_fill/on_close);
open P&L comes from the broker/mark-to-market feed via update_open_pnl().
"""
from __future__ import annotations
import datetime as dt
import math
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')


@dataclass
class Contract:
    root: str
    tick: float
    tick_value: float
    rt_cost: float          # round-turn commission+fees per contract
    max_qty: int            # prop cap for this contract type

    @property
    def point_value(self) -> float:
        return self.tick_value / self.tick


CONTRACTS = {
    'MNQ': Contract('MNQ', 0.25, 0.50, 1.50, 50),
    'MES': Contract('MES', 0.25, 1.25, 1.50, 50),
    'MYM': Contract('MYM', 1.0, 0.50, 1.50, 50),
    'M2K': Contract('M2K', 0.10, 0.50, 1.50, 50),
    'NQ': Contract('NQ', 0.25, 5.00, 5.00, 5),
    'ES': Contract('ES', 0.25, 12.50, 5.00, 5),
}

# Treat these as one risk bucket: never hold two of them at once.
CORRELATED = [{'MNQ', 'NQ', 'MES', 'ES', 'MYM', 'M2K'}]


@dataclass
class RiskLimits:
    daily_max_loss: float = 700.0        # internal hard budget (realised + open). Prop DLL reportedly $1,000.
    daily_shutdown: float = 550.0        # no new trade whose full stop-out could take the day below -this
    max_risk_per_trade: float = 150.0
    max_open_risk: float = 150.0         # sum of (entry-stop) risk of all open positions
    max_trades_per_day: int = 4
    max_consecutive_losses: int = 3
    cooldown_minutes_after_loss: int = 0
    profit_lock: float = 0.0             # stop new entries once day P&L >= this (0 = off)
    slippage_ticks: int = 1
    entry_window_et: tuple[str, str] = ('09:30', '15:35')   # entry webhooks accepted only inside this window
    flat_by_et: str = '15:58'            # bridge force-flattens at this time
    day_roll_et: str = '18:00'
    allowed_roots: tuple[str, ...] = ('MNQ',)


@dataclass
class Position:
    trade_id: str
    root: str
    side: int          # +1 long, -1 short
    qty: int
    entry: float
    stop: float
    target: float | None = None

    def risk_usd(self, c: Contract, slip_ticks: int) -> float:
        return self.qty * (abs(self.entry - self.stop) * c.point_value + c.rt_cost + 2 * slip_ticks * c.tick_value)


@dataclass
class Decision:
    ok: bool
    reason: str = ''
    qty: int = 0


class RiskEngine:
    def __init__(self, limits: RiskLimits, now_fn=None):
        self.L = limits
        self.now = now_fn or (lambda: dt.datetime.now(ET))
        self.day = None
        self.realized = 0.0
        self.open_pnl = 0.0
        self.trades = 0
        self.consec = 0
        self.halted = False
        self.halt_reason = ''
        self.last_loss_at: dt.datetime | None = None
        self.positions: dict[str, Position] = {}
        self.kill_switch = False
        self._roll()

    # ------------------------------------------------------------ day handling
    def trading_day(self, t: dt.datetime) -> dt.date:
        h, m = map(int, self.L.day_roll_et.split(':'))
        roll = t.replace(hour=h, minute=m, second=0, microsecond=0)
        return (t + dt.timedelta(days=1)).date() if t >= roll else t.date()

    def _roll(self):
        d = self.trading_day(self.now())
        if d != self.day:
            self.day = d; self.realized = 0.0; self.trades = 0; self.consec = 0
            self.halted = False; self.halt_reason = ''; self.last_loss_at = None

    @property
    def day_pnl(self) -> float:
        return self.realized + self.open_pnl

    def _in_window(self, t: dt.datetime, a: str, b: str) -> bool:
        hm = t.strftime('%H:%M')
        return a <= hm <= b

    # ------------------------------------------------------------ checks
    def size(self, root: str, entry: float, stop: float, risk_usd: float) -> int:
        c = CONTRACTS[root]
        per = abs(entry - stop) * c.point_value + c.rt_cost + 2 * self.L.slippage_ticks * c.tick_value
        if per <= 0:
            return 0
        return max(0, min(int(math.floor(risk_usd / per)), c.max_qty))

    def check_entry(self, root: str, side: int, qty: int, entry: float, stop: float | None) -> Decision:
        self._roll()
        t = self.now()
        if self.kill_switch:
            return Decision(False, 'kill switch engaged')
        if self.halted:
            return Decision(False, f'halted: {self.halt_reason}')
        if root not in self.L.allowed_roots or root not in CONTRACTS:
            return Decision(False, f'instrument {root} not allowed')
        if stop is None or (side > 0 and stop >= entry) or (side < 0 and stop <= entry):
            return Decision(False, 'missing or invalid protective stop')
        if not self._in_window(t, *self.L.entry_window_et):
            return Decision(False, 'outside entry window')
        if self.trades >= self.L.max_trades_per_day:
            return Decision(False, 'max trades per day reached')
        if self.consec >= self.L.max_consecutive_losses:
            return Decision(False, 'consecutive-loss shutdown')
        if self.L.profit_lock and self.day_pnl >= self.L.profit_lock:
            return Decision(False, 'daily profit lock reached')
        if self.last_loss_at and self.L.cooldown_minutes_after_loss and \
                t - self.last_loss_at < dt.timedelta(minutes=self.L.cooldown_minutes_after_loss):
            return Decision(False, 'cooldown after loss')
        for grp in CORRELATED:
            if root in grp and any(p.root in grp for p in self.positions.values()):
                return Decision(False, 'correlated position already open')
        c = CONTRACTS[root]
        max_q = self.size(root, entry, stop, self.L.max_risk_per_trade)
        if max_q < 1:
            return Decision(False, 'stop too wide for max risk per trade')
        q = min(qty, max_q)
        new_risk = Position('x', root, side, q, entry, stop).risk_usd(c, self.L.slippage_ticks)
        open_risk = sum(p.risk_usd(CONTRACTS[p.root], self.L.slippage_ticks) for p in self.positions.values())
        if open_risk + new_risk > self.L.max_open_risk + 1e-9:
            return Decision(False, 'max open risk exceeded')
        if self.day_pnl - open_risk - new_risk < -self.L.daily_shutdown:
            return Decision(False, 'trade could breach internal daily shutdown')
        return Decision(True, 'ok' if q == qty else f'qty reduced {qty}->{q}', q)

    def check_stop_modify(self, trade_id: str, new_stop: float) -> Decision:
        p = self.positions.get(trade_id)
        if p is None:
            return Decision(False, 'unknown position')
        # stops may only tighten (never widen)
        if (p.side > 0 and new_stop < p.stop) or (p.side < 0 and new_stop > p.stop):
            return Decision(False, 'stop widening rejected')
        return Decision(True)

    # ------------------------------------------------------------ events
    def on_open(self, pos: Position):
        self._roll(); self.positions[pos.trade_id] = pos; self.trades += 1

    def on_close(self, trade_id: str, pnl_usd: float):
        self._roll()
        self.positions.pop(trade_id, None)
        self.realized += pnl_usd
        if pnl_usd < 0:
            self.consec += 1; self.last_loss_at = self.now()
        else:
            self.consec = 0
        self._evaluate()

    def update_open_pnl(self, open_pnl: float) -> bool:
        """Returns True if the caller must FLATTEN EVERYTHING now."""
        self._roll(); self.open_pnl = open_pnl
        return self._evaluate()

    def must_flatten_for_time(self) -> bool:
        t = self.now()
        return bool(self.positions) and t.strftime('%H:%M') >= self.L.flat_by_et and t.strftime('%H:%M') < self.L.day_roll_et

    def _evaluate(self) -> bool:
        if self.day_pnl <= -self.L.daily_max_loss:
            self.halted = True; self.halt_reason = f'daily max loss {self.day_pnl:.2f}'
            return True
        if self.realized <= -self.L.daily_shutdown:
            self.halted = True; self.halt_reason = f'daily shutdown {self.realized:.2f}'
        if self.consec >= self.L.max_consecutive_losses:
            self.halted = True; self.halt_reason = 'consecutive losses'
        return False
