"""Ingest TradingView get_ohlcv JSON dumps into per-symbol/interval parquet-free CSVs (deduped)."""
import glob, json, os, sys
import pandas as pd
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/.claude/projects/-home-user-trendlinefutures')
OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
os.makedirs(OUT, exist_ok=True)
frames = {}
for f in glob.glob(os.path.join(SRC, '**', 'mcp-Trading_View-mcp-tv-get-ohlcv-*.txt'), recursive=True):
    d = json.load(open(f))
    if isinstance(d, list):
        d = json.loads(d[0]['text'])
    if 'bars' not in d or not isinstance(d['bars'], dict):
        continue
    df = pd.DataFrame(d['bars'])[['t', 'o', 'h', 'l', 'c', 'v']]
    key = (d['symbol'].split(':')[1].replace('1!', ''), d['interval'])
    frames.setdefault(key, []).append(df)
for (sym, iv), fs in sorted(frames.items()):
    path = os.path.join(OUT, f'{sym}_{iv}.csv')
    allf = pd.concat(fs + ([pd.read_csv(path)] if os.path.exists(path) else []))
    allf = allf.drop_duplicates('t', keep='first').sort_values('t')
    allf.to_csv(path, index=False)
    ts = pd.to_datetime(allf.t, unit='s', utc=True)
    print(f'{sym:4s} {iv:4s} {len(allf):6d} bars  {ts.min():%Y-%m-%d %H:%M} -> {ts.max():%Y-%m-%d %H:%M}')
