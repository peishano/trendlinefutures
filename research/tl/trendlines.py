"""Deterministic, non-repainting trendline construction (the "fan" method).

Translation of the transcript method into rules
-----------------------------------------------
* Swing points: a pivot high at bar i needs `k` lower highs on each side
  (k=1 -> "3-candle", k=2 -> "5-candle", k=3 -> "7-candle"). It is only KNOWN at
  bar i+k (confirmation delay), and is only used from that bar onward.
* Bearish (resistance) trendline: Point B = newly confirmed pivot high.
  Point A = the most recent earlier pivot high that is HIGHER than B such that
  the ray A->B "holds price": no bar high between A and B pierces the ray by more
  than `tol`*ATR, and no close between B and the confirmation bar is above it.
  Because A is searched from the most recent pivot backwards, a new lower high
  produces a steeper line whose A is usually the previous line's B -- exactly the
  "previous point B becomes new point A" fan described in transcript 1.
  `gen` counts consecutive fan steps (gen>=2 means a steeper fan line).
* Bullish (support) trendline: mirror image using pivot lows (higher lows).
* Break: bar CLOSE beyond the line by more than `disp`*ATR. A broken line is
  deactivated (kept as `last broken line` for retest logic).
* A newly built line replaces the active one of the same side ("adjust to the
  most recent touch point").

Every array value at index t describes the state AFTER bar t has closed, i.e.
what a live trader could know at the close of bar t. Line values for the next
bar are an extrapolation of a straight line, so they are known in advance
(this is what lets a stop order sit on the line).
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass
class Lines:
    # active lines after bar t: value at bar x = px + slope * (x - idx)
    r_ok: np.ndarray; r_idx: np.ndarray; r_px: np.ndarray; r_slope: np.ndarray; r_touch: np.ndarray; r_gen: np.ndarray
    s_ok: np.ndarray; s_idx: np.ndarray; s_px: np.ndarray; s_slope: np.ndarray; s_touch: np.ndarray; s_gen: np.ndarray
    # break events on bar t (evaluated with lines known at t-1)
    r_break: np.ndarray; s_break: np.ndarray
    # line value at bar t of the line that broke (nan otherwise) + its params
    rb_idx: np.ndarray; rb_px: np.ndarray; rb_slope: np.ndarray
    sb_idx: np.ndarray; sb_px: np.ndarray; sb_slope: np.ndarray
    # last confirmed pivot prices (structure stops)
    last_ph: np.ndarray; last_pl: np.ndarray

    def r_val(self, t: int, x: int) -> float:
        return self.r_px[t] + self.r_slope[t] * (x - self.r_idx[t])

    def s_val(self, t: int, x: int) -> float:
        return self.s_px[t] + self.s_slope[t] * (x - self.s_idx[t])


def build(high, low, close, atr, k=2, tol=0.25, disp=0.0, min_touch=2, max_back=12, max_span=600) -> Lines:
    n = len(close)
    f = lambda: np.full(n, np.nan)
    b = lambda: np.zeros(n, dtype=bool)
    i_ = lambda: np.zeros(n, dtype=np.int64)
    L = Lines(b(), i_(), f(), f(), i_(), i_(), b(), i_(), f(), f(), i_(), i_(), b(), b(),
              i_(), f(), f(), i_(), f(), f(), f(), f())
    ph: list[tuple[int, float]] = []
    pl: list[tuple[int, float]] = []
    r = None  # (idx, px, slope, touch, gen, b_idx)
    s = None
    lph = np.nan; lpl = np.nan
    idx = np.arange(n)
    for t in range(n):
        a = atr[t]
        # 1) break checks with lines known at t-1
        if r is not None:
            v = r[1] + r[2] * (t - r[0])
            if close[t] > v + disp * a:
                L.r_break[t] = True
                L.rb_idx[t], L.rb_px[t], L.rb_slope[t] = r[0], r[1], r[2]
                r = None
        if s is not None:
            v = s[1] + s[2] * (t - s[0])
            if close[t] < v - disp * a:
                L.s_break[t] = True
                L.sb_idx[t], L.sb_px[t], L.sb_slope[t] = s[0], s[1], s[2]
                s = None
        # 2) pivot confirmation for bar i = t-k
        i = t - k
        if i - k >= 0:
            w_h = high[i - k:t + 1]
            if high[i] == w_h.max() and high[i] > high[i - k:i].max():
                ph.append((i, high[i])); lph = high[i]
                cand = _make_line(ph, high, close, idx, a, t, tol, min_touch, max_back, +1, max_span)
                if cand is not None:
                    gen = (r[4] + 1) if (r is not None and cand[0] == r[5]) else 1
                    r = (cand[0], cand[1], cand[2], cand[3], gen, i)
            w_l = low[i - k:t + 1]
            if low[i] == w_l.min() and low[i] < low[i - k:i].min():
                pl.append((i, low[i])); lpl = low[i]
                cand = _make_line(pl, low, close, idx, a, t, tol, min_touch, max_back, -1, max_span)
                if cand is not None:
                    gen = (s[4] + 1) if (s is not None and cand[0] == s[5]) else 1
                    s = (cand[0], cand[1], cand[2], cand[3], gen, i)
        # 3) store state
        if r is not None:
            L.r_ok[t] = True; L.r_idx[t], L.r_px[t], L.r_slope[t], L.r_touch[t], L.r_gen[t] = r[0], r[1], r[2], r[3], r[4]
        if s is not None:
            L.s_ok[t] = True; L.s_idx[t], L.s_px[t], L.s_slope[t], L.s_touch[t], L.s_gen[t] = s[0], s[1], s[2], s[3], s[4]
        L.last_ph[t] = lph; L.last_pl[t] = lpl
    return L


def _make_line(piv, ext, close, idx, a, t, tol, min_touch, max_back, side, max_span=600):
    """side=+1 resistance (descending line over highs), -1 support (ascending under lows)."""
    bi, bp = piv[-1]
    lo = max(0, len(piv) - 1 - max_back)
    for j in range(len(piv) - 2, lo - 1, -1):
        ai, ap = piv[j]
        if side > 0 and ap <= bp:   # need a higher earlier high
            continue
        if side < 0 and ap >= bp:   # need a lower earlier low
            continue
        if bi - ai > max_span:      # same cap as the Pine implementation
            continue
        slope = (bp - ap) / (bi - ai)
        seg = slice(ai + 1, bi)
        line = ap + slope * (idx[seg] - ai)
        if side > 0:
            if len(line) and (ext[seg] - line).max() > tol * a:
                continue
            post = slice(bi + 1, t + 1)
            if (close[post] - (ap + slope * (idx[post] - ai))).max(initial=-np.inf) > 0:
                continue
        else:
            if len(line) and (line - ext[seg]).max() > tol * a:
                continue
            post = slice(bi + 1, t + 1)
            if ((ap + slope * (idx[post] - ai)) - close[post]).max(initial=-np.inf) > 0:
                continue
        touch = 2 + sum(1 for (pi, pp) in piv[j + 1:-1] if abs(pp - (ap + slope * (pi - ai))) <= tol * a)
        if touch < min_touch:
            continue
        return (ai, ap, slope, touch)
    return None
