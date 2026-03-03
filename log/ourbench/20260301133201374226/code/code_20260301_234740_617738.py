import numpy as np, pandas as pd
rets = {
 '^GSPC': -0.00433935274336017,
 '^IXIC': -0.009186398386113237,
 'KWEB': -0.012714558573253543,
 'FXI': -0.0029419631704190596,
 '^HSI': 0.00945829749706184,
 '^HSCE': 0.0051280585049966465,
 'BABA': -0.02661263086794996,
 'JD': -0.01667898443291338,
 'ZTO': 0.009942005382850283,
 '9988.HK': -0.0006993433812281236,
 '9618.HK': 0.0038461685180664062,
 '2057.HK': 0.03123318872953118,
}

# Group proxies by class
broad = pd.Series({k:rets[k] for k in ['^GSPC','^IXIC','^HSI','^HSCE']})
china_internet = pd.Series({k:rets[k] for k in ['KWEB','BABA','9988.HK','JD','9618.HK']})
logistics = pd.Series({k:rets[k] for k in ['ZTO','2057.HK']})
china_largecap = pd.Series({k:rets[k] for k in ['FXI']})

def coherence(s):
    # coherence as 1 - (dispersion relative to abs(mean)+eps), clipped 0..1
    m = float(s.mean())
    disp = float(s.std(ddof=0))
    denom = abs(m) + 1e-6
    c = 1 - disp/denom
    return max(0.0, min(1.0, c)), m, disp

coh = {}
for name, s in [('broad',broad),('china_internet',china_internet),('logistics',logistics),('china_largecap',china_largecap)]:
    c,m,disp=coherence(s)
    coh[name]={'coherence':c,'mean':m,'disp':disp,'n':len(s)}

# normalized proxy signal: weighted mean of group means (weights reflect relevance to 2618: logistics/ecommerce)
weights={'broad':0.25,'china_largecap':0.10,'china_internet':0.35,'logistics':0.30}
proxy_signal = sum(weights[g]*coh[g]['mean'] for g in weights)

# overall coherence: weighted average of group coherence, penalize if group mean signs conflict
coh_score = sum(weights[g]*coh[g]['coherence'] for g in weights)
means = {g:coh[g]['mean'] for g in weights}
# sign disagreement penalty: count sign changes vs proxy_signal sign for nontrivial means
sgn = np.sign(proxy_signal) if abs(proxy_signal)>1e-6 else 0
penalty=0
for g,m in means.items():
    if abs(m)>0.001 and sgn!=0 and np.sign(m)!=sgn:
        penalty += weights[g]
coh_score = max(0.0, coh_score - 0.5*penalty)

coh, proxy_signal, coh_score, penalty
