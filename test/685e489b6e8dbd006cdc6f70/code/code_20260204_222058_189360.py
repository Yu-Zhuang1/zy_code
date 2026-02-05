import re, pathlib, json
path='log/galaxy_futurex_0204/685e489b6e8dbd006cdc6f70/web/session_output_dir/read_webpage_20260204-142051_8c13f0e187.html'
text=pathlib.Path(path).read_text('utf-8', errors='ignore')
# find url-like strings
candidates=set(re.findall(r"https?://[^\"'\s>]+", text))
# also find relative endpoints containing 'dashboard' or 'api'
rel=set(re.findall(r"/[^\"'\s>]{1,120}", text))
rel2=[r for r in rel if any(k in r for k in ['api','dashboard','boxOffice','getDaily','movie','query','ajax','second.json','promovie'])]
# keep short unique
rel2=sorted(rel2, key=len)[:200]
list(candidates)[:20], len(candidates), rel2[:50]