import pandas as pd, numpy as np, math
from scipy.stats import theilslopes

dates = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15", "2026-01-16", "2026-01-19", "2026-01-20", "2026-01-21", "2026-01-22", "2026-01-23", "2026-01-26", "2026-01-27", "2026-01-28", "2026-01-29", "2026-01-30", "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05", "2026-02-06", "2026-02-09", "2026-02-10", "2026-02-11", "2026-02-12", "2026-02-13", "2026-02-16", "2026-02-20", "2026-02-23", "2026-02-24", "2026-02-25", "2026-02-26", "2026-02-27"]
vol = [3327505, 3594021, 4129132, 2363127, 3460506, 3294871, 4194714, 4980276, 6517572, 5961490, 4090744, 4838241, 9063614, 13195286, 5033827, 12333717, 9301034, 6221307, 9950118, 5170688, 8603164, 10585769, 12140885, 8488296, 6664099, 13186537, 9713451, 7640423, 5796593, 5341996, 5294995, 0, 4815441, 4235927, 6558767, 6103163, 5348413, 10097740]

df = pd.DataFrame({'date': pd.to_datetime(dates), 'volume': vol})
valid = df[df.volume>0].copy()
valid['dow'] = valid.date.dt.dayofweek
# anchor as median of last 20 sessions
anchor_window = valid.tail(20)
anchor = float(anchor_window.volume.median())
# trend compare last 5 vs previous 20 (excluding last 5)
last5 = valid.tail(5).volume
prev20 = valid.iloc[-25:-5].volume
trend_ratio = float(last5.median()/prev20.median())
trend_signal = float(np.log(trend_ratio))
# theil-sen slope on log volume last 20
x = np.arange(len(anchor_window))
y = np.log(anchor_window.volume.values)
slope, intercept, lo, hi = theilslopes(y, x)
trend_day_mult = float(math.exp(slope))
# Seasonality: Monday effect on last 40-ish sessions (here 37)
season_window = valid.copy()
overall_med = float(season_window.volume.median())
mon = season_window[season_window.dow==0].volume
mon_med = float(mon.median()) if len(mon)>0 else overall_med
seasonality_ratio = float(mon_med/overall_med)
seasonality_residual = float(np.log(seasonality_ratio))
# Combine: expected relative to anchor for next session (Monday 2026-03-02)
raw_mult = float(seasonality_ratio * trend_day_mult)
bounded_update_scale = float(np.clip(raw_mult, 0.85, 1.15))
# Stability: coefficient of variation of last 20
cv = float(anchor_window.volume.std(ddof=1)/anchor_window.volume.mean())
# outlier check: max/median last 20
outlier_ratio = float(anchor_window.volume.max()/anchor)
result = {
 'anchor_median_20': anchor,
 'trend_ratio_last5_vs_prev20': trend_ratio,
 'trend_signal_log_ratio': trend_signal,
 'theil_sen_slope_logvol_per_session': float(slope),
 'trend_day_mult': trend_day_mult,
 'monday_median': mon_med,
 'overall_median': overall_med,
 'seasonality_ratio_mon_vs_all': seasonality_ratio,
 'seasonality_residual_log': seasonality_residual,
 'raw_mult': raw_mult,
 'bounded_update_scale': bounded_update_scale,
 'last20_cv': cv,
 'last20_max_over_median': outlier_ratio,
 'dow_counts': season_window.dow.value_counts().to_dict(),
 'n_valid': int(len(valid))
}
result