import re, pathlib
path = pathlib.Path('log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/web/session_output_dir/read_webpage_20260204-140432_f49b9157d3.html')
html = path.read_text(encoding='utf-8', errors='ignore')
# Extract around rank occurrence
idx = html.find('rank')
print('idx', idx)
print(html[idx-500:idx+2000])
