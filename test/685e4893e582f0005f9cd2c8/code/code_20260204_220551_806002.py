import re, os, json
snap_path='log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/browser/session_output_dir/browser_snapshot_20260204-140533_e61746b3ce.html'
js=open(snap_path,'rb').read().decode('utf-8','ignore')
print('len',len(js))
patterns=[r"/ajax/[^\"\']+", r"https?://[^\"\']+ajax[^\"\']+", r"boardId\"\s*:\s*\d+", r"boardType\"\s*:\s*\d+", r"boardType\s*[:=]\s*\d+", r"mostExpected", r"wish"]
for pat in patterns:
    m=re.findall(pat, js)
    if m:
        print(pat, 'count', len(m), 'sample', m[:5])
maoyan_urls=re.findall(r"https?://[^\"\']+maoyan\\.com[^\"\']+", js)
print('maoyan urls', len(maoyan_urls))
print('sample', maoyan_urls[:20])
for key in ['fetch','axios','XMLHttpRequest','jsonp','request','api']:
    if key in js:
        print('contains', key)
print('board/6 occurrences', js.count('board/6'))
idx=js.find('boardType')
print('first idx', idx)
print(js[idx-200:idx+200] if idx!=-1 else 'none')
print('boardType=6 present', 'boardType=6' in js)
with_bt=re.findall(r"[^\s\"\']*board[^\s\"\']*\?[^\s\"\']*boardType[^\s\"\']*", js)
print('endpoints with boardType', len(with_bt), with_bt[:10])
