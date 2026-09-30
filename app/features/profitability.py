import numpy as np
from scipy.stats import norm
def profitability_test(probabilities,outcomes):
    p=np.asarray(probabilities,float); y=np.asarray(outcomes,float); expected=p.sum(); actual=y.sum(); var=np.sum(p*(1-p)); z=(actual-expected)/np.sqrt(var) if var>0 else 0.0; return {"n_bets":len(p),"expected_wins":expected,"actual_wins":actual,"excess_wins":actual-expected,"profit_z":z,"p_value":float(norm.sf(z))}
def bh_qvalues(pvalues):
    p=np.asarray(pvalues,float); n=len(p); order=np.argsort(p); q=np.empty(n); q[order]=np.minimum.accumulate((p[order]*n/np.arange(1,n+1))[::-1])[::-1]; return np.clip(q,0,1)

