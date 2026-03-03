import pandas as pd, numpy as np, datetime as dt
vol=[19866839,40062174,25373600,22532287,20969625,24437310,22608642,33545095,23464712,20928248,15752566,15445052,18248800,16301002,20750825,25965166,17117933,19895203,26549655,17156220,16676112,14701877,15412630,21869394,14082884,10758114,7743646,7172675,7965987,8480433,16248756,12924342,11818347,10454020]
dates=pd.to_datetime(["2026-01-05","2026-01-06","2026-01-07","2026-01-08","2026-01-09","2026-01-12","2026-01-13","2026-01-14","2026-01-15","2026-01-16","2026-01-19","2026-01-20","2026-01-21","2026-01-22","2026-01-23","2026-01-26","2026-01-27","2026-01-28","2026-01-29","2026-01-30","2026-02-02","2026-02-03","2026-02-04","2026-02-05","2026-02-06","2026-02-09","2026-02-10","2026-02-11","2026-02-12","2026-02-13","2026-02-24","2026-02-25","2026-02-26","2026-02-27"])
df=pd.DataFrame({'date':dates,'volume':vol})
df['weekday']=df['date'].dt.day_name()
df['logv']=np.log(df['volume'])
# overall robust baseline
overall_med=df['volume'].median()
weekday_med=df.groupby('weekday')['volume'].median()
weekday_med_log=df.groupby('weekday')['logv'].median()
# Monday effect
mon_med=weekday_med.get('Monday',np.nan)
mon_scale=mon_med/overall_med
# residuals vs weekday baseline
wk_base=df['weekday'].map(weekday_med_log)
df['resid']=df['logv']-wk_base
# recent residual (last 5 sessions)
resid_last5=df.tail(5)['resid'].median()
# trend: regress logv on time index over last 20 sessions
N=20
df_tr=df.tail(N).copy()
x=np.arange(N)
y=df_tr['logv'].values
slope=np.polyfit(x,y,1)[0]
trend_scale=float(np.exp(slope))
trend_signal=float(trend_scale-1)
# also compare last5 mean vs prior15 mean (in log)
last5=df.tail(5)['logv'].mean(); prior15=df.tail(20).head(15)['logv'].mean()
rel=float(np.exp(last5-prior15)-1)
# volatility/quality: resid std over last20
resid_std=float(df.tail(20)['resid'].std())
trend_info={'slope_log_per_session':slope,'trend_scale_next':trend_scale,'trend_signal':trend_signal,'last5_vs_prior15':rel,'resid_last5_med':resid_last5,'resid_std20':resid_std,'overall_med':overall_med,'monday_med':mon_med,'mon_scale':mon_scale,'weekday_medians':weekday_med.to_dict()}
trend_info