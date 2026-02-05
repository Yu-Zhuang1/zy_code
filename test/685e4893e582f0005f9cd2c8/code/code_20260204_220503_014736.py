import re, pandas as pd, pathlib
path = pathlib.Path('log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/web/session_output_dir/read_webpage_20260204-140432_f49b9157d3.html')
html = path.read_text(encoding='utf-8', errors='ignore')
card_pat = re.compile(r'<div class="board-card clearfix">(.*?)</div></div>', re.S)
cards = card_pat.findall(html)
rows=[]
for c in cards:
    # rank
    m_rank=re.search(r'<i class="rank-number">\s*(\d+)\s*</i>', c)
    m_id=re.search(r'/asgard/movie/(\d+)', c)
    m_title=re.search(r'<h3 class="title">\s*([^<]+?)\s*</h3>', c)
    # total wish count
    m_total=re.search(r'总想看：\s*([0-9,]+)人', c)
    # monthly new wish: number inside <p class="number">...
    m_month=re.search(r'本月新增想看\s*<p class="number">\s*([0-9,]+)\s*</p>', c)
    if m_rank and m_title:
        rows.append({
            'rank': int(m_rank.group(1)),
            'title_id': m_id.group(1) if m_id else None,
            'title_name': m_title.group(1).strip(),
            'want_total': int(m_total.group(1).replace(',','')) if m_total else None,
            'want_month_new': int(m_month.group(1).replace(',','')) if m_month else None,
        })

df=pd.DataFrame(rows).drop_duplicates(subset=['rank']).sort_values('rank')
df.head(12), df.shape
