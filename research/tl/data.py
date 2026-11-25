"""Data loading, session tagging and instrument specifications.

All bars are TradingView continuous front-month futures (NQ1!, ES1!, YM1!, RTY1!),
Electronic (ETH) session, unadjusted for rolls ("split-adjusted only").
Timestamps in the raw CSVs are bar OPEN times in unix seconds (UTC).
"""
from __future__ import annotations
import os
from dataclasses import dataclass
import numpy as np
import pandas as pd

RAW = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'raw')

TF_MIN = {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240}


@dataclass(frozen=True)
class Spec:
    name: str          # tradeable contract
    data: str          # underlying data symbol
    tick: float        # tick size (points)
    pv: float          # $ per point per contract
    rt_cost: float     # round-turn commission + exchange/NFA fees per contract ($)
    max_qty: int       # prop-firm cap for this contract type (50K plan: 50 micros / 5 minis, 3rd-party sourced)


# Commission assumptions: typical prop/Tradovate-routed all-in round turn.
# Micros ~$1.50 RT, minis ~$5.00 RT (conservative vs. common $1.24/$4.28 schedules).
SPECS = {
    'MNQ': Spec('MNQ', 'NQ', 0.25, 2.0, 1.50, 50),
    'MES': Spec('MES', 'ES', 0.25, 5.0, 1.50, 50),
    'MYM': Spec('MYM', 'YM', 1.0, 0.5, 1.50, 50),
    'M2K': Spec('M2K', 'RTY', 0.10, 5.0, 1.50, 50),
    'NQ': Spec('NQ', 'NQ', 0.25, 20.0, 5.00, 5),
    'ES': Spec('ES', 'ES', 0.25, 50.0, 5.00, 5),
    'YM': Spec('YM', 'YM', 1.0, 5.0, 5.00, 5),
    'RTY': Spec('RTY', 'RTY', 0.10, 50.0, 5.00, 5),
}


def load(sym: str, tf: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(RAW, f'{sym}_{tf}.csv'))
    df['ts'] = pd.to_datetime(df.t, unit='s', utc=True).dt.tz_convert('America/New_York')
    df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
    df = df[['ts', 'open', 'high', 'low', 'close', 'volume']].reset_index(drop=True)
    mins = TF_MIN[tf]
    df['close_ts'] = df.ts + pd.Timedelta(minutes=mins)
    # CME trading day: the session that opens 18:00 ET belongs to the next calendar day.
    df['tday'] = (df.ts + pd.Timedelta(hours=6)).dt.date
    # minutes since midnight ET of bar open / close
    df['open_min'] = df.ts.dt.hour * 60 + df.ts.dt.minute
    df['close_min'] = df.close_ts.dt.hour * 60 + df.close_ts.dt.minute
    # gap detector: a bar whose previous bar is in another trading day = new session
    df['new_session'] = df.tday != df.tday.shift(1)
    return df


def atr(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h, l, c = df.high.values, df.low.values, df.close.values
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    out = np.empty_like(tr)
    out[0] = tr[0]
    a = 1.0 / n
    for i in range(1, len(tr)):
        out[i] = out[i - 1] + a * (tr[i] - out[i - 1])
    return out
