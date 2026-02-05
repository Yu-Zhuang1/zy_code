from pathlib import Path
import re, json
raw='log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output/browser_snapshot_20260204-142020_b5b70af176.html'
html=Path(raw).read_text('utf-8','ignore')
# find the JSON payload by brace matching after '"data":'
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
print('movie0 keys', movies[0].keys())
# show one movie item
import pprint
pprint.pprint(movies[0])
# find fields for name and score across items
fields=set()
for m in movies:
    fields |= set(m.keys())
print('all fields', sorted(fields))
# determine best name and score keys
name_keys=[k for k in fields if 'Name' in k or k in ['name','title','movieName','nm','movieNm','cnm','enName']]
score_keys=[k for k in fields if 'score' in k.lower() or 'Score' in k or k in ['sc','grade','rating']]
print('name_keys candidates', name_keys)
print('score_keys candidates', score_keys)
# construct extracted list using discovered keys
# choose if there is 'movieInfo' nested
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

ex=[]
for m in movies:
    ex.append({'rank': m.get('rank') or m.get('ranking'), 'name': get_name(m), 'score': get_score(m)})
print('extracted', ex)
# check sorting by score descending
scores=[e['score'] for e in ex]
print('scores', scores)
# compute consistency: adjacent score non-increasing
ok=0; total=0
for a,b in zip(ex, ex[1:]):
    if a['score'] is None or b['score'] is None:
        continue
    total+=1
    if a['score']>=b['score']: ok+=1
print('adjacent score check', ok, '/', total)
