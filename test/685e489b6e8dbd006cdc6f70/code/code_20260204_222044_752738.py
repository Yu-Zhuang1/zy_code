from pathlib import Path
import re, json
html_path = Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-141943_aed56fef15.html')
html = html_path.read_text(encoding='utf-8', errors='ignore')
text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.S|re.I)
text = re.sub(r'<[^>]+>', ' ', text)
text = re.sub(r'&nbsp;',' ', text)
text = re.sub(r'\s+',' ', text).strip()
start = text.find('看过')
end = text.find('数据说明')
seg = text[start:end]
# More permissive pattern: rank + title (anything) + score
pattern = re.compile(r'\b(10|[1-9])\s+(.+?)\s+(\d+\.\d)\s*分')
items=[]
for m in pattern.finditer(seg):
    rank=int(m.group(1))
    title=m.group(2).strip()
    score=m.group(3).strip()+' 分'
    items.append((rank,title,score,m.start()))
# keep first occurrence per rank, but also clean title by trimming trailing genres if any? Actually title should be immediate string.
# In seg, after score comes genres; regex stops at score, so title should be correct.
seen=set(); parsed=[]
for r,t,s,idx in items:
    if r in seen: continue
    seen.add(r)
    parsed.append({'rank':r,'title':t,'score_raw':s,'_pos':idx})
parsed=sorted(parsed, key=lambda x:x['rank'])
for p in parsed:
    p.pop('_pos',None)
print('parsed', len(parsed))
print(parsed)
out_path = Path('session_output_dir/maoyan_ticket_rating_board_top10_20260204.json')
out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding='utf-8')
print('saved', str(out_path))
