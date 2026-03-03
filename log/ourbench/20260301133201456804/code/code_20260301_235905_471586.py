import numpy as np
broad = {'HSI': (26381.01953125,26630.5390625), 'FXI': (37.38999938964844,37.279998779296875), 'KWEB': (31.459999084472656,31.059999465942383)}
macro={'GSPC':(6908.85986328125,6878.8798828125)}
sector={'TAN':(57.58000183105469,55.0),'ICLN':(18.670000076293945,18.219999313354492),'ENPH':(45.77000045776367,42.27000045776367),'FSLR':(200.10000610351562,197.1999969482422),'JKS':(26.459999084472656,25.290000915527344),'CSIQ':(19.940000534057617,17.709999084472656),'DQ':(23.950000762939453,24.1200008392334)}

def ret(pair):
    c0,c1=pair
    return c1/c0-1

broad_rets={k:ret(v) for k,v in broad.items()}
macro_rets={k:ret(v) for k,v in macro.items()}
sector_rets={k:ret(v) for k,v in sector.items()}

broad_avg=np.mean(list(broad_rets.values()))
sector_avg=np.mean(list(sector_rets.values()))
macro_avg=np.mean(list(macro_rets.values()))

broad_rets, broad_avg, sector_avg, macro_avg