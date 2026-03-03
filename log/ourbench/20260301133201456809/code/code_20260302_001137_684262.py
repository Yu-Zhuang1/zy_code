from datetime import date, datetime, timezone, timedelta
# weekday for 2026-03-02 (Mon=0)
d=date(2026,3,2)
print(d.isoformat(), d.weekday())
# create a helper mapping for SSE day session times in UTC
cst=timezone(timedelta(hours=8))
for label,h,m in [('open',9,30),('break_start',11,30),('break_end',13,0),('close',15,0)]:
    dt=datetime(2026,3,2,h,m,tzinfo=cst)
    print(label, dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M'))
