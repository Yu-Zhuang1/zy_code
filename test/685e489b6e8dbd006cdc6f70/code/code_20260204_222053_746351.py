from pathlib import Path
import re, json
raw='log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output/browser_snapshot_20260204-142020_b5b70af176.html'
html=Path(raw).read_text('utf-8','ignore')
# get target script
scripts=re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
target=None
for s in scripts:
    if '"data":{\"data\"' in s or ('backGroundImg' in s and 'dataSourceDesc' in s and '"list"' in s):
        target=s
        break
if not target:
    # fallback choose largest script excluding AppData? choose one containing backGroundImg
    for s in scripts:
        if 'backGroundImg' in s and 'dataSourceDesc' in s:
            target=s;break
print('target found', target is not None, 'len', len(target) if target else None)

# Extract JSON assigned to something like '"data":{...}' within that script; find first occurrence of '"data":' then parse braces.
text=target
start=text.find('"data":')
if start==-1:
    start=text.find('data":')
print('start', start)

# brace matching to extract object after "data":
if start!=-1:
    # find first '{' after start
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
    blob=text[brace_start:end]
    # It might include escaped sequences like \"; attempt json.loads directly
    # sometimes it's already JSON, not a string
    try:
        obj=json.loads(blob)
        print('parsed outer keys', list(obj.keys())[:10])
    except Exception as e:
        print('json parse outer failed', e)
        obj=None

    # if obj has nested 'data' key containing actual payload
    payload=obj
    if obj and 'data' in obj and isinstance(obj['data'], dict):
        payload=obj['data']
        if 'data' in payload and isinstance(payload['data'], dict):
            payload=payload['data']
    if payload:
        print('payload keys', list(payload.keys())[:20])
        # print desc fields for scope
        for k in ['title','content','dataSourceDesc','boardTitle','subTitle','year','created']:
            if k in payload:
                v=payload[k]
                print(k, str(v)[:120])
        # locate list items
        # guess list field name
        list_field=None
        for k in ['list','movieList','dataList','items','topList']:
            if k in payload and isinstance(payload[k], list):
                list_field=k
                break
        if list_field:
            items=payload[list_field]
            print('list_field', list_field, 'n', len(items))
            # show first item keys
            if items:
                print('first keys', list(items[0].keys())[:20])
                # Extract rank, name, score fields from first 5
                extracted=[]
                for it in items[:10]:
                    name=it.get('movieName') or it.get('name') or it.get('title')
                    rank=it.get('ranking') or it.get('rank') or it.get('index')
                    score=it.get('score') or it.get('grade') or it.get('movieScore')
                    extracted.append({'rank':rank,'name':name,'score':score})
                print('sample extracted', extracted[:5])
        else:
            # search inside payload for list
            def find_list(d):
                if isinstance(d, dict):
                    for k,v in d.items():
                        if isinstance(v, list) and v and isinstance(v[0], dict) and any(key in v[0] for key in ['movieName','name','score','rank']):
                            return k,v
                        res=find_list(v)
                        if res: return res
                elif isinstance(d, list):
                    for v in d:
                        res=find_list(v)
                        if res: return res
                return None
            res=find_list(payload)
            print('deep list found', bool(res))
            if res:
                k,items=res
                print('deep list key', k, 'n', len(items))
                extracted=[]
                for it in items[:10]:
                    name=it.get('movieName') or it.get('name')
                    rank=it.get('rank') or it.get('ranking')
                    score=it.get('score') or it.get('movieScore')
                    extracted.append({'rank':rank,'name':name,'score':score})
                print('sample extracted', extracted[:5])

