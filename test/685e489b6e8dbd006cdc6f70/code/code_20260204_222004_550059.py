from bs4 import BeautifulSoup
from pathlib import Path
import re, json, pandas as pd
html_path = Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-141943_aed56fef15.html')
html = html_path.read_text(encoding='utf-8', errors='ignore')
soup = BeautifulSoup(html, 'html.parser')
# Try to find embedded JSON in script tags
scripts = soup.find_all('script')
json_candidates=[]
for s in scripts:
    if not s.string: 
        continue
    txt = s.string.strip()
    if 'topList' in txt or 'board' in txt or 'movieList' in txt or 'asgard' in txt:
        json_candidates.append(txt[:500])
len(scripts), len(json_candidates)
