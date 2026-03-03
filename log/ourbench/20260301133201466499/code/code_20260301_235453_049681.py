import pandas as pd, numpy as np

# Manually input from tool outputs (could re-call but keep minimal)
vol_399001=[3408800,3053400,2785900,2974000,2671500,2756500,3579800,3634600,3335000,3292200,3773400,3387900,2949700,2923100,2959700,2625500,2468300,2380900,2407200,2463600,2534500,2321200,2549400,2913400,2828100,2880000]
vol_000001=[680300,763600,688900,734400,667000,709700,782100,887400,755000,823000,905900,804300,733000,637700,674300,596700,556700,572600,524600,500700,529400,500800,566300,724800,651700,682000]
vol_000300=[254000,325300,267600,282700,266400,274200,314600,363000,301500,382300,415500,319800,304800,265500,264900,237900,202700,207300,187000,173400,197800,189200,218500,284300,234800,261400]

def activity_metrics(vol, short=5, long=20):
    vol=np.array(vol, dtype=float)
    if len(vol)<long:
        long=len(vol)
    long_mean=vol[-long:].mean()
    long_std=vol[-long:].std(ddof=1) if len(vol[-long:])>1 else 0.0
    short_mean=vol[-short:].mean() if len(vol)>=short else vol.mean()
    ratio=short_mean/long_mean if long_mean else 1.0
    z=(short_mean-long_mean)/long_std if long_std else 0.0
    last_ratio=vol[-1]/long_mean if long_mean else 1.0
    return dict(long_mean=long_mean, long_std=long_std, short_mean=short_mean, ratio=ratio, z=z, last_ratio=last_ratio)

m399001=activity_metrics(vol_399001)
m000001=activity_metrics(vol_000001)
m000300=activity_metrics(vol_000300)
m399001, m000001, m000300
