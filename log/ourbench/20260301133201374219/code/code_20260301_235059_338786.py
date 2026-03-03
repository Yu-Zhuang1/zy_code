import pandas as pd, numpy as np
path='log/ourbench0301_2/20260301133201374219/finance/session_output_dir/stock_0316_HK_d95fa0f555_20260301_235052.csv'
df=pd.read_csv(path)
# yfinance csv likely has Date column
if 'Date' in df.columns:
    df['Date']=pd.to_datetime(df['Date'])
else:
    # maybe unnamed
    df.iloc[:,0]=pd.to_datetime(df.iloc[:,0])
    df=df.rename(columns={df.columns[0]:'Date'})
df=df.sort_values('Date')
# keep only Volume and Date
v=df[['Date','Volume']].copy()
# remove zeros/na
v=v.dropna()
v=v[v['Volume']>0]
# restrict to recent window: last 120 trading days up to resolve date 2026-03-01 (non-trading day?); last date should be 2026-02-27? check
last_date=v['Date'].max()
last_date
