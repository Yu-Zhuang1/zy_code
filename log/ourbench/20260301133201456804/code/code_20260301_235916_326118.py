import numpy as np
broad=np.array([0.009458297506448776,-0.0029419794636855734,-0.012714546413566064])
macro=np.array([-0.00433935281103115])
sector=np.array([-0.04411818677686839])
# for coherence use underlying sector constituents rather than avg
sector_const=np.array([-0.044818963110, -0.024108000, -0.076513000, -0.014493000, -0.044225000, -0.111831000, 0.007098000])
# sign agreement within groups
sign_agree_broad=abs(np.mean(np.sign(broad)))
sign_agree_sector=abs(np.mean(np.sign(sector_const)))
# cross-group agreement: sign of means
means=np.array([np.mean(broad), np.mean(macro), np.mean(sector_const)])
cross_agree=abs(np.mean(np.sign(means)))
# magnitude consensus: mean/meanabs
mag_consensus=abs(np.mean(means))/np.mean(np.abs(means))
coherence=0.4*sign_agree_broad+0.4*sign_agree_sector+0.2*cross_agree
sign_agree_broad, sign_agree_sector, cross_agree, mag_consensus, coherence, means