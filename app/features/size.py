import numpy as np
def robust_z(values):
    x=np.log1p(np.asarray(values,dtype=float)); med=np.median(x); mad=np.median(np.abs(x-med)); return np.zeros(len(x)) if mad==0 else (x-med)/(1.4826*mad)
def percentile(value, values):
    a=np.asarray(values,dtype=float); return float(np.mean(a<=value)) if len(a) else float("nan")

