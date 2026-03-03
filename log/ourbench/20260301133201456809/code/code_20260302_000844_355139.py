import numpy as np, pandas as pd

dates = pd.to_datetime(["2026-02-02","2026-02-03","2026-02-04","2026-02-05","2026-02-06","2026-02-09","2026-02-10","2026-02-11","2026-02-12","2026-02-13","2026-02-24","2026-02-25","2026-02-26","2026-02-27"])
vol = np.array([26761180,17769837,18270735,15321163,14825244,18775678,14748181,11744516,11373749,10756697,20089748,27520608,13989226,21386639], dtype=float)

df = pd.DataFrame({'date':dates,'volume':vol}).sort_values('date').reset_index(drop=True)

# Anchor = last session
anchor = float(df.iloc[-1].volume)

# Robust microtrend using Theil-Sen slope on log(volume) over last 10 sessions
window = 10
sub = df.tail(window).copy()
sub['t'] = np.arange(len(sub))
logv = np.log(sub['volume'].values)
t = sub['t'].values

# Theil-Sen: median of pairwise slopes
slopes=[]
for i in range(len(t)):
    for j in range(i+1,len(t)):
        slopes.append((logv[j]-logv[i])/(t[j]-t[i]))
slopes=np.array(slopes)
ts_slope=float(np.median(slopes))
# convert to per-session percent change
microtrend = float(np.exp(ts_slope)-1.0)

# Robust dispersion on same window: MAD/median (and scaled)
med=float(np.median(sub['volume']))
mad=float(np.median(np.abs(sub['volume']-med)))
disp_raw = mad/med if med!=0 else np.nan
# scaled MAD to robust sigma and then CV: (1.4826*MAD)/median
robust_cv = (1.4826*mad)/med if med!=0 else np.nan

anchor, microtrend, disp_raw, robust_cv, sub[['date','volume']]
