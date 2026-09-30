import hashlib, json, math
from datetime import datetime, timezone
def composite(scores,reliability,weights=None):
    """Reliability-tempered naive-Bayes-style evidence combination.

    Scores are empirical anomaly percentiles. Their odds are multiplied in log
    space, so several agreeing modules matter more than one isolated high score.
    """
    weights=weights or [1]*len(scores); terms=[(float(s),float(q),float(w)) for s,q,w in zip(scores,reliability,weights) if s is not None and q>0]
    if not terms:return None,0
    evidence=sum(q*w*math.log(min(.99,max(.01,s))/(1-min(.99,max(.01,s)))) for s,q,w in terms)
    return 1/(1+math.exp(-max(-30,min(30,evidence)))),len(terms)
def alert_band(score,count,timing_high=False):
    if score is None:return "NONE"
    if score>=.92 and count>=5 and timing_high:return "PRIORITY"
    if score>=.85 and count>=4:return "REVIEW"
    if score>=.75 and count>=4:return "MONITOR"
    return "NONE"
def score_all(con):
    rows=con.execute("SELECT f.*,e.data_quality_flags,e.total_notional,e.trade_count FROM episode_features f JOIN episodes e USING(episode_id)").fetchdf(); con.execute("DELETE FROM alerts"); created=0
    for _,r in rows.iterrows():
        scores=[None if str(r[f"s{i}"])=="nan" else float(r[f"s{i}"]) for i in range(1,6)]; qs=[float(r[f"q{i}"]) for i in range(1,6)]; score,count=composite(scores,qs)
        strong=sum(1 for s,q in zip(scores,qs) if s is not None and q>0 and s>=.75)
        enough_activity=(r.trade_count>=2 and r.total_notional>=100) or r.total_notional>=5000
        band=alert_band(score,count,r.q2==1 and r.s2 is not None) if strong>=3 and enough_activity else "NONE"
        if band=="NONE": continue
        aid=hashlib.sha256(f"alert|{r.episode_id}".encode()).hexdigest(); evidence=json.dumps([f"S{i}={s:.2f}" for i,s in enumerate(scores,1) if s is not None],separators=(",",":")); counter=r.suppression_reasons or "Composite score is an anomaly ranking, not evidence of illegal conduct."
        con.execute("INSERT INTO alerts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",[aid,r.episode_id,*scores,score,count,band,sum(qs)/5,evidence,counter,r.data_quality_flags,r.feature_version,r.model_version,datetime.now(timezone.utc),"NEW"]); created+=1
    return created
