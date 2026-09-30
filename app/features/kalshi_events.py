import hashlib
import re
import pandas as pd

STOP={"will","the","be","in","on","at","a","an","to","of","for","more","than","above","below","or"}

def _tokens(text):
    return {x for x in re.findall(r"[a-z0-9]+",str(text).lower()) if len(x)>2 and x not in STOP}

def candidate_market_match(title, questions):
    """Return a cautious lexical candidate; it is not proof of equivalent rules."""
    left=_tokens(title); best=(None,0.0)
    for question in questions:
        right=_tokens(question); union=left|right
        score=len(left&right)/len(union) if union else 0
        if score>best[1]: best=(question,float(score))
    return best

def build_activity_events(frame,gap_minutes=30):
    if frame.empty:return pd.DataFrame()
    f=frame.copy(); f["timestamp_utc"]=pd.to_datetime(f.timestamp_utc,utc=True); f=f.sort_values(["ticker","timestamp_utc","trade_id"])
    f["prior_price"]=f.groupby("ticker").price.shift(1); f["next_price"]=f.groupby("ticker").price.shift(-1)
    f["event_number"]=f.groupby("ticker").timestamp_utc.diff().gt(pd.Timedelta(minutes=gap_minutes)).fillna(True).groupby(f.ticker).cumsum()
    rows=[]
    for (ticker,event_number),g in f.groupby(["ticker","event_number"],sort=False):
        if not bool(g.is_anomaly.any()):continue
        start=g.timestamp_utc.iloc[0]; end=g.timestamp_utc.iloc[-1]; before=g.prior_price.iloc[0]; after=g.next_price.iloc[-1]
        start_price=float(g.price.iloc[0]); end_price=float(g.price.iloc[-1]); before=float(before) if pd.notna(before) else start_price; after=float(after) if pd.notna(after) else end_price
        impact=end_price-before; reversal=(after-end_price)
        max_swing=float(g.price.max()-g.price.min()); total=float(g.notional.sum()); peak=float(g.notional.max())
        dims=[float(g[k].max()) for k in ("k1_size","k2_price","k3_burst","k4_concentration","k5_behavior")]
        strong=sum(x>=.80 for x in dims); close=pd.to_datetime(g.close_time.iloc[0],utc=True) if pd.notna(g.close_time.iloc[0]) else pd.NaT
        hours_to_close=(close-start).total_seconds()/3600 if pd.notna(close) else None
        reversed_direction=impact*reversal<0 and abs(reversal)>=.02
        if max_swing>=.10 and reversed_direction:kind="Price impact and reversal"
        elif hours_to_close is not None and 0<=hours_to_close<=24:kind="Settlement-window activity"
        elif float(g.k2_price.max())>=.8:kind="Abnormal trading burst"
        elif total>=1000:kind="Large unexplained activity"
        else:kind="Peer-market deviation"
        grade="HIGH" if total>=1000 and strong>=4 and (abs(impact)>=.05 or max_swing>=.10) else "MEDIUM" if total>=250 and strong>=3 else "LOW"
        eid=hashlib.sha256(f"{ticker}|{start.isoformat()}|{gap_minutes}".encode()).hexdigest()
        summary=(f"${total:,.0f} traded across {len(g):,} trade{'s' if len(g)!=1 else ''} in "
                 f"{max(1,int((end-start).total_seconds()/60)+1)} minutes. Price moved from {before:.2f} to {end_price:.2f}"
                 f" ({impact:+.2f}) and the next observed price was {after:.2f}.")
        rows.append(dict(activity_event_id=eid,ticker=ticker,event_number=int(event_number),title=g.title.iloc[0],subtitle=g.subtitle.iloc[0],event_ticker=g.event_ticker.iloc[0],weather_type=g.weather_type.iloc[0],start_time=start,end_time=end,trade_count=len(g),total_notional=total,largest_trade=peak,price_before=before,price_end=end_price,price_after=after,price_impact=impact,reversal_move=reversal,max_price_swing=max_swing,reversed=bool(reversed_direction),hours_to_close=hours_to_close,review_score=float(g.anomaly_score.max()),strong_dimensions=strong,evidence_grade=grade,case_type=kind,summary=summary,k1=dims[0],k2=dims[1],k3=dims[2],k4=dims[3],k5=dims[4]))
    out=pd.DataFrame(rows)
    if len(out):
        order={"HIGH":0,"MEDIUM":1,"LOW":2}; out["_order"]=out.evidence_grade.map(order); out=out.sort_values(["_order","strong_dimensions","review_score"],ascending=[True,False,False]).drop(columns="_order")
    return out
