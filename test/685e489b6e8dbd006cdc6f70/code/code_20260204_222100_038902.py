from pathlib import Path
import re, json
html_path = Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-141943_aed56fef15.html')
html = html_path.read_text(encoding='utf-8', errors='ignore')
# Extract text
text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.S|re.I)
text = re.sub(r'<[^>]+>', ' ', text)
text = re.sub(r'&nbsp;',' ', text)
text = re.sub(r'\s+',' ', text).strip()
# segment containing rankings
start = text.find('看过')
end = text.find('数据说明')
seg = text[start:end]
# find rank token positions in seg; use word boundary on digits with surrounding spaces
rank_positions=[]
for m in re.finditer(r'(?<!\d)(10|[1-9])(?!\d)\s+', seg):
    r=int(m.group(1))
    # Heuristic: only accept if preceded by space or start and followed by Chinese title char
    rank_positions.append((m.start(), r, m.end()))
# Keep first occurrence per rank in ascending order of appearance, but ensure 1-10 exists
# choose earliest appearance for each rank
pos_by_rank={}
for pos,r,endpos in rank_positions:
    if r not in pos_by_rank:
        pos_by_rank[r]=(pos,endpos)
# Build ordered by rank 1..10 by locating their positions in seg
blocks=[]
for r in range(1,11):
    if r not in pos_by_rank:
        continue
    pos,endpos=pos_by_rank[r]
    blocks.append((pos,r,endpos))
blocks=sorted(blocks, key=lambda x:x[0])
# determine slice end per block = next block start
parsed=[]
for i,(pos,r,endpos) in enumerate(blocks):
    nxt = blocks[i+1][0] if i+1<len(blocks) else len(seg)
    chunk = seg[endpos:nxt].strip()
    # title is up to score number pattern
    m = re.search(r'(\d+\.\d)\s*分', chunk)
    if not m:
        title = chunk[:30]
        score_raw = None
    else:
        title = chunk[:m.start()].strip()
        score_raw = m.group(1)+' 分'
    # cleanup title: remove trailing action labels like 想看/购票 and misc
    title = re.sub(r'^(\W+)|\s+$','',title)
    # some chunks might include action label at end of title; remove if present
    title = re.sub(r'\s*(想看|购票|预告片\d+个)$','',title).strip()
    parsed.append({'rank':r,'title':title,'score_raw':score_raw})
# Now sort by rank
parsed=sorted(parsed, key=lambda x:x['rank'])
print('found ranks', [p['rank'] for p in parsed])
print(parsed)
out_path=Path('session_output_dir/maoyan_ticket_rating_board_top10_20260204.json')
out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding='utf-8')
print('saved', out_path)
