import numpy as np
# returns in decimal
sp=-0.00434
nas=-0.00919
kweb=-0.0127
baba=-0.0266
jd=-0.0167
csi=-0.00343
cny= (6.8409/6.8692-1)  # negative means CNY stronger
sp, nas, kweb, baba, jd, csi, cny
w={'kweb':0.35,'peers':0.25,'nas':0.15,'sp':0.10,'csi':0.10,'fx':0.05}
peer_avg=(baba+jd)/2
signal=w['kweb']*kweb + w['peers']*peer_avg + w['nas']*nas + w['sp']*sp + w['csi']*csi + w['fx']*(-cny)  # -cny so CNY stronger => positive
signal
