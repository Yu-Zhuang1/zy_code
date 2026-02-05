from pathlib import Path
import re, json
html_path = Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/browser/session_output_dir/browser_snapshot_20260204-141943_aed56fef15.html')
html = html_path.read_text(encoding='utf-8', errors='ignore')
# Extract visible text similarly and parse ranks 1-10 with title and score
text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.S|re.I)
text = re.sub(r'<[^>]+>', ' ', text)
text = re.sub(r'&nbsp;',' ', text)
text = re.sub(r'\s+',' ', text).strip()
# focus between '看过' and '数据说明'
start = text.find('看过')
end = text.find('数据说明')
seg = text[start:end]
# regex: rank number, space, title, space, score like 9.8 分
pattern = re.compile(r'\b(10|[1-9])\s+([^\d]{2,40}?)\s+(\d+\.\d)\s*分')
items=[]
for m in pattern.finditer(seg):
    rank=int(m.group(1))
    title=m.group(2).strip()
    score=m.group(3).strip()+' 分'
    items.append((rank,title,score))
# dedupe by rank keep first
seen=set(); parsed=[]
for r,t,s in items:
    if r in seen: continue
    seen.add(r)
    parsed.append({'rank':r,'title':t,'score_raw':s})
parsed=sorted(parsed, key=lambda x:x['rank'])
print('parsed', len(parsed))
print(parsed)
# save artifact json
out_path = Path('session_output_dir/maoyan_ticket_rating_board_top10_20260204.json')
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding='utf-8')
print('saved', str(out_path))
