import re
snap_path='log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/browser/session_output_dir/browser_snapshot_20260204-140533_e61746b3ce.html'
js=open(snap_path,'rb').read().decode('utf-8','ignore')
for pat in [r'https?://[^\"\']+', r'//[^\"\']+']:
    urls=re.findall(pat, js)
    print(pat, len(urls))
    # filter interesting
    ints=[u for u in urls if any(k in u for k in ['maoyan','pipi','meituan','dpfile','api','ajax','asgard'])]
    print('interesting', len(ints))
    print(ints[:30])
# search for domain-like strings without protocol
cands=set(re.findall(r'[a-zA-Z0-9.-]+\.(?:com|cn|net)(?::\d+)?(?:/[a-zA-Z0-9_./-]+)?', js))
ints=[c for c in cands if any(k in c for k in ['maoyan','meituan','pipi','dpfile','api','ajax'])]
print('domain cands', len(cands), 'interesting', len(ints))
print(sorted(ints)[:50])
# look for /api/ path strings
paths=set(re.findall(r'/(?:api|ajax)/[a-zA-Z0-9_./-]+', js))
print('api/ajax paths', len(paths))
print(list(paths)[:50])
# look for request path in JSONP like '...get' '...board'
paths2=set(re.findall(r'"(/[^\"]+)"', js))
ints2=[p for p in paths2 if 'board' in p or 'wish' in p or 'movie' in p or 'rank' in p]
print('quoted paths total', len(paths2), 'interesting', len(ints2))
print(list(ints2)[:80])
