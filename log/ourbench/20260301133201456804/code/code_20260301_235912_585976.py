import pandas as pd, numpy as np

dates = pd.to_datetime(["2026-02-24","2026-02-25","2026-02-26","2026-02-27"])
close = np.array([92.2699966430664,98.45999908447266,98.33000183105469,104.5])
df = pd.DataFrame({'close':close}, index=dates)
df['ret']=df['close'].pct_change()
ret1 = float(df['ret'].iloc[-1])
ret3 = float(close[-1]/close[0]-1)
ret2 = float(close[-1]/close[1]-1)
ret1, ret2, ret3