from lxml import html as lhtml
import pathlib, re
path = pathlib.Path('log/ourbench0301_2/20260301133201374226/browser/session_output/browser_snapshot_20260301-154658_3a0cc8c396.html')
text = path.read_text(errors='ignore')
doc = lhtml.fromstring(text)
# find elements containing '02618'
els = doc.xpath("//*[contains(text(),'02618')]")
print('num els', len(els))
for e in els[:20]:
    s = ' '.join(e.text_content().split())
    print(s[:200])
# attempt to get parent tr for first occurrence
if els:
    tr = els[0].xpath('ancestor::tr[1]')
    if tr:
        row = [' '.join(td.text_content().split()) for td in tr[0].xpath('./td|./th')]
        print('row cols', len(row))
        print(row)
