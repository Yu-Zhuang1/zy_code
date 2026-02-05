import re, json, os, pandas as pd, pathlib
paths = [
'log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/web/session_output_dir/read_webpage_20260204-140406_3c41b731c2.html',
'log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/web/session_output_dir/read_webpage_20260204-140408_f49b9157d3.html',
'log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/web/session_output_dir/read_webpage_20260204-140409_4d494bf129.html'
]
for p in paths:
    if os.path.exists(p):
        txt=open(p,'rb').read().decode('utf-8','ignore')
        print('\n==',p,'len',len(txt))
        # find potential json endpoints
        for pat in [r'https?://[^\"\']+ajax[^\"\']+', r'/ajax/[^\"\']+', r'boardtype=\d+', r'boardType\":\d+', r'api[^\"\']+']:
            pass
        hits=set(re.findall(r'(https?://[^\s\"\']+(?:ajax|asgard)[^\s\"\']+)', txt))
        if hits:
            print('url hits', list(hits)[:10])
        hits2=set(re.findall(r'(/ajax/[^\s\"\']+)', txt))
        if hits2:
            print('ajax path hits', list(hits2)[:10])
        hits3=set(re.findall(r'boardtype\s*=\s*(\d+)', txt, flags=re.I))
        if hits3:
            print('boardtype', hits3)
        # script contains JSON?
        m=re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;\s*</script>', txt, flags=re.S)
        print('initial_state', bool(m))
        if m:
            print('initial_state size', len(m.group(1)))
        # search for 'want' 'wish'
        for key in ['board/','asgard/board','mostExpected','most-wanted','wish','want']:
            if key in txt:
                print('contains', key)
        # look for json embedded as __NEXT_DATA__ or etc
        m2=re.search(r'__NEXT_DATA__\s*=\s*({.*?})\s*</script>', txt, flags=re.S)
        print('__NEXT_DATA__', bool(m2))
        if m2:
            print('next size', len(m2.group(1)))

print('done')