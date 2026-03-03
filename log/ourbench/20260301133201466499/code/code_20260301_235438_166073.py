import numpy as np, pandas as pd, math

dates = pd.to_datetime(["2026-02-02","2026-02-03","2026-02-04","2026-02-05","2026-02-06","2026-02-09","2026-02-10","2026-02-11","2026-02-12","2026-02-13","2026-02-24","2026-02-25","2026-02-26","2026-02-27"])
vol = np.array([33307646,21118806,26993092,17751844,16690283,17575942,14852510,12023703,16352958,13679498,16378614,18420215,21159965,15507415], dtype=float)

df = pd.DataFrame({'date':dates,'volume':vol}).sort_values('date').reset_index(drop=True)
# last completed session
anchor = df.iloc[-1]

# choose rolling window last 10 sessions
win = df.tail(10).copy()

# robust dispersion: MAD/median
median = np.median(win.volume)
mad = np.median(np.abs(win.volume - median))
dispersion = mad/median

# robust microtrend: Theil-Sen slope on log(volume) vs index
x = np.arange(len(win))
y = np.log(win.volume.values)
slopes=[]
for i in range(len(x)):
    for j in range(i+1,len(x)):
        slopes.append((y[j]-y[i])/(x[j]-x[i]))
slopes = np.array(slopes)
theil_sen = np.median(slopes)
# Convert to per-session multiplicative change: exp(slope)-1
microtrend = float(np.exp(theil_sen)-1)

# also compute IQR/median as alternative (not returned)
q1,q3 = np.percentile(win.volume,[25,75])
iqr = q3-q1

anchor_dict = {
    'anchor_date': str(anchor.date.date()),
    'anchor_volume': float(anchor.volume),
    'win_start': str(win.date.iloc[0].date()),
    'win_end': str(win.date.iloc[-1].date()),
    'median': float(median),
    'mad': float(mad),
    'dispersion_mad_over_median': float(dispersion),
    'theil_sen_log_slope': float(theil_sen),
    'microtrend_exp_slope_minus1': microtrend,
    'iqr_over_median': float(iqr/median),
    'min_vol': float(win.volume.min()),
    'max_vol': float(win.volume.max()),
}
anchor_dict
