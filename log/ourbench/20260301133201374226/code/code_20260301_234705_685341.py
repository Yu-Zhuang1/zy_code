import pandas as pd, re, pathlib
path = pathlib.Path('log/ourbench0301_2/20260301133201374226/browser/session_output/browser_snapshot_20260301-154658_3a0cc8c396.html')
html = path.read_text(errors='ignore')
# try to locate stock 2618 row by regex
m = re.search(r'\b02618\b.*', html)
print('found line?', bool(m))
print(m.group(0)[:200] if m else 'no')
# Use pandas read_html to extract tables
tables = pd.read_html(html)
print('num tables', len(tables))
# identify table containing 02618
idxs=[]
for i,t in enumerate(tables):
    if (t.astype(str).apply(lambda col: col.str.contains('02618')).any()).any():
        idxs.append(i)
        print('table',i,'shape',t.shape)
print('idxs',idxs)
# print matching rows
for i in idxs[:3]:
    t=tables[i]
    mask = t.astype(str).apply(lambda col: col.str.contains('02618'))
    rows = t[mask.any(axis=1)]
    print('table',i,'rows')
    print(rows.to_string(index=False)[:1500])
