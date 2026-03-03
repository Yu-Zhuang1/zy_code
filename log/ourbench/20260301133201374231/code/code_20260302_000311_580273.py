import numpy as np, pandas as pd

dates = pd.to_datetime(["2026-02-02","2026-02-03","2026-02-04","2026-02-05","2026-02-06","2026-02-09","2026-02-10","2026-02-11","2026-02-12","2026-02-13","2026-02-16","2026-02-20","2026-02-23","2026-02-24","2026-02-25","2026-02-26","2026-02-27"])
vol = np.array([10585769,12140885,8488296,6664099,13186537,9713451,7640423,5796593,5341996,5294995,0,4815441,4235927,6558767,6103163,5348413,10097740], dtype=float)

df = pd.DataFrame({'date':dates,'volume':vol}).set_index('date')
# remove zero or nan volumes
s = df['volume'].replace(0,np.nan).dropna()
# define window last 10 sessions ending at last date
window = 10
s_win = s.iloc[-window:]
# anchor is last value
anchor = float(s.iloc[-1])

# robust microtrend: Theil-Sen slope on log(volume) vs session index
x = np.arange(len(s_win), dtype=float)
y = np.log(s_win.values)
# compute pairwise slopes
slopes=[]
for i in range(len(x)):
    for j in range(i+1,len(x)):
        slopes.append((y[j]-y[i])/(x[j]-x[i]))
slopes=np.array(slopes)
ts_slope=float(np.median(slopes)) # per session log change
microtrend = ts_slope

# robust dispersion: MAD of log volumes around median, also provide linear approx
med = float(np.median(y))
mad = float(np.median(np.abs(y-med)))
# convert to multiplicative factor: exp(mad) ~ typical factor from median
mult_disp = float(np.exp(mad)-1.0)

out = {
 'anchor_volume_shares': anchor,
 'microtrend_log_per_session': microtrend,
 'microtrend_pct_per_session': float(np.exp(microtrend)-1.0),
 'dispersion_mad_log': mad,
 'dispersion_mult_minus1': mult_disp,
 'window_start': str(s_win.index[0].date()),
 'window_end': str(s_win.index[-1].date()),
 'window_n': int(len(s_win)),
 'window_volumes': s_win.to_dict()
}
print(out)
