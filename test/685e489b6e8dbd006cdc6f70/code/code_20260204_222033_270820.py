import pathlib, re
p=pathlib.Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-141953_fad0b1ecd4.html')
html=p.read_text('utf-8', errors='ignore')
# extract all paths in JS containing '/api/' or 'bangdan'
paths=set(re.findall(r'\"(/[^\"]{1,120})\"', html))
api_paths=sorted([x for x in paths if 'api' in x or 'bangdan' in x or 'board' in x or 'asgard' in x])
print('num candidate paths', len(api_paths))
for x in api_paths[:80]:
    print(x)
