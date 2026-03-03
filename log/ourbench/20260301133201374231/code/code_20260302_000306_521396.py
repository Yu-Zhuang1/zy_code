import pandas as pd, numpy as np, json, math
# Reconstruct from tool output? We'll hardcode by reading from previous variable not available. We'll paste volumes/dates from get_stock_data output.
dates = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15", "2026-01-16", "2026-01-19", "2026-01-20", "2026-01-21", "2026-01-22", "2026-01-23", "2026-01-26", "2026-01-27", "2026-01-28", "2026-01-29", "2026-01-30", "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05", "2026-02-06", "2026-02-09", "2026-02-10", "2026-02-11", "2026-02-12", "2026-02-13", "2026-02-16", "2026-02-20", "2026-02-23", "2026-02-24", "2026-02-25", "2026-02-26", "2026-02-27"]
vol = [3327505, 3594021, 4129132, 2363127, 3460506, 3294871, 4194714, 4980276, 6517572, 5961490, 4090744, 4838241, 9063614, 13195286, 5033827, 12333717, 9301034, 6221307, 9950118, 5170688, 8603164, 10585769, 12140885, 8488296, 6664099, 13186537, 9713451, 7640423, 5796593, 5341996, 5294995, 0, 4815441, 4235927, 6558767, 6103163, 5348413, 10097740]

df = pd.DataFrame({'date': pd.to_datetime(dates), 'volume': vol})
# remove non-trading sessions with 0 volume
valid = df[df.volume>0].copy()
valid['dow'] = valid.date.dt.dayofweek # Monday=0
# anchor: median of last 20 valid sessions
anchor_window = valid.tail(20)
anchor = anchor_window.volume.median()
# trend: compare last 5 vs prior 20 (excluding last 5)
last5 = valid.tail(5).volume
prev20 = valid.iloc[-25:-5].volume
trend_ratio = last5.median()/prev20.median()
trend_signal = float(np.log(trend_ratio))
# also compute robust slope of log(volume) over last 20 sessions
from sklearn.linear_model import HuberRegressor
X = np.arange(len(anchor_window)).reshape(-1,1)
y = np.log(anchor_window.volume.values)
huber = HuberRegressor().fit(X,y)
slope = float(huber.coef_[0])
# convert slope to per-day multiplicative trend over 1 day: exp(slope)
trend_day_mult = math.exp(slope)
# seasonality: weekday effect for Monday relative to overall, using last 8 weeks (~40 sessions) of valid
season_window = valid.copy()  # 37 valid sessions here
overall_med = season_window.volume.median()
mon_med = season_window[season_window.dow==0].volume.median()
seasonality_ratio = mon_med/overall_med
seasonality_residual = float(np.log(seasonality_ratio))
# expected multiplier for next Monday relative to anchor: use seasonality_ratio * near-term trend extrap 1 session
raw_mult = seasonality_ratio * trend_day_mult
# bound multiplier to [0.8, 1.2] maybe; but choose symmetric clip [0.75,1.25] based on skill.
bounded = float(np.clip(raw_mult, 0.8, 1.2))
# diagnostics: volatility
cv = float(anchor_window.volume.std()/anchor_window.volume.mean())
trend_info = dict(anchor=anchor, trend_ratio=trend_ratio, slope=slope, trend_day_mult=trend_day_mult,
                  seasonality_ratio=seasonality_ratio, raw_mult=raw_mult, bounded=bounded, cv=cv,
                  counts_by_dow=season_window.dow.value_counts().to_dict())
trend_info