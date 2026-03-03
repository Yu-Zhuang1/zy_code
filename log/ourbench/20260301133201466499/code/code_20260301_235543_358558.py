import pandas as pd, numpy as np
path='log/ourbench0301_2/20260301133201466499/finance/session_output_dir/stock_002049_SZ_8c4d1435de_20260301_235508.csv'
df=pd.read_csv(path)
# Standardize columns
# yfinance csv likely has Date column named 'Date'
if 'Date' in df.columns:
    df['Date']=pd.to_datetime(df['Date'])
    df=df.sort_values('Date')
else:
    # first column maybe unnamed
    df.rename(columns={df.columns[0]:'Date'}, inplace=True)
    df['Date']=pd.to_datetime(df['Date'])
    df=df.sort_values('Date')

# keep needed
vol=df['Volume'].astype(float)
df['vol']=vol
# mark valid trade days as vol>0
valid=df[df['vol']>0].copy()
valid['logv']=np.log(valid['vol'])
valid['weekday']=valid['Date'].dt.weekday # Mon=0

# parameters
baseline_n=120
recent_n=5
prev_n=20

# take last baseline_n valid sessions ending at last available date
valid_tail=valid.tail(baseline_n).copy()

# weekday means on baseline
weekday_means=valid_tail.groupby('weekday')['logv'].mean()
overall_mean=valid_tail['logv'].mean()

# compute residuals for baseline window using weekday mean
valid_tail['resid']=valid_tail.apply(lambda r: r['logv']-weekday_means.loc[r['weekday']], axis=1)
resid_std=valid_tail['resid'].std(ddof=1)

# last session info
last_row=valid_tail.iloc[-1]
last_date=last_row['Date']
last_weekday=int(last_row['weekday'])
last_resid=float(last_row['resid'])
last_resid_z=float(last_resid/resid_std) if resid_std>0 else 0.0

# trend: mean resid last recent_n vs previous prev_n (before last recent_n)
recent=valid_tail.tail(recent_n)
prev=valid_tail.iloc[-(recent_n+prev_n):-recent_n] if len(valid_tail)>=recent_n+prev_n else valid_tail.iloc[:0]
trend_raw=float(recent['resid'].mean()-prev['resid'].mean()) if len(prev)>0 else 0.0
trend_z=float(trend_raw/resid_std) if resid_std>0 else 0.0

# expected seasonal effect for target date 2026-03-02 (Monday)
target_date=pd.Timestamp('2026-03-02')
target_weekday=int(target_date.weekday())
# If weekday mean missing (rare), fallback overall_mean
wmean=float(weekday_means.get(target_weekday, overall_mean))
seasonal_effect_log=wmean-overall_mean
seasonal_factor=float(np.exp(seasonal_effect_log))

# Quality adjustments: count valid sessions and recent zero-volume suspensions
n_valid=len(valid)
# count zero-volume days in last 60 calendar rows
last60=df.tail(60)
zero_recent=int((last60['Volume']<=0).sum())
# days since last zero-volume day
zero_dates=df.loc[df['Volume']<=0, 'Date']
days_since_zero=(df['Date'].max()-zero_dates.max()).days if len(zero_dates)>0 else 999

# quality weight
w=min(1.0, len(valid_tail)/baseline_n)
# penalty if any zero-volume within last 90 calendar days
if days_since_zero<90:
    w*=0.7

# combine into scale: start from seasonal_factor then apply exp on z terms (small)
raw_scale=seasonal_factor*np.exp(0.08*trend_z + 0.05*last_resid_z)
# shrink toward 1 by w
shrunk_scale=1 + w*(raw_scale-1)
# clip
bounded=float(np.clip(shrunk_scale, 0.85, 1.15))

out={
    'last_date': str(last_date.date()),
    'last_weekday': last_weekday,
    'target_weekday': target_weekday,
    'resid_std': float(resid_std),
    'last_resid_log': last_resid,
    'last_resid_z': last_resid_z,
    'trend_raw_log': trend_raw,
    'trend_z': trend_z,
    'seasonal_effect_log': float(seasonal_effect_log),
    'seasonal_factor': seasonal_factor,
    'raw_scale': raw_scale,
    'w_quality': w,
    'bounded_scale': bounded,
    'n_valid_total': n_valid,
    'zero_recent_60': zero_recent,
    'days_since_last_zero': days_since_zero,
}
print(out)
