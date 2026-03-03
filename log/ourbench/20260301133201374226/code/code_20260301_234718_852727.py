import pathlib, re
from bs4 import BeautifulSoup
path = pathlib.Path('log/ourbench0301_2/20260301133201374226/browser/session_output/browser_snapshot_20260301-154658_3a0cc8c396.html')
html = path.read_text(errors='ignore')
soup = BeautifulSoup(html, 'html.parser')
# Find text '02618'
cell = soup.find(string=re.compile(r'\b02618\b'))
print('found', bool(cell))
if cell:
    td = cell.find_parent(['td','th'])
    tr = td.find_parent('tr') if td else None
    if tr:
        cols=[ ' '.join(c.get_text(' ', strip=True).split()) for c in tr.find_all(['td','th'])]
        print('ncols',len(cols))
        print(cols)
# Let's ensure we get correct row for JD LOGISTICS (2618). Find rows containing 'JD LOGISTICS'
cell2 = soup.find(string=re.compile('JD', re.I))
# too broad; search JD LOGISTICS
cell2 = soup.find(string=re.compile('JD LOGISTICS', re.I))
print('found jd', bool(cell2))
if cell2:
    tr=cell2.find_parent('tr')
    cols=[ ' '.join(c.get_text(' ', strip=True).split()) for c in tr.find_all(['td','th'])]
    print(cols)
