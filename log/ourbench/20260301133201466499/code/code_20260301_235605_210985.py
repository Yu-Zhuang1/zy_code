import pandas as pd
path='log/ourbench0301_2/20260301133201466499/finance/session_output_dir/stock_002049_SZ_8c4d1435de_20260301_235508.csv'
df=pd.read_csv(path)
df.rename(columns={df.columns[0]:'Date'} if df.columns[0] != 'Date' else {}, inplace=True)
df['Date']=pd.to_datetime(df['Date'])
df=df.sort_values('Date')
df['vol']=df['Volume'].astype(float)
# identify zero-volume streaks in early 2026
zero=df[df['vol']<=0][['Date','vol']]
print(zero.tail(20).to_string(index=False))
