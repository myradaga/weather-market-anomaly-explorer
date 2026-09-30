import numpy as np
from sklearn.ensemble import IsolationForest
def anomaly_percentiles(frame, contamination=.02):
    if len(frame)<2: return np.full(len(frame),.5), None
    x=np.nan_to_num(frame.astype(float).to_numpy()); model=IsolationForest(n_estimators=200,contamination=contamination,random_state=42).fit(x); raw=-model.score_samples(x); ranks=np.argsort(np.argsort(raw)); return (ranks+1)/len(raw),model
