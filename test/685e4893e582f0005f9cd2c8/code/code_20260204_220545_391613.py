import re, os, textwrap, json
snap_path='log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/browser/session_output_dir/browser_snapshot_20260204-140533_e61746b3ce.html'
js=open(snap_path,'rb').read().decode('utf-8','ignore')
print('len',len(js))
# Search for board api endpoints and xhr
patterns=[r'/ajax/[^"\']+', r'https?://[^"\']+ajax[^"\']+', r'boardId\"\s*:\s*\d+', r'boardType\"\s*:\s*\d+', r'boardType\s*[:=]\s*\d+', r'mostExpected', r'wish']
for pat in patterns:
    m=re.findall(pat, js)
    if m:
        print(pat, 'count', len(m), 'sample', m[:5])
# Search for 'asgard' api endpoints
m=re.findall(r'https?://[^"\']+maoyan\.com[^"\']+', js)
print('maoyan urls', len(m))
print('sample', m[:20])
# Look for fetch or axios endpoints
for key in ['fetch','axios','XMLHttpRequest','jsonp','mtop','request','api']:
    if key in js:
        print('contains', key)
# find any 'board/6' occurrences
print('board/6 occurrences', js.count('board/6'))
# attempt to locate a request config object around boardType
idx=js.find('boardType')
print('first idx', idx)
print(js[idx-200:idx+200] if idx!=-1 else 'none')
# search for 'asgard' and 'board' together
for m in re.finditer(r'board', js):
    if m.start()<50000:
        pass
# maybe endpoint is /asgard/board/{id}?$from=canary and inside calls /ajax/board?boardType=6
# search for 'boardType=6'
print('boardType=6 present', 'boardType=6' in js)
# extract endpoints with boardType
m=re.findall(r'[^\s"\']*board[^\s"\']*\?[^\s"\']*boardType[^\s"\']*', js)
print('endpoints with boardType', len(m), m[:10])
# extract endpoints with 'wish' maybe wantCount
m2=re.findall(r'[^\s"\']*(?:wish|want)[^\s"\']*', js)
print('tokens wish/want sample', m2[:50])
