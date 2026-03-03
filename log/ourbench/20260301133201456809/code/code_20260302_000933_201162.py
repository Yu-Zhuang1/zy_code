import pandas as pd, numpy as np
from sklearn.linear_model import LinearRegression

dates = pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15", "2026-01-16", "2026-01-19", "2026-01-20", "2026-01-21", "2026-01-22", "2026-01-23", "2026-01-26", "2026-01-27", "2026-01-28", "2026-01-29", "2026-01-30", "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05", "2026-02-06", "2026-02-09", "2026-02-10", "2026-02-11", "2026-02-12", "2026-02-13", "2026-02-24", "2026-02-25", "2026-02-26", "2026-02-27"])
vol = np.array([29743547, 24747603, 43944735, 35087599, 30775737, 23844300, 19980087, 24926671, 18727363, 30941695, 22986419, 23556922, 20350717, 16226405, 22992419, 31199400, 23531617, 47597157, 34395383, 24917260, 26761180, 17769837, 18270735, 15321163, 14825244, 18775678, 14748181, 11744516, 11373749, 10756697, 20089748, 27520608, 13989226, 21386639])

df = pd.DataFrame({'date':dates,'volume':vol})
df['dow']=df['date'].dt.dayofweek

df['logv']=np.log(df['volume'])

# Rolling anchor: median of last 20 sessions
last20=df.tail(20).copy()
anchor=float(np.median(last20['volume']))

# Trend: slope of logv over last 20 sessions (per session)
X=np.arange(len(last20)).reshape(-1,1)
y=last20['logv'].values
lr=LinearRegression().fit(X,y)
slope=float(lr.coef_[0])
# expected multiplicative change from last20 start to end is exp(slope*(n-1)). For next session, exp(slope)
trend_scale=float(np.exp(slope))

# Seasonality: DOW median factors from all available sessions (34)
dow_median=df.groupby('dow')['volume'].median()
overall_median=float(df['volume'].median())
seasonality_factor=float(dow_median.loc[0]/overall_median)  # Monday vs overall

# Recent seasonality residual: last session (Fri dow=4) vs its DOW median
last=df.iloc[-1]
fri_med=float(dow_median.loc[4])
seasonality_residual=float(last['volume']/fri_med - 1.0)

# Stability: counts per dow
counts=df['dow'].value_counts().sort_index()

# Combine for next session: trend_scale * seasonality_factor; but avoid overreaction.
raw_scale=trend_scale*seasonality_factor
bounded_scale=float(np.clip(raw_scale, 0.85, 1.15))

# Also compute dispersion of residuals by dow (robust MAD)
# Residuals: vol / dow_median[dow] -1
residuals=df.apply(lambda r: r['volume']/dow_median.loc[r['dow']] - 1.0, axis=1)
mad=float(np.median(np.abs(residuals-np.median(residuals))))

anchor, slope, trend_scale, seasonality_factor, seasonality_residual, raw_scale, bounded_scale, counts.to_dict(), overall_median, mad
