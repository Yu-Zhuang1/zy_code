import pathlib, re
p=pathlib.Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-141953_fad0b1ecd4.html')
html=p.read_text('utf-8', errors='ignore')
# find api host in config
m=re.search(r'"api":"(http[^"]+)"', html)
print('api host', m.group(1) if m else None)
# search for 'board' api endpoints in html
for pat in ['board','bangdan','asgard/board','/api','/ajax']:
    print(pat, html.count(pat))
# extract all urls in html
urls=set(re.findall(r'https?://[^\"\'\s<>]+', html))
print('num urls', len(urls))
print('\n'.join(list(sorted([u for u in urls if 'board' in u or 'bangdan' in u or 'api' in u]))[:50]))
