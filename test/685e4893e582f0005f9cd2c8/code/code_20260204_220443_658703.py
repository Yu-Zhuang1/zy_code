import re, json, pathlib
path = pathlib.Path('log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/web/session_output_dir/read_webpage_20260204-140432_f49b9157d3.html')
html = path.read_text(encoding='utf-8', errors='ignore')
# find JSON-like segments containing "想看" maybe embedded state
patterns=[r'__NEXT_DATA__\s*=\s*(\{.*?\})\s*;</script>', r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;', r'__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;']
found=[]
for pat in patterns:
    m=re.search(pat, html, re.S)
    if m:
        found.append((pat, m.group(1)[:200]))
found[:3], len(found)
