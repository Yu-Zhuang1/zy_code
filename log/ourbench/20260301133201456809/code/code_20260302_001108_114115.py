import datetime, calendar
print(datetime.date(2026,3,2), calendar.day_name[datetime.date(2026,3,2).weekday()])
# also print UTC conversions for SSE session boundaries
from datetime import datetime, timezone, timedelta
cst=timezone(timedelta(hours=8))
for t in ['09:30','11:30','13:00','15:00']:
    h,m=map(int,t.split(':'))
    dt=datetime(2026,3,2,h,m,tzinfo=cst)
    print(t, 'CST', '->', dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
