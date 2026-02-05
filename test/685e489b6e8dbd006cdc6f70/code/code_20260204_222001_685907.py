from bs4 import BeautifulSoup
import re, json, pathlib
html_path = pathlib.Path('session_output_dir/browser_snapshot_20260204-141953_fad0b1ecd4.html')
html = html_path.read_text('utf-8', errors='ignore')
soup = BeautifulSoup(html, 'html.parser')
# find script tags with JSON or window.__INITIAL_STATE__
scripts = soup.find_all('script')
found=[]
for i,s in enumerate(scripts):
    txt=s.get_text('\n')
    if 'board' in txt or 'asgard' in txt or '榜单' in txt or '__NEXT_DATA__' in txt or '__INITIAL_STATE__' in txt or 'Apollo' in txt or 'graphql' in txt:
        if len(txt.strip())>0:
            found.append((i, txt[:5000]))
len(scripts), len(found)