import pandas as pd, numpy as np
vol=[19866839,40062174,25373600,22532287,20969625,24437310,22608642,33545095,23464712,20928248,15752566,15445052,18248800,16301002,20750825,25965166,17117933,19895203,26549655,17156220,16676112,14701877,15412630,21869394,14082884,10758114,7743646,7172675,7965987,8480433,16248756,12924342,11818347,10454020]
dates=pd.to_datetime(["2026-01-05","2026-01-06","2026-01-07","2026-01-08","2026-01-09","2026-01-12","2026-01-13","2026-01-14","2026-01-15","2026-01-16","2026-01-19","2026-01-20","2026-01-21","2026-01-22","2026-01-23","2026-01-26","2026-01-27","2026-01-28","2026-01-29","2026-01-30","2026-02-02","2026-02-03","2026-02-04","2026-02-05","2026-02-06","2026-02-09","2026-02-10","2026-02-11","2026-02-12","2026-02-13","2026-02-24","2026-02-25","2026-02-26","2026-02-27"])
df=pd.DataFrame({'date':dates,'volume':vol})
df['weekday']=df['date'].dt.day_name()
df['logv']=np.log(df['volume'])
weekday_med_log=df.groupby('weekday')['logv'].median()
# last observed Monday
last_mon=df[df['weekday']=='Monday'].iloc[-1]
mon_med_log=weekday_med_log['Monday']
last_mon_resid=float(last_mon['logv']-mon_med_log)
last_mon_ratio=float(np.exp(last_mon_resid))
last_mon_date=str(last_mon['date'].date())
# recent 4 sessions (Feb24-27) vs their weekday medians
wk_base=df['weekday'].map(weekday_med_log)
df['resid']=df['logv']-wk_base
recent=df.tail(4)[['date','weekday','volume','resid']]
recent['resid_ratio']=np.exp(recent['resid'])
last_mon_date,last_mon['volume'],last_mon_ratio, recent