from pathlib import Path
import re, json
html_path = Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-141943_aed56fef15.html')
html = html_path.read_text(encoding='utf-8', errors='ignore')
# find potential JSON blobs
# common patterns: window.__INITIAL_STATE__=..., window.__PRELOADED_STATE__=..., __NEXT_DATA__
patterns = [r'__NEXT_DATA__\s*=\s*(\{.*?\})\s*;</script>',
            r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;',
            r'window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;']
for pat in patterns:
    m = re.search(pat, html, flags=re.S)
    print(pat, bool(m), m.start(1) if m else None)
print('html length', len(html))
# list script tags quickly by counting occurrences
print('script tags', html.count('<script'))
# search for 'boardId' or 'topList'
for kw in ['boardId','topList','movieList','movieName','score','movieId','asgard/board']:
    idx = html.find(kw)
    print(kw, idx)
