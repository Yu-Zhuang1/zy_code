from pathlib import Path
import re, json
raw='log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output/browser_snapshot_20260204-142020_b5b70af176.html'
html=Path(raw).read_text('utf-8','ignore')
print('len', len(html))
# locate AppData or similar
m=re.search(r'var\s+AppData\s*=\s*(\{.*?\})\s*;\s*</script>', html, re.S)
print('AppData', bool(m))
if m:
    data=json.loads(m.group(1).replace('&amp;','&'))
    print('AppData.query', data.get('query'))
# find any window.__PRELOADED_STATE__
for pat in [r'__NEXT_DATA__', r'__INITIAL_STATE__', r'__PRELOADED_STATE__', r'__NUXT__']:
    if pat in html:
        print('contains', pat)

# try find a JSON string with board data embedded, by searching for 'movieList' or 'board' keys in scripts
scripts=re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
print('scripts', len(scripts), 'maxlen', max(len(s) for s in scripts))
# find script containing 'boardData'
target=None
for s in scripts:
    if 'board' in s and 'movie' in s and ('score' in s or 'grade' in s) and len(s)>3000:
        target=s
        break
print('found target script', target is not None)
if target:
    print('target len', len(target))
    # find JSON fragments like "boardData":{...}
    # We'll attempt to find first occurrence of 'data":{' and parse minimal brace match.
    idx=target.find('"data":')
    print('data idx', idx)
    if idx!=-1:
        sub=target[idx:idx+600]
        print('data head', sub[:250])

# Extract visible title and description
mtitle=re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
print('meta desc', mtitle.group(1) if mtitle else None)

# Find text tokens in HTML for scope
for tok in ['中国大陆','上映电影','电影购票评分榜','Top10','更新于','购票评分']:
    if tok in html:
        print('has', tok)

# Attempt to extract the first 12 rank items from rendered DOM, if present
# Look for pattern: <span class="rank">1</span> etc? We'll do generic: rank followed by Chinese name.
# Search for occurrences of 'board-item' class
classes=set(re.findall(r'class="([^"]+)"', html))
print('class count', len(classes))
# find if 'board-item' in any class
print('board-item present', any('board' in c and 'item' in c for c in classes))

# Simple extraction using regex on snapshot text embedded maybe as <p> etc; We'll pick out patterns like '>1<' followed later by '分'
# We'll just see if the HTML contains the film names as plain text
for name in ['志愿军：存亡之战','坂本龙一：杰作','这个杀手不太冷']:
    print(name, 'present', name in html)
