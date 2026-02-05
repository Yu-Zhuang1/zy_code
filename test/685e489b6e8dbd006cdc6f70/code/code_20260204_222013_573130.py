import pathlib, re
p=pathlib.Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-141953_fad0b1ecd4.html')
print('exists', p.exists(), 'size', p.stat().st_size if p.exists() else None)
html=p.read_text('utf-8', errors='ignore')
scripts=re.findall(r'<script[^>]*>(.*?)</script>', html, flags=re.S|re.I)
print('num scripts', len(scripts))
# look for initial state markers
keys=['__NEXT_DATA__','__INITIAL_STATE__','Apollo','board','window.__']
for k in keys:
    hits=sum(1 for s in scripts if k in s)
    print(k, hits)
# print around occurrences of __NEXT_DATA__
for s in scripts:
    if '__NEXT_DATA__' in s or '__INITIAL_STATE__' in s:
        print('snippet', s[:1000])
        break
