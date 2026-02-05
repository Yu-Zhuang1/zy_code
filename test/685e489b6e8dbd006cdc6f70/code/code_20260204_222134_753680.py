from pathlib import Path
import re
raw='log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output/browser_snapshot_20260204-142020_b5b70af176.html'
html=Path(raw).read_text('utf-8','ignore')
scripts=re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
print('num scripts', len(scripts))
for i,s in enumerate(scripts):
    if 'backGroundImg' in s or 'dataSourceDesc' in s or 'movies' in s and 'success' in s:
        print('\n-- script', i, 'len', len(s))
        print('contains backGroundImg', 'backGroundImg' in s, 'dataSourceDesc', 'dataSourceDesc' in s, 'movies', 'movies' in s, 'success', 'success' in s)
        head=s[:200].replace('\n',' ')
        print('head:', head)
        # show around backGroundImg
        if 'backGroundImg' in s:
            idx=s.find('backGroundImg')
            print('around backGroundImg:', s[max(0,idx-60):idx+80].replace('\n',' '))
