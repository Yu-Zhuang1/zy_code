import pathlib, re
p=pathlib.Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-141953_fad0b1ecd4.html')
html=p.read_text('utf-8', errors='ignore')
for kw in ['boardId','boardid','id=24','year','offset','limit','TOP10','getBoard','bangdan']:
    print(kw, len(re.findall(kw, html, flags=re.I)))
# show lines containing boardId
for m in re.finditer(r'.{0,80}boardId.{0,120}', html, flags=re.I|re.S):
    print(m.group(0)[:200])
    break
