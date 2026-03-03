import pandas as pd, numpy as np

dates = pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15", "2026-01-16", "2026-01-19", "2026-01-20", "2026-01-21", "2026-01-22", "2026-01-23", "2026-01-26", "2026-01-27", "2026-01-28", "2026-01-29", "2026-01-30", "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05", "2026-02-06", "2026-02-09", "2026-02-10", "2026-02-11", "2026-02-12", "2026-02-13", "2026-02-24", "2026-02-25", "2026-02-26", "2026-02-27"])
vol = np.array([29743547, 24747603, 43944735, 35087599, 30775737, 23844300, 19980087, 24926671, 18727363, 30941695, 22986419, 23556922, 20350717, 16226405, 22992419, 31199400, 23531617, 47597157, 34395383, 24917260, 26761180, 17769837, 18270735, 15321163, 14825244, 18775678, 14748181, 11744516, 11373749, 10756697, 20089748, 27520608, 13989226, 21386639])

df=pd.DataFrame({'date':dates,'volume':vol})
df['dow']=df['date'].dt.dayofweek
# last 10 volumes
last10=df.tail(10)
last5=df.tail(5)

# trend signal: z-scored log-volume slope over last 20 sessions
last20=df.tail(20).reset_index(drop=True)
x=np.arange(len(last20))
y=np.log(last20['volume'].values)
# slope b
b,_a=np.polyfit(x,y,1)
# approximate SE for b
yhat=b*x+_a
res=y-yhat
s2=np.sum(res**2)/(len(x)-2)
Sxx=np.sum((x-x.mean())**2)
se_b=np.sqrt(s2/Sxx)
trend_t=b/se_b
# map to [-1,1] via tanh
trend_signal=float(np.tanh(trend_t/3))

# seasonal residual: last session normalized residual vs its DOW median
season_median=df.groupby('dow')['volume'].median()
last=df.iloc[-1]
seasonality_residual=float(last['volume']/season_median.loc[last['dow']] - 1)

# scale computed earlier
overall_median=float(df['volume'].median())
mon_factor=float(season_median.loc[0]/overall_median)
trend_scale=float(np.exp(b))
raw_scale=trend_scale*mon_factor
bounded_scale=float(np.clip(raw_scale,0.85,1.15))

# stability metrics
residuals=df.apply(lambda r: r['volume']/season_median.loc[r['dow']] - 1.0, axis=1)
mad=float(np.median(np.abs(residuals-np.median(residuals))))
# stationarity-ish: ratio last10 median to prior10 median
prior10=df.iloc[-20:-10]
ratio=float(np.median(last10['volume'])/np.median(prior10['volume']))

trend_signal, trend_t, b, se_b, seasonality_residual, mon_factor, trend_scale, raw_scale, bounded_scale, mad, ratio, list(last10['volume'].values)
