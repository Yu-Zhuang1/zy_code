import numpy as np, pandas as pd, math

dates = ["2026-02-02","2026-02-03","2026-02-04","2026-02-05","2026-02-06","2026-02-09","2026-02-10","2026-02-11","2026-02-12","2026-02-13","2026-02-16","2026-02-20","2026-02-23","2026-02-24","2026-02-25","2026-02-26","2026-02-27"]
vol = [1099564,869587,1357373,1476268,1077430,1050224,1256370,587334,1307026,858803,0,976930,934481,1127429,1737999,2180294,1301463]

df = pd.DataFrame({'date': pd.to_datetime(dates), 'volume': vol}).sort_values('date')
# mark zero volumes as missing for robust stats
vol_nonzero = df['volume'].replace(0, np.nan)

def theil_sen_slope(x, y):
    # x, y arrays with no nan
    n = len(x)
    slopes = []
    for i in range(n):
        for j in range(i+1, n):
            if x[j] != x[i]:
                slopes.append((y[j]-y[i])/(x[j]-x[i]))
    return float(np.median(slopes)) if slopes else float('nan')

# choose window = last 10 available sessions ending last date
last_date = df['date'].iloc[-1]
# Use last 10 rows including potential NaN but will drop NaN for slope/dispersion
window_n = 10
w = df.tail(window_n).copy()
wnz = w['volume'].replace(0, np.nan).dropna()
# slope on log volume
w_valid = w.copy()
w_valid['volume'] = w_valid['volume'].replace(0, np.nan)
w_valid = w_valid.dropna()
# x index 0..k-1
x = np.arange(len(w_valid), dtype=float)
y = np.log(w_valid['volume'].astype(float).values)

slope = theil_sen_slope(x, y)
# per-session multiplicative trend
microtrend = math.exp(slope) - 1 if not math.isnan(slope) else float('nan')

# dispersion: robust MAD of log volume; convert to multiplicative cv approx
med = np.nanmedian(np.log(wnz.values))
mad = np.nanmedian(np.abs(np.log(wnz.values) - med))
# scale mad to sigma for normal (1.4826) then convert to multiplicative dispersion (approx exp(sigma)-1)
sigma = 1.4826 * mad
multiplicative_disp = math.exp(sigma) - 1

# also compute IQR/median on raw volume for interpretability
q1, q3 = np.nanpercentile(wnz.values, [25,75])
iqr = q3 - q1
raw_med = np.nanmedian(wnz.values)
iqr_over_med = iqr/raw_med

out = {
    'last_date': str(last_date.date()),
    'anchor_volume': float(df['volume'].iloc[-1]),
    'window_dates': [str(d.date()) for d in w['date']],
    'window_volumes': w['volume'].tolist(),
    'valid_points': int(len(wnz)),
    'microtrend_per_session': microtrend,
    'log_mad': mad,
    'log_sigma': sigma,
    'multiplicative_dispersion': multiplicative_disp,
    'raw_median': float(raw_med),
    'iqr_over_median': float(iqr_over_med),
    'contains_zero': bool((w['volume']==0).any())
}
out
