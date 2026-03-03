import numpy as np
turnover = {
    '2026-02-20':165.37,
    '2026-02-23':172.96,
    '2026-02-24':250.99,
    '2026-02-25':236.77,
    '2026-02-26':259.28,
    '2026-02-27':288.42037517,
}
baseline_days = ['2026-02-20','2026-02-23','2026-02-24','2026-02-25','2026-02-26']
baseline = np.array([turnover[d] for d in baseline_days])
last = turnover['2026-02-27']
mean = baseline.mean()
std = baseline.std(ddof=1)
ratio = last/mean
pct = ratio-1
z = (last-mean)/std
mean,std,ratio,pct,z
