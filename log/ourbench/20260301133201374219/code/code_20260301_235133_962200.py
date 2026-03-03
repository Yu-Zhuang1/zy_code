import pandas as pd, numpy as np
from scipy.stats import median_abs_deviation

path='log/ourbench0301_2/20260301133201374219/finance/session_output_dir/stock_0316_HK_d95fa0f555_20260301_235052.csv'
df=pd.read_csv(path)
df['Date']=pd.to_datetime(df['Date'])
df=df.sort_values('Date')
# If Date has timezone info, keep; else localize to HK? Here shows +08 already.
# Ensure Volume numeric
v=df[['Date','Volume']].dropna()
v=v[v['Volume']>0]

# compute weekday from Date in its tz
v['weekday']=v['Date'].dt.weekday

recent_lookback=90
trend_lookback=20
resid_lookback=5
recent=v.tail(recent_lookback).copy()
weekday_median=recent.groupby('weekday')['Volume'].median()

recent['baseline']=recent['weekday'].map(weekday_median)
recent['resid_ratio']=recent['Volume']/recent['baseline']
recent['log_resid']=np.log(recent['resid_ratio'])
last5=recent.tail(resid_lookback).copy()
seasonality_residual=float(last5['log_resid'].mean())

trend_window=v.tail(trend_lookback).copy()
trend_window=trend_window.sort_values('Date')
trend_window['t']=np.arange(len(trend_window))
trend_window['logv']=np.log(trend_window['Volume'])
trend_signal=float(np.polyfit(trend_window['t'], trend_window['logv'], 1)[0])

mad=float(median_abs_deviation(recent['log_resid'], scale='normal'))
noise_scale=0.3
w=1/(1+(mad/noise_scale)**2) if mad>0 else 1
w=float(np.clip(w,0.2,1.0))
raw_scale=float(np.exp(w*(trend_signal + 0.7*seasonality_residual)))
bounded=float(np.clip(raw_scale,0.75,1.25))

(last5[['Date','weekday','Volume','baseline','resid_ratio','log_resid']], v['Date'].max(), weekday_median.to_dict(), trend_signal, seasonality_residual, mad, w, raw_scale, bounded)
