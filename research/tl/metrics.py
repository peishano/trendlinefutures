from __future__ import annotations
import numpy as np
import pandas as pd


def daily(tr: pd.DataFrame, all_days=None) -> pd.Series:
    d = tr.groupby('tday').pnl.sum() if len(tr) else pd.Series(dtype=float)
    if all_days is not None:
        d = d.reindex(all_days, fill_value=0.0)
    return d


def streak(x: np.ndarray) -> int:
    best = cur = 0
    for v in x:
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return best


def summarize(tr: pd.DataFrame, n_days: int, bar_min: int = 0, label: dict | None = None) -> dict:
    out = dict(label or {})
    if len(tr) == 0:
        out.update(trades=0, net=0.0)
        return out
    p = tr.pnl.values
    w, ls = p[p > 0], p[p <= 0]
    dd_curve = np.cumsum(p)
    mdd = float((np.maximum.accumulate(np.r_[0, dd_curve]) - np.r_[0, dd_curve]).max())
    d = daily(tr)
    active = len(d)
    dly = d.reindex(range(0), fill_value=0) if False else d
    # daily sharpe over ALL trading days in sample (inactive days = 0)
    dfull = np.r_[d.values, np.zeros(max(n_days - active, 0))]
    sd = dfull.std(ddof=1) if len(dfull) > 1 else np.nan
    neg = dfull[dfull < 0]
    ddev = np.sqrt((neg ** 2).sum() / len(dfull)) if len(dfull) else np.nan
    gross_cost = None
    out.update(
        trades=len(p), net=float(p.sum()), win_rate=float((p > 0).mean()),
        pf=float(w.sum() / -ls.sum()) if ls.sum() < 0 else np.inf,
        avg_win=float(w.mean()) if len(w) else 0.0, avg_loss=float(ls.mean()) if len(ls) else 0.0,
        exp=float(p.mean()), exp_R=float(np.nanmean(tr.R.values)),
        max_dd=mdd, ret_dd=float(p.sum() / mdd) if mdd > 0 else np.inf,
        trades_day=len(p) / max(n_days, 1),
        hold_min=float(tr.bars.mean() * bar_min) if bar_min else float(tr.bars.mean()),
        max_losing_streak=streak(p),
        prof_days=float((d > 0).sum() / max(active, 1)),
        sharpe=float(dfull.mean() / sd * np.sqrt(252)) if sd and sd > 0 else np.nan,
        sortino=float(dfull.mean() / ddev * np.sqrt(252)) if ddev and ddev > 0 else np.nan,
        worst_day=float(d.min()), best_day=float(d.max()),
        days_le_550=int((d <= -550).sum()), days_le_700=int((d <= -700).sum()),
        d250=float((d >= 250).mean()), d500=float((d >= 500).mean()),
        d750=float((d >= 750).mean()), d1000=float((d >= 1000).mean()),
    )
    return out


def monthly(tr: pd.DataFrame) -> pd.Series:
    if not len(tr):
        return pd.Series(dtype=float)
    m = pd.to_datetime(tr.tday).dt.to_period('M')
    return tr.groupby(m).pnl.sum()
