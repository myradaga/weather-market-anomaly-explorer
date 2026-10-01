from datetime import datetime, timezone
import re
import numpy as np
import pandas as pd
from app.clients.kalshi import KalshiClient
from app.db.database import initialize, connect
from app.features.behavior import anomaly_percentiles
from app.scoring.composite import composite
from app.weather import classify_daily_rain_temperature, classify_weather, official_weather_source

WEATHER_WORDS=("temperature","hottest","coldest","rain","rainfall","snow","snowfall","hurricane","tornado","storm","wind speed","precipitation","heat wave","freeze","frost")
WEATHER_PATTERN=re.compile(r"\b(?:temperature|hottest|coldest|rain|rainfall|snow|snowfall|hurricane|hurricanes|tornado|tornadoes|storm|storms|wind speed|precipitation|heat wave|freeze|frost)\b",re.I)

def _dt(value):
    if not value: return None
    return datetime.fromisoformat(str(value).replace("Z","+00:00"))

def _number(value):
    try: return float(value or 0)
    except (TypeError,ValueError): return 0.0

def _weather_series(series):
    return classify_weather(series) is not None

def _weather_market(market):
    return classify_weather(market) is not None

def _score_market_trades(con,ticker):
    """Score against the same weather-contract type, while retaining ticker-local burst and concentration signals."""
    weather_type=con.execute("SELECT weather_type FROM kalshi_weather_markets WHERE ticker=?",[ticker]).fetchone()[0]
    peer=con.execute("""SELECT t.trade_id,t.ticker,t.timestamp_utc,t.notional,t.price,t.contracts,t.is_block_trade
        FROM kalshi_weather_trades t JOIN kalshi_weather_markets m USING(ticker)
        WHERE m.weather_type=? ORDER BY t.timestamp_utc""",[weather_type]).fetchdf()
    frame=peer[peer.ticker==ticker].copy().sort_values("timestamp_utc")
    if frame.empty:return 0
    peer_x=np.log1p(peer.notional.astype(float).to_numpy()); med=float(np.median(peer_x)); mad=float(np.median(np.abs(peer_x-med)))
    x=np.log1p(frame.notional.astype(float).to_numpy()); z=np.zeros(len(x)) if mad==0 else (x-med)/(1.4826*mad)
    peer_rank=peer.notional.rank(method="max",pct=True); k1=peer_rank.loc[frame.index].to_numpy()
    k2=np.clip(2*np.abs(frame.price.astype(float).to_numpy()-.5),0,1)
    gaps=pd.to_datetime(frame.timestamp_utc,utc=True).diff().dt.total_seconds().div(60).fillna(1440).clip(lower=0)
    positive=gaps[(gaps>0)&(gaps<1440)]; expected_gap=float(positive.median()) if len(positive)>=20 else 60.0
    # Poisson-arrival baseline: only intervals unusually short relative to this
    # market's own history receive a high burst score.
    k3=np.exp(-gaps.to_numpy()/max(expected_gap,1e-6)) if len(positive)>=20 else np.full(len(frame),.5)
    total=max(float(frame.notional.sum()),1e-9); k4=np.clip(frame.notional.astype(float).to_numpy()/total*20,0,1)
    peer_behavior=peer[["notional","price","contracts"]].copy(); peer_behavior["is_block_trade"]=peer.is_block_trade.astype(float)
    peer_behavior["gap_minutes"]=peer.groupby("ticker").timestamp_utc.diff().dt.total_seconds().div(60).fillna(1440).clip(lower=0)
    peer_behavior=peer_behavior.rank(method="average",pct=True)
    peer_k5,_=anomaly_percentiles(peer_behavior.fillna(.5),contamination=.02); k5=pd.Series(peer_k5,index=peer.index).loc[frame.index].to_numpy()
    scores=np.array([composite([a,b,c,d,e],[1,1,.4,1,1])[0] for a,b,c,d,e in zip(k1,k2,k3,k4,k5)])
    strong=np.sum(np.vstack([k1,k2,k3,k4,k5])>=.85,axis=0)
    flagged=(scores>=.95)&(k1>=.95)&(strong>=4)&(frame.notional.astype(float).to_numpy()>=50)
    for trade_id,p,zv,score,a,b,c,d,e,is_flagged in zip(frame.trade_id,k1,z,scores,k1,k2,k3,k4,k5,flagged):
        con.execute("UPDATE kalshi_weather_trades SET size_percentile=?,robust_z=?,anomaly_score=?,is_anomaly=?,k1_size=?,k2_price=?,k3_burst=?,k4_concentration=?,k5_behavior=? WHERE trade_id=?",[float(p),float(zv),float(score),bool(is_flagged),float(a),float(b),float(c),float(d),float(e),trade_id])
    return int(flagged.sum())

def rescore_all_kalshi(con):
    """Vectorized peer-type scoring; fits K5 once per weather type."""
    frame=con.execute("""SELECT t.trade_id,t.ticker,t.timestamp_utc,t.notional,t.price,t.contracts,t.is_block_trade,m.weather_type,m.close_time
        FROM kalshi_weather_trades t JOIN kalshi_weather_markets m USING(ticker)
        WHERE m.status IN ('open','active') AND m.weather_type IS NOT NULL""").fetchdf()
    con.execute("UPDATE kalshi_weather_trades SET is_anomaly=FALSE")
    if frame.empty:return 0
    parts=[]
    for weather_type,peer in frame.groupby("weather_type"):
        peer=peer.copy(); relative_size=peer.notional.rank(method="max",pct=True)
        absolute_materiality=np.clip(peer.notional.astype(float)/250,0,1)
        peer["k1_size"]=(relative_size+absolute_materiality)/2
        peer["gap_minutes"]=peer.groupby("ticker").timestamp_utc.diff().dt.total_seconds().div(60).fillna(1440).clip(lower=0)
        peer["k2_price"]=.5
        for ticker,idx in peer.groupby("ticker").groups.items():
            gaps=peer.loc[idx,"gap_minutes"]; positive=gaps[(gaps>0)&(gaps<1440)]
            burst=np.exp(-gaps/max(float(positive.median()),1e-6)) if len(positive)>=20 else np.full(len(gaps),.5)
            stamps=pd.to_datetime(peer.loc[idx,"timestamp_utc"],utc=True); closes=pd.to_datetime(peer.loc[idx,"close_time"],utc=True)
            hours_to_close=(closes-stamps).dt.total_seconds().div(3600).clip(lower=0); close_proximity=np.exp(-hours_to_close/24).fillna(0)
            peer.loc[idx,"k2_price"]=np.maximum(burst,close_proximity)
        # Price-impact/reversal evidence from the contract's own executed-price path.
        peer=peer.sort_values(["ticker","timestamp_utc","trade_id"])
        previous=peer.groupby("ticker").price.shift(1); following=peer.groupby("ticker").price.shift(-1)
        impact=(peer.price-previous).abs().fillna(0); reversed_move=((peer.price-previous)*(following-peer.price)<0).fillna(False)
        reversal_size=(following-peer.price).abs().fillna(0)
        peer["k3_burst"]=np.clip(.65*(impact/.15)+.35*reversed_move.astype(float)*np.clip(reversal_size/.10,0,1),0,1)
        totals=peer.groupby("ticker").notional.transform("sum").clip(lower=1e-9); peer["k4_concentration"]=np.clip(peer.notional/totals*20,0,1)
        behavior=peer[["notional","price","contracts","gap_minutes"]].copy(); behavior["is_block_trade"]=peer.is_block_trade.astype(float); behavior=behavior.rank(method="average",pct=True)
        peer["k5_behavior"],_=anomaly_percentiles(behavior.fillna(.5),contamination=.02)
        peer["anomaly_score"]=[composite(vals,[1,.4,.8,1,1])[0] for vals in peer[["k1_size","k2_price","k3_burst","k4_concentration","k5_behavior"]].to_numpy()]
        strong=(peer[["k1_size","k2_price","k3_burst","k4_concentration","k5_behavior"]]>=.80).sum(axis=1)
        peer["is_anomaly"]=(peer.anomaly_score>=.95)&(peer.k1_size>=.85)&(strong>=3)&(peer.notional>=250)
        x=np.log1p(peer.notional.astype(float)); med=float(x.median()); mad=float((x-med).abs().median()); peer["robust_z"]=0 if mad==0 else (x-med)/(1.4826*mad); peer["size_percentile"]=peer.k1_size
        parts.append(peer[["trade_id","size_percentile","robust_z","anomaly_score","is_anomaly","k1_size","k2_price","k3_burst","k4_concentration","k5_behavior"]])
    scored=pd.concat(parts,ignore_index=True); con.register("kalshi_scores",scored)
    con.execute("""UPDATE kalshi_weather_trades t SET size_percentile=s.size_percentile,robust_z=s.robust_z,anomaly_score=s.anomaly_score,is_anomaly=s.is_anomaly,k1_size=s.k1_size,k2_price=s.k2_price,k3_burst=s.k3_burst,k4_concentration=s.k4_concentration,k5_behavior=s.k5_behavior FROM kalshi_scores s WHERE t.trade_id=s.trade_id""")
    return int(scored.is_anomaly.sum())

def ingest_kalshi_weather(max_series=None,max_markets=1000):
    initialize(); client=KalshiClient(); series=client.all_series()
    weather=[s for s in series if _weather_series(s)]; weather=weather[:max_series] if max_series else weather; market_count=trade_count=0; tickers=[]
    with connect() as con:
        now=datetime.now(timezone.utc)
        con.execute("UPDATE kalshi_weather_markets SET status='stale' WHERE status IN ('open','active')")
        for candidate in series:
            wtype=classify_weather(candidate); external=str(candidate.get("ticker") or "")
            audit_id=__import__('hashlib').sha256(f"kalshi-series|{external}|{now.date()}".encode()).hexdigest()
            con.execute("INSERT OR REPLACE INTO market_discovery_audit VALUES (?,?,?,?,?,?,?,?)",[audit_id,"kalshi",now,external,candidate.get("title"),"ACCEPTED" if wtype else "REJECTED","Weather series metadata match" if wtype else "No meteorological series metadata match",wtype])
        for item in weather:
            result=client.markets(item.get("ticker"),"open",1000)
            for market in (result.get("markets",[]) if isinstance(result,dict) else []):
                # A weather-like series is only a discovery route. The individual
                # contract must independently contain explicit meteorological terms.
                wtype=classify_daily_rain_temperature(market)
                audit_id=__import__('hashlib').sha256(f"kalshi|{market.get('ticker')}|{now.date()}".encode()).hexdigest()
                con.execute("INSERT OR REPLACE INTO market_discovery_audit VALUES (?,?,?,?,?,?,?,?)",[audit_id,"kalshi",now,str(market.get("ticker") or ""),market.get("title"),"ACCEPTED" if wtype else "REJECTED","Weather series and contract metadata match" if wtype else "No meteorological contract metadata match",wtype])
                if not wtype: continue
                if market_count>=max_markets:break
                ticker=str(market.get("ticker")); tickers.append(ticker)
                con.execute("""INSERT OR REPLACE INTO kalshi_weather_markets
                    (ticker,event_ticker,series_ticker,title,subtitle,status,open_time,close_time,last_price,volume,open_interest,result,updated_at,weather_type)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",[
                    ticker,market.get("event_ticker"),item.get("ticker"),market.get("title"),market.get("subtitle") or market.get("yes_sub_title"),market.get("status"),_dt(market.get("open_time")),_dt(market.get("close_time")),_number(market.get("last_price_dollars")),_number(market.get("volume_fp")),_number(market.get("open_interest_fp")),market.get("result"),datetime.now(timezone.utc),wtype])
                source_name,source_url=official_weather_source(wtype)
                con.execute("INSERT OR REPLACE INTO authoritative_weather_sources VALUES (?,?,?,?,?)",[wtype,source_name,source_url,f"Independent reference for {wtype.lower()} contracts",datetime.now(timezone.utc)])
                trades=client.trades(ticker,10000)
                for trade in (trades.get("trades",[]) if isinstance(trades,dict) else []):
                    price=_number(trade.get("yes_price_dollars")); contracts=_number(trade.get("count_fp")); side=str(trade.get("taker_outcome_side") or trade.get("taker_side") or "").upper()
                    effective_price=price if side=="YES" else _number(trade.get("no_price_dollars"))
                    con.execute("""INSERT OR REPLACE INTO kalshi_weather_trades
                        (trade_id,ticker,timestamp_utc,outcome_side,book_side,price,contracts,notional,size_percentile,robust_z,anomaly_score,is_anomaly,is_block_trade,k1_size,k2_price,k3_burst,k4_concentration,k5_behavior)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",[trade.get("trade_id"),ticker,_dt(trade.get("created_time")),side,str(trade.get("taker_book_side") or "").upper(),effective_price,contracts,effective_price*contracts,None,None,None,False,bool(trade.get("is_block_trade")),None,None,None,None,None])
                    trade_count+=1
                market_count+=1
            if market_count>=max_markets:break
        anomalies=rescore_all_kalshi(con)
    return {"source":"kalshi","weather_series":len(weather),"markets":market_count,"trades":trade_count,"anomalies":anomalies}
