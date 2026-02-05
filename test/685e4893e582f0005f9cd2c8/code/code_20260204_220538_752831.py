import re, pandas as pd, pathlib

raw_path = pathlib.Path('log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/web/session_output_dir/read_webpage_20260204-140432_f49b9157d3.html')
html = raw_path.read_text(encoding='utf-8', errors='ignore')

m_update = re.search(r'(\d{4}-\d{2}-\d{2})\s*已更新', html)
update_date = m_update.group(1) if m_update else None

segments = html.split('<div class="board-card clearfix">')[1:]
rows=[]
for seg in segments:
    s = seg[:9000]
    m_rank=re.search(r'<i class="rank-number">\s*(\d+)\s*</i>', s)
    m_id=re.search(r'/asgard/movie/(\d+)', s)
    m_title=re.search(r'<h3 class="title">\s*([^<]+?)\s*</h3>', s)
    m_total=re.search(r'总想看：\s*([0-9,]+)人', s)
    m_month=re.search(r'本月新增想看\s*<p class="number">\s*([0-9,]+)\s*</p>', s)
    if m_rank and m_title:
        rows.append({
            'rank': int(m_rank.group(1)),
            'title_id': m_id.group(1) if m_id else None,
            'title_name': m_title.group(1).strip(),
            'want_total': int(m_total.group(1).replace(',','')) if m_total else None,
            'want_month_new': int(m_month.group(1).replace(',','')) if m_month else None,
        })

df=pd.DataFrame(rows).drop_duplicates(subset=['rank']).sort_values('rank').reset_index(drop=True)
maxdist = max(abs(5-8), abs(12-8))
sub = df[(df['rank']>=5)&(df['rank']<=12)].copy()
sub['rank_proximity_score'] = (1 - (sub['rank']-8).abs()/maxdist).clip(lower=0, upper=1)

rank5_12 = sub[['rank','title_id','title_name','want_total','want_month_new','rank_proximity_score']].reset_index(drop=True)
rank7_9 = rank5_12[rank5_12['rank'].between(7,9)].reset_index(drop=True)

artifact_dir = pathlib.Path('session_output_dir')
artifact_dir.mkdir(exist_ok=True)
rank5_12_path = artifact_dir/'maoyan_want_snapshot_20260204_rank5_12.json'
rank7_9_path = artifact_dir/'maoyan_want_snapshot_20260204_rank7_9.json'
rank5_12.to_json(rank5_12_path, orient='records', force_ascii=False, indent=2)
rank7_9.to_json(rank7_9_path, orient='records', force_ascii=False, indent=2)

print('update_date', update_date, 'parsed_n', df.shape[0])
print(rank5_12.to_string(index=False))
print('artifacts', rank5_12_path, rank7_9_path)
