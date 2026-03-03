import numpy as np, pandas as pd, math

dates = ["2026-02-02","2026-02-03","2026-02-04","2026-02-05","2026-02-06","2026-02-09","2026-02-10","2026-02-11","2026-02-12","2026-02-13","2026-02-16","2026-02-20","2026-02-23","2026-02-24","2026-02-25","2026-02-26","2026-02-27"]
vol = [1099564,869587,1357373,1476268,1077430,1050224,1256370,587334,1307026,858803,0,976930,934481,1127429,1737999,2180294,1301463]

df = pd.DataFrame({'date': pd.to_datetime(dates), 'volume': vol}).sort_values('date')
# find the last nonzero volume
last_nonzero_row = df[df['volume']>0].iloc[-1]
last_any_row = df.iloc[-1]
last_nonzero_row, last_any_row
