import pandas as pd, numpy as np

# hardcode closes from tool outputs
closes = {
 'SPY': [693.1500244140625, 689.2999877929688, 685.989990234375],
 'QQQ': [616.6799926757812, 609.239990234375, 607.2899780273438],
 'ASHR':[34.56999969482422,34.16999816894531,34.09000015258789],
 'FXI':[38.41999816894531,37.38999938964844,37.279998779296875],
 'MCHI':[60.66999816894531,59.22999954223633,59.060001373291016],
 'KWEB':[32.2400016784668,31.459999084472656,31.059999465942383],
 'BABA':[152.27999877929688,148.0500030517578,144.11000061035156],
 'JD':[27.540000915527344,26.979999542236328,26.530000686645508],
 'PDD':[106.9000015258789,105.38999938964844,103.7300033569336],
 'SOXX':[368.0,356.79998779296875,352.2900085449219],
 'ITA':[241.22000122070312,242.82000732421875,243.72000122070312],
 'YINN':[41.529998779296875,38.18000030517578,37.86000061035156],
 'YANG':[24.389999389648438,26.3700008392334,26.600000381469727]
}
# Returns for Feb27 vs Feb26
rets = {k: (v[2]/v[1]-1) for k,v in closes.items()}
rets

# FX: CNY=X (USD/CNY) close decreased => CNY stronger. We'll include as + for risk? maybe stronger CNY bullish for CN stocks.
fx = {'CNY=X':[6.8831000328063965,6.869200229644775,6.84089994430542]}
fx_ret = fx['CNY=X'][2]/fx['CNY=X'][1]-1 # USD/CNY
fx_ret

# create proxy groups
broad_us = ['SPY','QQQ']
china_broad = ['ASHR','FXI','MCHI']
china_growth = ['KWEB','YINN']
adr = ['BABA','JD','PDD']
sector = ['SOXX','ITA']

# Adjust fx sign: USD/CNY down => bullish => use -fx_ret
adj_rets = rets.copy()
adj_rets['CNY_bull'] = -fx_ret

# compute group means
import math

def mean_ret(names):
    return float(np.mean([adj_rets[n] for n in names]))

signals = {
 'broad_us': mean_ret(broad_us),
 'china_broad': mean_ret(china_broad),
 'china_growth': mean_ret(china_growth),
 'adr': mean_ret(adr),
 'sector': mean_ret(sector),
 'cny': adj_rets['CNY_bull']
}
signals

# For 002179: defense/electronics connector; tie to ITA (defense) and some tech cycle (SOXX), plus CN broad. We'll weight: china_broad 0.35, broad_us 0.15, sector 0.25, adr/china_growth 0.15, cny 0.10
proxy_return_signal = (0.35*signals['china_broad'] + 0.15*signals['broad_us'] + 0.25*signals['sector'] + 0.15*(0.5*signals['adr']+0.5*signals['china_growth']) + 0.10*signals['cny'])
proxy_return_signal

# coherence: compute sign agreement with overall across proxies used
proxy_list = ['SPY','QQQ','ASHR','FXI','MCHI','KWEB','YINN','BABA','JD','PDD','SOXX','ITA','CNY_bull']
proxy_vals = np.array([adj_rets.get(p, rets.get(p)) for p in proxy_list])
# overall mean
overall = proxy_vals.mean()
# sign agreement fraction
agree = np.mean(np.sign(proxy_vals)==np.sign(overall))
# dispersion penalty: 1 - (std/ (abs(mean)+std+1e-9))
std = proxy_vals.std(ddof=0)
penalty = 1 - std/(abs(overall)+std+1e-9)
coherence = float(max(0,min(1, agree*penalty)))
overall, agree, std, penalty, coherence
