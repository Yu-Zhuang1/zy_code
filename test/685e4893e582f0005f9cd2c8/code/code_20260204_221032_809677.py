from datetime import date
anchor=date(2026,2,5)
release_dates={'熊猫计划之部落奇遇记':date(2026,2,17),'星河入梦':date(2026,2,17),'喜欢上“欠欠”的你':date(2026,2,14),'藏地情书':date(2026,2,14),'爱乐之城(IMAX重映)':date(2026,2,14),'重返·狼群':date(2017,6,16)}
{t:(d-anchor).days for t,d in release_dates.items()}
