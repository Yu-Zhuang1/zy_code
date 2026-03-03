import pandas as pd, numpy as np

data = {
 '2618.HK': [11.0699996948,11.1700000763],
 '^HSI': [26381.019531,26630.539062],
 '^HSCE': [8814.290039,8859.490234],
 '^GSPC': [6908.859863,6878.879883],
 '^IXIC': [22878.380859,22668.210938],
 'KWEB': [31.459999,31.059999],
 'FXI': [37.389999,37.279999],
 'BABA': [148.05,144.11],
 'JD': [26.98,26.530001],
 'ZTO': [24.139999,24.379999],
 '^VIX': [18.629999,19.860001],
}
rets = {k: v[1]/v[0]-1 for k,v in data.items()}
df = pd.DataFrame({'ret_1d': pd.Series(rets)}).sort_values('ret_1d')
# also compute z-scores vs cross-proxy set excluding VIX (risk off inverse)
proxy_syms = ['^GSPC','^IXIC','KWEB','FXI','BABA','JD','ZTO','^HSI','^HSCE']
proxy = pd.Series({k:rets[k] for k in proxy_syms})
mean=proxy.mean(); std=proxy.std(ddof=0)
z = (proxy-mean)/(std if std>0 else 1)

out = {
 'rets': rets,
 'proxy_mean': float(mean),
 'proxy_std': float(std),
 'proxy_z': {k: float(zv) for k,zv in z.items()},
}
print(df.to_string())
print('---')
print(out)
