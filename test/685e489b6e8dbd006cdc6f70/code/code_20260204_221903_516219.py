from pathlib import Path
import re, json
paths = [
'log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/web/session_output/read_webpage_20260204-141848_b5b70af176.html',
'log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/web/session_output/read_webpage_20260204-141848_dc99982003.html',
'log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/web/session_output/read_webpage_20260204-141849_96c7a54c8e.html'
]
for p in paths:
    html = Path(p).read_text(encoding='utf-8', errors='ignore')
    print('\n===', p.split('/')[-1], 'len', len(html))
    # find likely JSON blobs
    for key in ['__NEXT_DATA__','__INITIAL_STATE__','__NUXT__','INITIAL_STATE','SSR_DATA','__APOLLO_STATE__']:
        if key in html:
            print('found', key)
    # look for script type application/json
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        data=m.group(1)
        print('next_data size', len(data))
    # try to find window.__INITIAL_STATE__ assignment
    m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;', html, re.S)
    if m:
        blob=m.group(1)
        print('initial_state size', len(blob))
    # print title and meta description
    t=re.search(r'<title>(.*?)</title>', html, re.S)
    if t: print('title:', t.group(1)[:80])
    d=re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
    if d: print('desc:', d.group(1)[:120])
    # find any board id/name occurrences
    for pat in ['购票评分','board','id=24','year=2024','asgard/board']:
        if pat in html:
            print('contains', pat)
    # find api endpoint patterns
    apis=set(re.findall(r'https?://[^\"\']+asgard[^\"\']+', html))
    if apis:
        print('apis sample:', list(apis)[:3])
    # look for JSON in script tags in general (first 300 chars)
    scripts=re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
    big=[s for s in scripts if len(s)>5000]
    print('num scripts', len(scripts), 'big', len(big))
    if big:
        print('big script head:', big[0][:200].replace('\n',' ')[:200])
