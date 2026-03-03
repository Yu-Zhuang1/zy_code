import pandas as pd, numpy as np
from scipy.stats import median_abs_deviation

v = globals().get('v')
# ensure timezone removed for weekday computations
v2=v.copy()
v2['Date']=pd.to_datetime(v2['Date']).dt.tz_convert(None)
v2['weekday']=v2['Date'].dt.weekday
v2=v2.sort_values('Date')

# define recent windows
recent_lookback=90
trend_lookback=20
resid_lookback=5

recent=v2.tail(recent_lookback).copy()
# weekday baseline median over recent window
weekday_median=recent.groupby('weekday')['Volume'].median()
weekday_mad=recent.groupby('weekday')['Volume'].apply(lambda x: median_abs_deviation(x, scale='normal'))

# anchor for next session Monday (0)
anchor=weekday_median.get(0, recent['Volume'].median())

# compute seasonality residual for last session(s)
recent['baseline']=recent['weekday'].map(weekday_median)
recent['resid_ratio']=recent['Volume']/recent['baseline']
recent['log_resid']=np.log(recent['resid_ratio'])

last=resid=recent.tail(resid_lookback)
seasonality_residual=float(np.mean(last['log_resid'])) # positive => above baseline

# trend: slope of log(volume) over last trend_lookback
trend_window=v2.tail(trend_lookback).copy()
trend_window['t']=np.arange(len(trend_window))
trend_window['logv']=np.log(trend_window['Volume'])
# robust slope via simple OLS (small); use np.polyfit
slope=np.polyfit(trend_window['t'], trend_window['logv'], 1)[0]
# convert slope to 1-day multiplicative effect exp(slope)
trend_signal=float(slope)  # per day log-change

# quality: check outliers using MAD on log_resid in recent window
mad=float(median_abs_deviation(recent['log_resid'], scale='normal'))
std=float(np.std(recent['log_resid']))

# bounded update scale: combine recent residual and trend into 1-step forecast
# base effect = exp(trend_signal + seasonality_residual*0.5) with weights
# shrink if noisy: weight = 1/(1+ (mad/0.3)^2)
noise_scale=0.3
w=1/(1+(mad/noise_scale)**2) if mad>0 else 1
# cap w between 0.2 and 1
w=float(np.clip(w,0.2,1.0))
raw_scale=np.exp(w*(trend_signal + 0.7*seasonality_residual))
# clip scale to [0.75,1.25]
bounded_update_scale=float(np.clip(raw_scale,0.75,1.25))

# Prepare some descriptive stats
out={
 'last_date': str(v2['Date'].max().date()),
 'anchor_monday_median': float(anchor),
 'weekday_median': weekday_median.to_dict(),
 'seasonality_residual_log_mean_last5': seasonality_residual,
 'trend_slope_log_per_day_last20': trend_signal,
 'mad_log_resid_recent90': mad,
 'w': w,
 'raw_scale': float(raw_scale),
 'bounded_update_scale': bounded_update_scale,
 'last5': last[['Date','Volume','weekday','baseline','resid_ratio','log_resid']].to_dict('records'),
 'last20_vol_mean': float(trend_window['Volume'].mean()),
 'last20_vol_median': float(trend_window['Volume'].median()),
}
out
