import re, pathlib
path = pathlib.Path('log/galaxy_futurex_0204/685e4893e582f0005f9cd2c8/web/session_output_dir/read_webpage_20260204-140432_f49b9157d3.html')
html = path.read_text(encoding='utf-8', errors='ignore')
# Search for 'boardList' or 'movieList' keywords
for kw in ['boardList','movieList','wish','wishCount','name\":\"飞驰人生3','top10','boardInfos','rank','movieId','id']:
    print(kw, '->', html.find(kw))
