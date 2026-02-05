from pathlib import Path
import re, json, html
p='log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/web/session_output/read_webpage_20260204-141848_b5b70af176.html'
text=Path(p).read_text('utf-8','ignore')
# extract AppData JSON
m=re.search(r'var\s+AppData\s*=\s*(\{.*?\})\s*;\s*</script>', text, re.S)
print('AppData found', bool(m))
if m:
    blob=m.group(1)
    # unescape html entities
    blob=html.unescape(blob)
    # JSON parse (it is JSON-like)
    data=json.loads(blob)
    print('AppData keys', list(data.keys())[:20])
    print('name', data.get('name'))
    print('query', data.get('query'))
    # find api fields
    for k in ['api','url','request','initialState','data']:
        if k in data: print('has',k)
    # search for any endpoint strings inside
    import itertools
    def find_urls(obj):
        urls=[]
        if isinstance(obj, dict):
            for v in obj.values():
                urls+=find_urls(v)
        elif isinstance(obj, list):
            for v in obj: urls+=find_urls(v)
        elif isinstance(obj, str):
            if 'http' in obj or '/ajax' in obj or '/asgard' in obj or 'api' in obj:
                urls.append(obj)
        return urls
    urls=find_urls(data)
    # show unique url-like strings
    uniq=[]
    for u in urls:
        if u not in uniq: uniq.append(u)
    print('url-like count', len(uniq))
    for u in uniq[:15]:
        print(' ',u[:180])

# also try to find server-rendered state in other scripts
patterns=[r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;',
          r'window\.__data\s*=\s*(\{.*?\})\s*;']
for pat in patterns:
    m=re.search(pat, text, re.S)
    print('pattern', pat, 'found', bool(m))

# generic search for "movieList" and "data" fields
for token in ['movieList','list','boardData','boardList','dataList','boardName','ranking','items','movieId','movieName']:
    if token in text:
        print('contains token', token)
