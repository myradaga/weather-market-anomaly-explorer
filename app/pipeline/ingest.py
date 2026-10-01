import hashlib, json, logging, re
from datetime import datetime, timezone
from app.clients.gamma import GammaClient
from app.clients.data_api import DataAPIClient
from app.config import get_settings
from app.db.database import initialize,connect
from app.normalize.markets import token_ids
from app.normalize.fills import signed_yes_exposure, stable_fill_id
from app.weather import classify_daily_rain_temperature, classify_weather, official_weather_source
log=logging.getLogger(__name__)
CATEGORY_TAGS={
    "Politics":{"politics","elections","trump","congress","government"},
    "Sports":{"sports","soccer","nba","nfl","basketball","baseball","hockey"},
    "Weather":{"weather","climate","temperature","hurricane","rain","snow","storms"},
    "Crypto":{"crypto","bitcoin","ethereum","solana","crypto prices"},
    "Business & Economy":{"business","economy","finance","stocks","commodities","nymex crude oil futures"},
    "Science & Technology":{"science","technology","ai","space"},
    "Pop Culture":{"entertainment","culture","eurovision","movies","celebrities","music","television","pop culture","awards"},
    "World Affairs":{"world","geopolitics","iran","eu","war","foreign policy"},
}

def event_category(event):
    labels=[str(event["category"])] if event.get("category") else []
    labels += [str(t.get("label")) for t in event.get("tags",[]) if t.get("label")]
    normalized={label.lower() for label in labels}
    for category,tags in CATEGORY_TAGS.items():
        if normalized & tags: return category
    return labels[0] if labels and labels[0]!="All" else "Other"

def diversified_markets(events,limit):
    """Round-robin categories and cap each event so one event cannot dominate."""
    buckets={}
    for event in events or []:
        category=event_category(event)
        for market in (event.get("markets") or [])[:2]:
            buckets.setdefault(category,[]).append((event,market,category))
    chosen=[]
    while len(chosen)<limit and any(buckets.values()):
        for category in list(buckets):
            if buckets[category] and len(chosen)<limit: chosen.append(buckets[category].pop(0))
    return chosen

def dt(v):
    if not v:return None
    try:
        if isinstance(v,(int,float)):
            value=float(v)
            if value>10_000_000_000: value/=1000
            return datetime.fromtimestamp(value,timezone.utc)
        return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except Exception:return None
def resolved_outcome(market):
    if not market.get("closed"): return ""
    try:
        outcomes=market.get("outcomes") or [];
        prices=market.get("outcomePrices") or []
        if isinstance(outcomes,str): outcomes=json.loads(outcomes)
        if isinstance(prices,str): prices=json.loads(prices)
        values=[float(x) for x in prices]
        if values and max(values)>=.95: return str(outcomes[values.index(max(values))]).upper()
    except Exception: pass
    return ""
def is_weather_question(question): return classify_weather(question) is not None

def ingest(limit=25, closed=True, weather_only=False):
    initialize(); started=datetime.now(timezone.utc); gamma=GammaClient(); data=DataAPIClient(); errors=0; mc=fc=pc=0
    events=gamma.all_events(closed=closed,tag_id=84 if weather_only else None,max_events=max(1000,limit*10))
    discovered_events=list(events)
    if weather_only:
        # The event/tag is only a discovery route. Each visible contract question
        # must independently contain meteorological language.
        events=[dict(ev,markets=[m for m in (ev.get("markets") or []) if classify_daily_rain_temperature(m.get("question"))]) for ev in events]
        events=[ev for ev in events if ev.get("markets")]
    selected=[]
    if weather_only:
        for ev in events:
            for market in ev.get("markets") or []:
                if len(selected)>=limit: break
                selected.append((ev,market,"Weather"))
            if len(selected)>=limit: break
    else: selected=diversified_markets(events,limit)
    with connect() as con:
        now=datetime.now(timezone.utc)
        if weather_only:
            con.execute("DELETE FROM market_discovery_audit WHERE source='polymarket' AND discovered_at < ?",[now.replace(hour=0,minute=0,second=0,microsecond=0)])
            for ev in discovered_events:
                for candidate in ev.get("markets") or []:
                    wtype=classify_daily_rain_temperature(candidate.get("question")); external=str(candidate.get("id") or candidate.get("conditionId") or "")
                    audit_id=hashlib.sha256(f"polymarket|{external}|{now.date()}".encode()).hexdigest()
                    con.execute("INSERT OR REPLACE INTO market_discovery_audit VALUES (?,?,?,?,?,?,?,?)",[audit_id,"polymarket",now,external,candidate.get("question"),"ACCEPTED" if wtype else "REJECTED","Visible question match" if wtype else "No meteorological terms in visible question",wtype])
        for ev,market,category in selected:
                if weather_only: category="Weather"
                weather_type=classify_daily_rain_temperature(market.get("question")) if weather_only else None
                yes,no=token_ids(market)
                if not (yes and no): continue
                mid=str(market.get("id")); cond=str(market.get("conditionId") or market.get("condition_id") or "")
                outcomes=market.get("outcomes"); prices=market.get("outcomePrices")
                resolved=resolved_outcome(market); status="resolved" if market.get("closed") else "open"
                con.execute("""INSERT OR REPLACE INTO markets
                    (market_id,event_id,condition_id,question,slug,category,yes_token_id,no_token_id,open_time,close_time,resolution_time,resolved_token,status,volume,liquidity,unique_traders,eligible,eligibility_reason,data_quality_flags,raw_snapshot_id,created_at,updated_at,weather_type)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",[mid,str(ev.get("id")),cond,market.get("question"),market.get("slug"),category,yes,no,dt(market.get("startDate")),dt(market.get("endDate")),dt(market.get("closedTime")),resolved,status,float(market.get("volumeNum") or market.get("volume") or 0),float(market.get("liquidityNum") or market.get("liquidity") or 0),0,False,"unique-trader history not yet measurable","DQ11","live",datetime.now(timezone.utc),datetime.now(timezone.utc),weather_type]); mc+=1
                try:
                    trades=data.trades(cond or mid,get_settings().trade_limit)
                    if isinstance(trades,dict):trades=trades.get("data",trades.get("trades",[]))
                    for n,t in enumerate(trades or []):
                        tx=str(t.get("transactionHash") or t.get("transaction_hash") or hashlib.sha256(json.dumps(t,sort_keys=True).encode()).hexdigest()); li=str(t.get("logIndex") if t.get("logIndex") is not None else n); outcome=str(t.get("outcome") or ("YES" if str(t.get("asset") or t.get("token_id"))==yes else "NO")); side=str(t.get("side") or "BUY"); size=float(t.get("size") or 0); price=float(t.get("price") or 0)
                        fill_id=stable_fill_id(tx,li); public_wallet=t.get("proxyWallet") or t.get("proxy_wallet"); wallet=str(public_wallet) if public_wallet else f"unidentified:{fill_id}"
                        quality="" if public_wallet else "DQ_IDENTITY_MISSING"
                        con.execute("INSERT INTO fills VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(fill_id) DO NOTHING",[fill_id,tx,li,wallet,mid,cond,str(t.get("asset") or t.get("token_id") or ""),outcome,side,dt(t.get("timestamp")),price,size,price*size,signed_yes_exposure(side,outcome,size,price),"live",quality]); fc+=1
                except Exception as exc: errors+=1; log.warning("Trades unavailable for %s: %s",mid,exc)
                try:
                    hist=data.prices(yes); hist=hist.get("data",hist.get("history",[])) if isinstance(hist,dict) else hist
                    for p in hist or []:
                        stamp=dt(p.get("t") or p.get("timestamp"))
                        if stamp is None: continue
                        con.execute("INSERT OR REPLACE INTO price_observations VALUES (?,?,?,?,?,?)",[mid,yes,stamp,float(p.get("p") or p.get("price")),int(p.get("resolution_seconds") or 43200),"live"]); pc+=1
                except Exception as exc: errors+=1; log.warning("Prices unavailable for %s: %s",mid,exc)
                stats=con.execute("SELECT count(DISTINCT wallet),coalesce(sum(notional),0) FROM fills WHERE market_id=?",[mid]).fetchone()
                eligible=stats[0]>=get_settings().min_market_traders and stats[1]>=get_settings().min_market_notional
                reason="eligible" if eligible else f"liquidity gate: {stats[0]} traders, ${stats[1]:,.2f} observed notional"
                con.execute("UPDATE markets SET unique_traders=?, eligible=?, eligibility_reason=?, data_quality_flags=? WHERE market_id=?",[stats[0],eligible,reason,"" if eligible else "DQ11",mid])
                if weather_only and dt(market.get("endDate")):
                    event_time=dt(market.get("endDate")); eid=hashlib.sha256(f"weather-schedule|{mid}|{event_time.isoformat()}".encode()).hexdigest()
                    con.execute("INSERT OR REPLACE INTO public_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",[eid,mid,event_time,event_time,event_time,event_time,"Scheduled weather observation / contract close",f"https://polymarket.com/event/{market.get('slug') or mid}","MARKET_SCHEDULE","MEDIUM","SYSTEM",True,False,datetime.now(timezone.utc),datetime.now(timezone.utc),datetime.now(timezone.utc)])
                if weather_only:
                    source_name,source_url=official_weather_source(weather_type)
                    con.execute("INSERT OR REPLACE INTO authoritative_weather_sources VALUES (?,?,?,?,?)",[weather_type,source_name,source_url,f"Independent reference for {weather_type.lower()} contracts",datetime.now(timezone.utc)])
        run_id=hashlib.sha256(f"live-ingest|{started.isoformat()}|{limit}|{closed}".encode()).hexdigest()
        config_hash=hashlib.sha256(str(get_settings().model_dump()).encode()).hexdigest()
        con.execute("INSERT INTO pipeline_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",[run_id,started,datetime.now(timezone.utc),("ingest-weather-resolved" if closed else "ingest-weather-active") if weather_only else ("ingest-resolved" if closed else "ingest-active"),"SUCCESS" if errors==0 else "PARTIAL",mc,fc,pc,0,0,errors,"unknown",config_hash])
    return {"mode":"resolved" if closed else "active","markets":mc,"fills":fc,"prices":pc,"errors":errors}
