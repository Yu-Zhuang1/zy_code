import pandas as pd, numpy as np

dates = ["2026-01-15", "2026-01-16", "2026-01-19", "2026-01-20", "2026-01-21", "2026-01-22", "2026-01-23", "2026-01-26", "2026-01-27", "2026-01-28", "2026-01-29", "2026-01-30", "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05", "2026-02-06", "2026-02-09", "2026-02-10", "2026-02-11", "2026-02-12", "2026-02-13", "2026-02-16", "2026-02-20", "2026-02-23", "2026-02-24", "2026-02-25", "2026-02-26", "2026-02-27"]
close = [67.9000015258789, 67.19999694824219, 66.0999984741211, 66.5999984741211, 66.80000305175781, 64.8499984741211, 63.79999923706055, 64.4000015258789, 64.25, 65.4000015258789, 63.29999923706055, 63.25, 60.95000076293945, 60.29999923706055, 60.650001525878906, 60.650001525878906, 59.150001525878906, 61.45000076293945, 60.25, 61.099998474121094, 60.0, 60.29999923706055, 60.650001525878906, 56.849998474121094, 58.150001525878906, 56.900001525878906, 56.70000076293945, 56.45000076293945, 56.75]
volume = [12752909, 7946609, 5704055, 5458727, 6663411, 6077406, 5427578, 5750976, 6071493, 6379154, 8256878, 5890753, 6690818, 8942658, 6673065, 6212387, 6475693, 5282853, 4257248, 3359205, 3724164, 4830708, 0, 5897448, 4469003, 7700415, 6626191, 10192680, 6079063]

df = pd.DataFrame({'date': pd.to_datetime(dates), 'close': close, 'volume': volume}).set_index('date').sort_index()
# Filter to presumed actual trading days (volume>0)
df_tr = df[df.volume>0].copy()
# daily simple returns
rets = df_tr.close.pct_change().dropna()

# last verified close
anchor_date = df_tr.index.max()
anchor_close = float(df_tr.loc[anchor_date,'close'])

# compute microtrend and vol over last 10 trading sessions ending anchor
window_n = 10
last_n = df_tr.tail(window_n)
rets_n = last_n.close.pct_change().dropna()
microtrend_mean_daily = float(rets_n.mean())
vol_std_daily = float(rets_n.std(ddof=1))
# also cumulative over window for reference
microtrend_cum = float(last_n.close.iloc[-1]/last_n.close.iloc[0]-1)

# last 5 sessions too
last_5 = df_tr.tail(5)
rets_5 = last_5.close.pct_change().dropna()
microtrend5_mean_daily = float(rets_5.mean())
vol5_std_daily = float(rets_5.std(ddof=1))
microtrend5_cum = float(last_5.close.iloc[-1]/last_5.close.iloc[0]-1)

(anchor_date, anchor_close, microtrend_mean_daily, vol_std_daily, microtrend_cum, microtrend5_mean_daily, vol5_std_daily, microtrend5_cum, df_tr.tail(12))