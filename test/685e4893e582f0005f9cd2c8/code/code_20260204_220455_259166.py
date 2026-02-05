import re, pandas as pd, pathlib
path = pathlib.Path('log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/web/session_output_dir/read_webpage_20260204-140432_f49b9157d3.html')
html = path.read_text(encoding='utf-8', errors='ignore')
# Extract each board-card block and parse rank, movie id, title, total wish, monthly new wish
# Use regex patterns robustly
card_pat = re.compile(r'<div class="board-card clearfix">(.*?)</div></div>', re.S)
cards = card_pat.findall(html)
len(cards)
