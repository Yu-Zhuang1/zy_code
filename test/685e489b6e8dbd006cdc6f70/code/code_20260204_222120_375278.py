import re, pathlib
path='log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-142116_8c13f0e187.html'
html=pathlib.Path(path).read_text('utf-8', errors='ignore')
# extract script src and inline that includes api endpoints
srcs=re.findall(r"<script[^>]+src=\"([^\"]+)\"", html)
# find occurrences of 'dashboard' or 'api' strings
snippets=[]
for m in re.finditer(r".{0,80}(dashboard|api|second\.json|/ajax|/getDaily).{0,80}", html):
    snippets.append(m.group(0))
print('script src count',len(srcs))
print(srcs[:20])
print('endpoint snippet count',len(snippets))
print('\n'.join(snippets[:10]))