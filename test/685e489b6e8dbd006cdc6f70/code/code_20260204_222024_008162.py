from pathlib import Path
import re
html_path = Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-141943_aed56fef15.html')
html = html_path.read_text(encoding='utf-8', errors='ignore')
# crude text extraction
text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.S|re.I)
text = re.sub(r'<[^>]+>', ' ', text)
text = re.sub(r'\s+', ' ', text)
# find segment starting at year title
start = text.find('2025年电影购票评分榜')
print('start', start)
print(text[start:start+3000])
