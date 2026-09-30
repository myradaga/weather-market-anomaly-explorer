import json, numpy as np, pandas as pd
from .size import robust_z, percentile
from .behavior import anomaly_percentiles

FEATURE_VERSION="features-v2-shrinkage-liquidity"; MODEL_VERSION="isolation-forest-v2-peer-2pct"
def build_features(con):
    e=con.execute("SELECT e.*,coalesce(m.weather_type,'Other weather') weather_type FROM episodes e JOIN markets m USING(market_id) WHERE m.eligible ORDER BY e.entry_time").fetchdf()
    if e.empty: con.execute("DELETE FROM episode_features"); return 0
    m=con.execute("SELECT market_id, volume, unique_traders FROM markets").fetchdf().set_index("market_id")
    events=con.execute("SELECT market_id,event_time_utc,confidence,source_type,earliest_time_utc,latest_time_utc FROM public_events WHERE verified AND NOT rejected ORDER BY event_time_utc").fetchdf()
    event_map={mid:g for mid,g in events.groupby('market_id')} if len(events) else {}
    market_percentiles={}; market_z={}
    for market,g in e.groupby("market_id"):
        pct=g.total_notional.rank(method="max",pct=True)
        z=robust_z(g.total_notional)
        market_percentiles.update(dict(zip(g.episode_id,pct)))
        market_z.update(dict(zip(g.episode_id,z)))
    flow=con.execute("SELECT market_id,wallet,sum(notional) wallet_notional FROM fills GROUP BY market_id,wallet").fetchdf()
    totals=con.execute("SELECT market_id,sum(notional) total_notional,sum(signed_exposure) signed_exposure,count(*) fill_count FROM fills GROUP BY market_id").fetchdf().set_index("market_id")
    wallet_flow={(r.market_id,r.wallet):float(r.wallet_notional) for _,r in flow.iterrows()}
    liquidity=totals.reset_index()[["market_id","total_notional","fill_count"]].copy()
    liquidity["bucket"]=pd.qcut(liquidity.total_notional.rank(method="first"),q=min(10,len(liquidity)),labels=False,duplicates="drop") if len(liquidity)>1 else 0
    share_frame=flow.merge(liquidity,on="market_id",how="left"); share_frame["raw_share"]=share_frame.wallet_notional/share_frame.total_notional.clip(lower=1e-9)
    share_frame["share_percentile"]=share_frame.groupby("bucket").raw_share.rank(method="max",pct=True)
    share_percentile={(r.market_id,r.wallet):float(r.share_percentile) for _,r in share_frame.iterrows()}
    wallet_history={}
    rows=[]
    for _,r in e.iterrows():
        prior=pd.DataFrame(wallet_history.get(r.wallet,[]))
        mp=float(market_percentiles[r.episode_id]); wp=percentile(r.total_notional,prior.total_notional) if len(prior)>=3 else mp
        volume=float(m.loc[r.market_id,"volume"]) if r.market_id in m.index else 0
        lead=None; s2=None; q2=0; suppression=[]
        evs=event_map.get(r.market_id)
        if evs is not None:
            forecasts=evs[evs.source_type=="FORECAST_UPDATE"]
            prior_forecasts=forecasts[pd.to_datetime(forecasts.event_time_utc)<=pd.to_datetime(r.entry_time)]
            if len(prior_forecasts):
                ev=prior_forecasts.iloc[-1]; since=(pd.to_datetime(r.entry_time)-pd.to_datetime(ev.event_time_utc)).total_seconds()/3600
                # Immediate post-update trading is expected; unexplained activity grows
                # more informative as time since the last public update increases.
                s2=float(1-np.exp(-max(0,since)/6)); lead=since; q2=1 if ev.confidence=="HIGH" else .7
            else:
                ev=evs.iloc[-1]; lead=(pd.to_datetime(ev.event_time_utc)-pd.to_datetime(r.entry_time)).total_seconds()/3600
                s2=float(np.exp(-max(0,lead)/72)) if lead>0 else 0; q2=.25
                suppression.append("S2: no forecast-issuance history; close-time proxy down-weighted")
        else: suppression.append("S2: no verified public event")
        prior_resolved=prior[prior.resolved==True] if len(prior) else prior; n=len(prior_resolved)
        median_prior=float(prior_resolved.total_notional.median()) if n else 0
        mean_roi=float((prior_resolved.realized_pnl/prior_resolved.total_notional.clip(lower=1)).mean()) if n else 0
        shrink=n/(n+7) if n else 0
        s3=float(np.clip(.5+.5*np.tanh(2*mean_roi*shrink),0,1)) if n else None
        q3=shrink
        if n<3: suppression.append("S3: thin history strongly shrunk toward neutral")
        stat=totals.loc[r.market_id] if r.market_id in totals.index else None; denom=float(stat.total_notional) if stat is not None else 0
        wallet_share=wallet_flow.get((r.market_id,r.wallet),0)/denom if denom else 0
        imbalance=float(stat.signed_exposure/denom) if denom else 0
        conditioned_share=share_percentile.get((r.market_id,r.wallet),.5)
        s4=min(1,max(0,(abs(imbalance)+conditioned_share)/2)); q4=1 if stat is not None and stat.fill_count>=20 and denom>=1000 else 0
        if q4==0:suppression.append("S4: market below 20-trade / $1,000 liquidity floor")
        rows.append(dict(episode_id=r.episode_id,wallet_age_days=float((pd.to_datetime(r.entry_time)-pd.to_datetime(prior.entry_time.min())).total_seconds()/86400) if n else 0,prior_episode_count=n,prior_volume=float(prior.total_notional.sum()) if n else 0,prior_notional_median=float(prior.total_notional.median()) if n else None,prior_notional_p95=float(prior.total_notional.quantile(.95)) if n else None,prior_win_rate=float((prior.realized_pnl>0).mean()) if n else None,prior_realized_pnl=float(prior.realized_pnl.sum()) if n else 0,prior_category_count=0,prior_market_count=int(prior.market_id.nunique()) if n else 0,episode_notional=r.total_notional,max_open_exposure=r.peak_open_notional,market_volume_share=r.total_notional/volume if volume else None,market_size_percentile=mp,wallet_size_percentile=wp,market_robust_z=float(market_z[r.episode_id]),wallet_robust_z=None,lead_hours=lead,signed_move_15m=None,signed_move_1h=None,signed_move_6h=None,signed_move_24h=None,timing_percentile=s2,timestamp_sensitivity="NOT_TESTED",market_order_imbalance=imbalance,wallet_directional_share=wallet_share,pre_move_volume_share=wallet_share,n_bets=n,expected_wins=None,actual_wins=None,excess_wins=None,expected_pnl=None,actual_pnl=float(prior.realized_pnl.sum()) if n else 0,profit_z=None,p_value=None,q_value=None,raw_anomaly_score=None,anomaly_percentile=None,top_3_contributors="",model_version=MODEL_VERSION,feature_version=FEATURE_VERSION,s1=max(mp,wp),s2=s2,s3=s3,s4=s4,s5=None,q1=1,q2=q2,q3=q3,q4=q4,q5=1,suppression_reasons="; ".join(suppression)))
        wallet_history.setdefault(r.wallet,[]).append(r.to_dict())
    df=pd.DataFrame(rows); behavior_cols=df[["episode_notional","market_size_percentile","wallet_directional_share","prior_episode_count"]].fillna(0)
    normalized=behavior_cols.copy()
    for col in normalized: normalized[col]=normalized.groupby(e.weather_type.reset_index(drop=True))[col].rank(method="average",pct=True)
    pct,model=anomaly_percentiles(normalized,contamination=.02); df["raw_anomaly_score"]=pct; df["anomaly_percentile"]=pct; df["s5"]=pct
    for i in df.index:
        deviations=(normalized.loc[i]-.5).abs().sort_values(ascending=False).head(3); df.loc[i,"top_3_contributors"]=json.dumps([f"{name}:{value:.3f}" for name,value in deviations.items()])
    con.execute("DELETE FROM episode_features"); con.register("feature_rows",df); con.execute("INSERT INTO episode_features SELECT * FROM feature_rows"); return len(df)
