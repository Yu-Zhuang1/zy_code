import pandas as pd, numpy as np

dates = ["2026-02-02","2026-02-03","2026-02-04","2026-02-05","2026-02-06","2026-02-09","2026-02-10","2026-02-11","2026-02-12","2026-02-13","2026-02-24","2026-02-25","2026-02-26","2026-02-27"]
vol = [16676112,14701877,15412630,21869394,14082884,10758114,7743646,7172675,7965987,8480433,16248756,12924342,11818347,10454020]

df = pd.DataFrame({'date': pd.to_datetime(dates), 'volume': np.array(vol, dtype=float)})
df = df.sort_values('date').reset_index(drop=True)

# last completed session volume
anchor_vol = float(df.iloc[-1].volume)
anchor_date = df.iloc[-1].date.date().isoformat()

# choose rolling window N=10 sessions ending at anchor
N=10
window = df.tail(N).copy()

# Robust dispersion: MAD / median (robust CV-like)
med = float(np.median(window.volume))
mad = float(np.median(np.abs(window.volume - med)))
robust_cv = mad/med if med!=0 else np.nan

# Microtrend: robust slope of log(volume) over session index using Theil-Sen (median of pairwise slopes)
# Use index as 0..N-1 to avoid holiday gap affecting slope.
idx = np.arange(len(window))
logv = np.log(window.volume.values)
slopes=[]
for i in range(len(idx)):
    for j in range(i+1,len(idx)):
        slopes.append((logv[j]-logv[i])/(idx[j]-idx[i]))
sl = float(np.median(slopes))
# convert to per-session multiplicative change (approx): exp(slope)-1
microtrend = float(np.exp(sl)-1)

# Also compute last 5 vs previous 5 median ratio for interpretability
m1 = float(np.median(window.volume.values[-5:]))
m0 = float(np.median(window.volume.values[:5]))
ratio_5v5 = m1/m0 if m0!=0 else np.nan

anchor_vol, anchor_date, med, mad, robust_cv, microtrend, ratio_5v5, window