from pathlib import Path
import re, json
p='log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/web/session_output/read_webpage_20260204-141848_b5b70af176.html'
text=Path(p).read_text(encoding='utf-8', errors='ignore')
m=re.search(r'var\s+AppData\s*=\s*(\{.*?\})\s*;\s*</script>', text, re.S)
print('AppData found', bool(m))
if m:
    blob=m.group(1)
    blob=blob.replace('&amp;','&')
    data=json.loads(blob)
    print('name', data.get('name'))
    print('query', data.get('query'))
    # collect url-like strings
    def walk(o, out):
        if isinstance(o, dict):
            for v in o.values(): walk(v,out)
        elif isinstance(o, list):
            for v in o: walk(v,out)
        elif isinstance(o, str):
            if 'http' in o or '/ajax' in o or '/asgard' in o:
                out.append(o)
    out=[]
    walk(data,out)
    uniq=[]
    for s in out:
        if s not in uniq: uniq.append(s)
    print('url-like sample:', uniq[:10])

# Find any inline JSON containing board data in scripts
# heuristic: look for "board" and "movie" in same script and large
scripts=re.findall(r'<script[^>]*>(.*?)</script>', text, re.S)
large=[s for s in scripts if len(s)>2000]
print('large scripts', len(large), [len(s) for s in large[:3]])
for i,s in enumerate(large[:5]):
    if 'movie' in s and 'board' in s:
        print('large script', i, 'has movie+board')
        print(s[:200].replace('\n',' '))

# simple regex to locate board title text nodes
for pat in [r'购票评分榜', r'电影购票评分榜', r'2024年.*?购票评分']:
    if re.search(pat, text):
        print('matched', pat)
