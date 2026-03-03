import pandas as pd, numpy as np

dates = ["2026-01-05","2026-01-06","2026-01-07","2026-01-08","2026-01-09","2026-01-12","2026-01-13","2026-01-14","2026-01-15","2026-01-16","2026-01-19","2026-01-20","2026-01-21","2026-01-22","2026-01-23","2026-01-26","2026-01-27","2026-01-28","2026-01-29","2026-01-30","2026-02-02","2026-02-03","2026-02-04","2026-02-05","2026-02-06","2026-02-09","2026-02-10","2026-02-11","2026-02-12","2026-02-13","2026-02-24","2026-02-25","2026-02-26","2026-02-27"]
close = [87.12999725341797,87.11000061035156,88.23999786376953,88.7300033569336,87.0,86.37000274658203,84.8499984741211,83.69999694824219,85.0999984741211,85.18000030517578,85.8499984741211,84.7300033569336,85.30999755859375,87.0999984741211,88.5199966430664,93.93000030517578,94.3499984741211,90.5,86.36000061035156,83.97000122070312,83.20999908447266,88.4000015258789,90.3499984741211,86.54000091552734,87.06999969482422,93.13999938964844,95.22000122070312,96.5999984741211,96.69999694824219,94.5999984741211,92.2699966430664,98.45999908447266,98.33000183105469,104.5]

df = pd.DataFrame({'date': pd.to_datetime(dates), 'close': close}).set_index('date')
df['ret'] = df['close'].pct_change()
df['logret'] = np.log(df['close']).diff()

anchor_close = float(df['close'].iloc[-1])
last_date = df.index[-1]

# last 5 sessions
last5 = df.tail(5)
# cumulative return over last 5 closes (4 returns)
microtrend_return_5sess = float(last5['close'].iloc[-1]/last5['close'].iloc[0]-1)
# mean daily return over last 5 sessions (4 returns)
mean_ret_5sess = float(last5['ret'].iloc[1:].mean())

# realized vol: std of log returns, annualization not needed, one-session sigma
sigma_log_5sess = float(last5['logret'].iloc[1:].std(ddof=1))
sigma_pct_5sess = float(last5['ret'].iloc[1:].std(ddof=1))

# also compute 10-session vol
last10 = df.tail(10)
sigma_log_10 = float(last10['logret'].iloc[1:].std(ddof=1))
sigma_pct_10 = float(last10['ret'].iloc[1:].std(ddof=1))

# envelope 1-sigma (percentage) using 10-session, and 2-sigma as reference
env1_lo = anchor_close * (1 - sigma_log_10)
env1_hi = anchor_close * (1 + sigma_log_10)
env2_lo = anchor_close * (1 - 2*sigma_log_10)
env2_hi = anchor_close * (1 + 2*sigma_log_10)

anchor_close, str(last_date.date()), microtrend_return_5sess, mean_ret_5sess, sigma_log_5sess, sigma_log_10, env1_lo, env1_hi, env2_lo, env2_hi