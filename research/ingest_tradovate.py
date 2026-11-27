"""Merge Tradovate market_history JSON dumps (5-min bars, individual quarterly contracts) into a front-month
series data/raw/{ROOT}_5m_tv.csv. Each file holds one contract over its front-month window (we only request
that window), so concatenating gives a roll-on-Thursday-before-expiry-week continuous series (unadjusted)."""
import glob, json, os, sys
import pandas as pd
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/.claude/projects/-home-user-trendlinefutures')
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
fr = {}
for f in glob.glob(os.path.join(SRC, '**', 'mcp-Tradovate_Demo-market_history-*.txt'), recursive=True):
    d = json.load(open(f))
    if d.get('barSize') != 5 or 'bars' not in d or not d['bars'] or 'open' not in d['bars'][0]:
        continue
    df = pd.DataFrame(d['bars'])
    df['t'] = (pd.to_datetime(df.timestamp, utc=True) - pd.Timestamp('1970-01-01', tz='UTC')).dt.total_seconds().astype('int64')
    df['v'] = df.upVolume + df.downVolume
    df = df.rename(columns={'open': 'o', 'high': 'h', 'low': 'l', 'close': 'c'})[['t', 'o', 'h', 'l', 'c', 'v']]
    df['contract'] = d['symbol']
    fr.setdefault(d['symbol'][:-2], []).append(df)
for root, fs in fr.items():
    a = pd.concat(fs).drop_duplicates('t', keep='last').sort_values('t')
    a.to_csv(os.path.join(OUT, f'{root}_5m_tv.csv'), index=False)
    ts = pd.to_datetime(a.t, unit='s', utc=True)
    gaps = ts.diff().dt.total_seconds() / 86400
    print(root, len(a), ts.min(), ts.max(), 'contracts', a.contract.nunique(), 'gaps>4d:', (gaps > 4).sum())
