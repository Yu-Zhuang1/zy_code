import pathlib, re
p=pathlib.Path('log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/web/session_output/read_webpage_20260204-141848_b5b70af176.html')
html=p.read_text('utf-8', errors='ignore')
print('size', len(html))
# extract AppData JSON
m=re.search(r'var\s+AppData\s*=\s*(\{.*?\});', html, flags=re.S)
print('AppData found', bool(m))
if m:
    app=m.group(1)
    print(app[:600])
    # find endpoints hints in AppData
    for kw in ['api','host','bangdan','board','id','year','movie','list']:
        print(kw, app.count(kw))
# find 'board' in full html in context
for kw in ['board','bangdan','api','boardId','movieList','dataList','items']:
    print(kw, html.count(kw))
