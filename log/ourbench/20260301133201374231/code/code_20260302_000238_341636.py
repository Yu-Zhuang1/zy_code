import datetime as dt
for d in ['2026-03-01','2026-03-02','2026-02-27','2026-02-28']:
    dd=dt.date.fromisoformat(d)
    print(d, dd.strftime('%A'))
