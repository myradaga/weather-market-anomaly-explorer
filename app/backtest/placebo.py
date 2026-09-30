import numpy as np
def placebo_percentile(real_score,n=100,seed=42):
    values=np.random.default_rng(seed).uniform(0,1,n); return float(np.mean(values<=real_score))

