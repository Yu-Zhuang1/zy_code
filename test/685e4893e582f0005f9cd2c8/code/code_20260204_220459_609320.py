import re, os
p='log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/web/session_output_dir/read_webpage_20260204-140406_3c41b731c2.html'
html=open(p,'rb').read().decode('utf-8','ignore')
# find script src
scripts=re.findall(r'<script[^>]+src="([^"]+)"', html)
print('scripts', len(scripts))
print('\n'.join(scripts[:20]))
# find any json endpoints containing board
endpoints=set(re.findall(r'(https?://[^\s\"\']*maoyan\.com[^\s\"\']*(?:ajax|api|board)[^\s\"\']*)', html))
print('endpoints count', len(endpoints))
for u in list(endpoints)[:50]:
    if 'board' in u or 'ajax' in u or 'api' in u:
        print(u)
# find /ajax endpoints explicitly
paths=set(re.findall(r'(/ajax/[^\s\"\']+)', html))
print('ajax paths', len(paths), list(paths)[:20])
# find asgard endpoints
paths2=set(re.findall(r'(/asgard/[^\s\"\']+)', html))
print('asgard paths', len(paths2), list(paths2)[:30])
# look for 'boardType' or 'boardtype'
for pat in ['boardType','boardtype','wish','want','mostExpected']:
    print(pat, html.lower().count(pat.lower()))
# extract movie id list
movie_ids=re.findall(r'/asgard/movie/(\d+)', html)
print('movie_ids', len(movie_ids), movie_ids[:15])
print('unique ids', len(set(movie_ids)))
# find any JSON blobs in page
json_like=re.findall(r'\{\"[^\n]{0,200}?\"\}', html)
print('json_like sample', json_like[:3])
# search for 'boardtype=6' occurrences
print('boardtype=6 present', 'boardtype=6' in html.lower(), 'boardType=6' in html)
# search for 'mostExpected' resources
print('contains /board/6', '/board/6' in html)
# Find any 'update' date
m=re.search(r'(\d{4}-\d{2}-\d{2}).{0,20}更新', html)
print('update date match', m.group(0) if m else None)
