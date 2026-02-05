from pathlib import Path
import re
p='log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/web/session_output/read_webpage_20260204-141848_b5b70af176.html'
text=Path(p).read_text('utf-8','ignore')
# find all URL paths containing ajax or api
cands=set(re.findall(r'(?:https?:)?//[^\s"\']+|/[^\s"\']+)', text))
interesting=[]
for u in cands:
    if any(k in u for k in ['ajax','api','board','rank','asgard']):
        if len(u)<200:
            interesting.append(u)
interesting=sorted(set(interesting))
print('interesting count', len(interesting))
for u in interesting[:80]:
    print(u)
# find occurrences of 'score' and context
for m in re.finditer('score', text):
    if m.start()<0: break
print('total score occurrences', len(list(re.finditer('score', text))))
# Look for JSON-like arrays 'movieList' or 'list'
for token in ['movieList','boardList','boardData','dataList','listData','rankList','scoreList','boardItems']:
    if token in text:
        print('token present', token)
# Show small context around 'score'
for m in re.finditer('score', text):
    start=max(0,m.start()-80); end=min(len(text), m.start()+120)
    ctx=text[start:end]
    if 'movie' in ctx or 'board' in ctx:
        print('ctx:', ctx.replace('\n',' ')[:200])
        break
