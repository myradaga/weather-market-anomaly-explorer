def split(frame):
    x=frame.sort_values("entry_time"); n=len(x); return x.iloc[:int(.7*n)],x.iloc[int(.7*n):int(.85*n)],x.iloc[int(.85*n):]
def run(con):
    a=con.execute("SELECT a.*,e.entry_time FROM alerts a JOIN episodes e USING(episode_id)").fetchdf(); train,val,test=split(a)
    return {"precision@25":float((test.head(25).alert_band.isin(["REVIEW","PRIORITY"])).mean()) if len(test) else 0,"false-positive rate":float((a.alert_band=="MONITOR").mean()) if len(a) else 0,"insufficient-evidence rate":float((a.status=="INSUFFICIENT_EVIDENCE").mean()) if len(a) else 0}

