import pathlib, re, json
p=pathlib.Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/web/session_output/read_webpage_20260204-141848_b5b70af176.html')
html=p.read_text('utf-8', errors='ignore')
m=re.search(r'var\s+AppData\s*=\s*(\{.*?\});', html, flags=re.S)
app_json=json.loads(m.group(1))
# print keys and config hosts
a=app_json.get('$config',{})
host=a.get('host',{})
print('host keys', list(host.keys())[:20])
print('api host', host.get('api'))
# search for api endpoints in html: look for '/api/' patterns or 'bangdan' in request url
urls=set(re.findall(r'https?://[^\"\'\s<>]+', html))
print('urls containing bangdan/api/board:', [u for u in sorted(urls) if 'bangdan' in u or 'board' in u or 'api' in u][:40])
# look for fetch/xhr config in html
for pat in ['maoyanapi.vip.sankuai.com', 'getJSON', 'axios', 'XMLHttpRequest', 'fetch(']:
    print(pat, html.count(pat))
