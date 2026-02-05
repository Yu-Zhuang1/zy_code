import pathlib, re
p=pathlib.Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-141953_fad0b1ecd4.html')
html=p.read_text('utf-8', errors='ignore')
scripts=re.findall(r'<script[^>]*>(.*?)</script>', html, flags=re.S|re.I)
# find script containing 'board'
for s in scripts:
    if 'board' in s:
        print(s[:2000])
        break
