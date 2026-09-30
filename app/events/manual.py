import hashlib
from datetime import datetime,timezone
def save_event(con,market_id,event_time,headline,source_url,confidence="MEDIUM",annotator="manual",verified=True,event_id=None,source_type="MANUAL"):
    eid=event_id or hashlib.sha256(f"{market_id}|{event_time}|{source_url}".encode()).hexdigest(); now=datetime.now(timezone.utc)
    con.execute("INSERT OR REPLACE INTO public_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",[eid,market_id,event_time,event_time,event_time,event_time,headline,source_url,source_type,confidence,annotator,verified,False,now,now,now]); return eid
