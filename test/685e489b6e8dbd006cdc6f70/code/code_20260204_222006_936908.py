import pathlib, re, json
p=pathlib.Path('session_output_dir/browser_snapshot_20260204-141953_fad0b1ecd4.html')
html=p.read_text('utf-8', errors='ignore')
# extract script contents quickly by regex
scripts=re.findall(r'<script[^>]*>(.*?)</script>', html, flags=re.S|re.I)
len(scripts)
