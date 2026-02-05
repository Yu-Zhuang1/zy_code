from pathlib import Path
import re, json
raw='log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output/browser_snapshot_20260204-142020_b5b70af176.html'
html=Path(raw).read_text('utf-8','ignore')
# find payload script
scripts=re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
target=None
for s in scripts:
    if 'backGroundImg' in s and 'dataSourceDesc' in s and 'movies' in s and 'success' in s:
        target=s;break
text=target
start=text.find('"data":')
brace_start=text.find('{', start)
depth=0
end=None
for i,ch in enumerate(text[brace_start:], start=brace_start):
    if ch=='{': depth+=1
    elif ch=='}':
        depth-=1
        if depth==0:
            end=i+1
            break
outer=json.loads(text[brace_start:end])
payload=outer['data']['data']
movies=payload['movies']
print('n movies', len(movies))
print('movie0 keys', sorted(list(movies[0].keys()))[:50])
# show short snippet of movie0
m0=movies[0]
# print nested keys if movieInfo exists
if 'movieInfo' in m0 and isinstance(m0['movieInfo'], dict):
    print('movieInfo keys', sorted(m0['movieInfo'].keys())[:60])

# find fields across items
fields=set()
for m in movies:
    fields |= set(m.keys())
print('all top-level fields', sorted(fields))

# guess extraction

def get_name(m):
    for k in ['movieName','name','title','nm','movieNm','cnm']:
        if k in m and m[k]: return m[k]
    if 'movieInfo' in m and isinstance(m['movieInfo'], dict):
        for k in ['movieName','name','title','nm','cnm']:
            if k in m['movieInfo'] and m['movieInfo'][k]: return m['movieInfo'][k]
    return None

def get_score(m):
    for k in ['score','movieScore','sc','rating','grade']:
        if k in m and m[k] is not None: return m[k]
    if 'movieInfo' in m and isinstance(m['movieInfo'], dict):
        for k in ['score','sc']:
            if k in m['movieInfo'] and m['movieInfo'][k] is not None: return m['movieInfo'][k]
    return None

def get_rank(m):
    for k in ['rank','ranking','index']:
        if k in m and m[k] is not None: return m[k]
    return None

ex=[]
for m in movies:
    ex.append({'rank': get_rank(m), 'name': get_name(m), 'score': get_score(m)})
print('ex first5', ex[:5])

# Check ordering by rank increasing and score descending
rank_ok=0; score_ok=0; total=0
score_total=0
for a,b in zip(ex, ex[1:]):
    total+=1
    if a['rank'] is not None and b['rank'] is not None and a['rank']<b['rank']:
        rank_ok+=1
    if a['score'] is not None and b['score'] is not None:
        score_total+=1
        if a['score']>=b['score']:
            score_ok+=1
print('adjacent rank inc', rank_ok,'/',total)
print('adjacent score non-inc', score_ok,'/',score_total)

# Try to locate score/name fields by sampling first movie item JSON
# output compact json of m0 excluding long strings
import math
compact={k:v for k,v in m0.items() if not isinstance(v,str) or len(v)<80}
print('movie0 compact', json.dumps(compact, ensure_ascii=False)[:500])
if 'movieInfo' in m0:
    c2={k:v for k,v in m0['movieInfo'].items() if not isinstance(v,str) or len(v)<80}
    print('movieInfo compact', json.dumps(c2, ensure_ascii=False)[:500])
