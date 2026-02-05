from pathlib import Path
import re
p='log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/web/session_output/read_webpage_20260204-141848_b5b70af176.html'
text=Path(p).read_text('utf-8','ignore')
scripts=re.findall(r'<script[^>]*>(.*?)</script>', text, re.S)
large=sorted([s for s in scripts if len(s)>2000], key=len, reverse=True)
print('largest script length', len(large[0]))
js=large[0]
# find potential api endpoints or paths
for needle in ['/asgard/api','/ajax','boardList','boardData','getBoard','boardName','boardTitle','movieList','dataList','boardItems','topList','nation','China','中国','大陆','movie']:
    idx=js.find(needle)
    if idx!=-1:
        print('found', needle, 'at', idx)
# show snippets around '/asgard'
for m in re.finditer(r'/asgard[^\"\']{0,120}', js):
    snippet=js[m.start():m.end()]
    if 'board' in snippet or 'api' in snippet:
        print('snippet', snippet)
        break
# show snippets around 'board' keywords
for m in re.finditer(r'board[^\"\']{0,80}', js):
    if 'board' in js[m.start():m.start()+120] and 'id' in js[m.start():m.start()+120]:
        print('board-related snippet:', js[m.start():m.start()+160])
        break
# See if js contains embedded JSON after 'module.exports=' or 'data:'
for pat in [r'__INITIAL_STATE__', r'initialState', r'\"data\":\{', r'\"board\":\{']:
    if re.search(pat, js):
        print('regex hit', pat)

# Count occurrences of 'movie' 'score'
print('movie count', js.count('movie'))
print('score count', js.count('score'))
print('grade count', js.count('grade'))
