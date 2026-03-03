import pandas as pd, numpy as np
closes=[33.9900016784668,34.9900016784668,35.0099983215332,34.83000183105469,34.61000061035156,34.79999923706055,34.56999969482422,34.29999923706055,34.5099983215332,34.290000915527344,34.880001068115234,35.220001220703125,35.86000061035156,35.54999923706055]
dates=pd.to_datetime(['2026-02-02','2026-02-03','2026-02-04','2026-02-05','2026-02-06','2026-02-09','2026-02-10','2026-02-11','2026-02-12','2026-02-13','2026-02-24','2026-02-25','2026-02-26','2026-02-27'])
df=pd.DataFrame({'close':closes},index=dates)
df['ret']=df['close'].pct_change()
# choose short window=5 trading days ending at anchor date
w=5
last=df.iloc[-w:]
microtrend_mean=float(last['ret'].mean())
microtrend_cum=float(df['close'].iloc[-1]/df['close'].iloc[-w]-1)  # from first of window to last
vol=float(last['ret'].std(ddof=1))
# also compute 10-day alt
w2=10
last2=df.iloc[-w2:]
microtrend_mean10=float(last2['ret'].mean())
microtrend_cum10=float(df['close'].iloc[-1]/df['close'].iloc[-w2]-1)
vol10=float(last2['ret'].std(ddof=1))
(anchor_close:=float(df['close'].iloc[-1]), microtrend_mean, microtrend_cum, vol, microtrend_mean10, microtrend_cum10, vol10)
