import pandas as pd, numpy as np
path='log/ourbench0301_2/20260301133201466499/finance/session_output_dir/stock_002049_SZ_8c4d1435de_20260301_235508.csv'
df=pd.read_csv(path)
df.rename(columns={df.columns[0]:'Date'} if df.columns[0] != 'Date' else {}, inplace=True)
df['Date']=pd.to_datetime(df['Date'])
df=df.sort_values('Date')
df['vol']=df['Volume'].astype(float)
valid=df[df['vol']>0].copy()
valid['logv']=np.log(valid['vol'])
valid['weekday']=valid['Date'].dt.weekday
baseline_n=120
valid_tail=valid.tail(baseline_n).copy()
weekday_means=valid_tail.groupby('weekday')['logv'].mean()
valid_tail['resid']=valid_tail.apply(lambda r: r['logv']-weekday_means.loc[r['weekday']], axis=1)
resid_std=valid_tail['resid'].std(ddof=1)
# recent residual average and z
recent_n=5
recent=valid_tail.tail(recent_n)
season_resid=float(recent['resid'].mean())
season_resid_z=float(season_resid/resid_std)

# stability: compute autocorr of resid and std ratio recent vs baseline
recent_std=float(recent['resid'].std(ddof=1))
base_std=float(valid_tail['resid'].std(ddof=1))
std_ratio=recent_std/base_std if base_std>0 else np.nan
acf1=recent['resid'].autocorr(lag=1)

# show last 10 volumes
last10=valid.tail(10)[['Date','Volume']].copy()
print('season_resid_z',season_resid_z,'std_ratio',std_ratio,'acf1',acf1)
print(last10.to_string(index=False))
