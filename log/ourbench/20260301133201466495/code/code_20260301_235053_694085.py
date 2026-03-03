import numpy as np
# Recompute full outputs for reporting
rets = {'SPY': -0.0048012941732112765,
 'QQQ': -0.003200128499436311,
 'ASHR': -0.002341991487043286,
 'FXI': -0.002942495193428157,
 'MCHI': -0.002871964559286129,
 'KWEB': -0.012713976209683925,
 'BABA': -0.02661037922064092,
 'JD': -0.01667826926237532,
 'PDD': -0.01574980912875631,
 'SOXX': -0.012637906825212078,
 'ITA': 0.0037067781103078365,
 'YINN': -0.008381351920967737,
 'YANG': 0.008723932201172376}

fx_ret = 6.84089994430542/6.869200229644775-1
cny_bull = -fx_ret

signals = {
 'broad_us': np.mean([rets['SPY'], rets['QQQ']]),
 'china_broad': np.mean([rets['ASHR'], rets['FXI'], rets['MCHI']]),
 'china_growth': np.mean([rets['KWEB'], rets['YINN']]),
 'adr': np.mean([rets['BABA'], rets['JD'], rets['PDD']]),
 'sector': np.mean([rets['SOXX'], rets['ITA']]),
 'cny': cny_bull
}
proxy_return_signal = float(0.35*signals['china_broad'] + 0.15*signals['broad_us'] + 0.25*signals['sector'] + 0.15*(0.5*signals['adr']+0.5*signals['china_growth']) + 0.10*signals['cny'])

signals, fx_ret, cny_bull, proxy_return_signal
