import re
snap_path='log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/browser/session_output_dir/browser_snapshot_20260204-140533_e61746b3ce.html'
js=open(snap_path,'rb').read().decode('utf-8','ignore')
# locate '/mmdb/v1/wish.json'
idx=js.find('/mmdb/v1/wish.json')
print('idx', idx)
print(js[idx-300:idx+500] if idx!=-1 else 'not found')
# also search for 'wish.json' occurrences
for m in re.finditer('wish.json', js):
    print('pos', m.start())
    if m.start()>idx-10 and m.start()<idx+10:
        pass
# Find query param names used around it
if idx!=-1:
    seg=js[idx-2000:idx+2000]
    params=set(re.findall(r'\b([a-zA-Z]{2,20})\b(?=\s*:\s*)', seg))
    print('some keys', sorted(list(params))[:80])
