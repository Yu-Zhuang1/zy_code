import pandas as pd, numpy as np
# yfinance data copied from tool output manually? We'll reconstruct from arrays

dates = pd.to_datetime(["2026-01-15","2026-01-16","2026-01-19","2026-01-20","2026-01-21","2026-01-22","2026-01-23","2026-01-26","2026-01-27","2026-01-28","2026-01-29","2026-01-30","2026-02-02","2026-02-03","2026-02-04","2026-02-05","2026-02-06","2026-02-09","2026-02-10","2026-02-11","2026-02-12","2026-02-13","2026-02-24","2026-02-25","2026-02-26","2026-02-27"])
close = np.array([79.45999908447266,78.72000122070312,82.4000015258789,86.0199966430664,84.08000183105469,85.30000305175781,84.25,84.97000122070312,84.69999694824219,87.30999755859375,87.5999984741211,87.97000122070312,80.33000183105469,83.33999633789062,84.80000305175781,83.61000061035156,86.69999694824219,87.0199966430664,86.0,88.8499984741211,88.0,84.95999908447266,87.25,89.70999908447266,90.0199966430664,93.0])

s = pd.Series(close, index=dates)
ret = s.pct_change().dropna()
logret = np.log(s).diff().dropna()

# windows
for w in [3,5,10,20]:
    if len(ret)>=w:
        r = ret.iloc[-w:]
        lr = logret.iloc[-w:]
        drift = lr.mean()  # avg daily log return
        vol = lr.std(ddof=1)
        print(w, 'mean_logret', drift, 'std_logret', vol, 'cum_return', (s.iloc[-1]/s.iloc[-w-1]-1))

# last close
print('anchor_close', float(s.iloc[-1]), 'date', s.index[-1].date())

# compute 5-day simple mean return and 5-day realized vol using simple returns
w=5
r = ret.iloc[-w:]
print('mean_simple', r.mean(), 'std_simple', r.std(ddof=1))

# also 10-day using simple
w=10
r=ret.iloc[-w:]
print('10 mean_simple', r.mean(), '10 std_simple', r.std(ddof=1))
