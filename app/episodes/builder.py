import hashlib
from datetime import timedelta
import pandas as pd

VERSION="episode-v1"
def build_episodes_frame(fills, gap_hours=24):
    if fills.empty: return pd.DataFrame()
    f=fills.copy(); f["timestamp_utc"]=pd.to_datetime(f.timestamp_utc,utc=True); f=f.sort_values(["wallet","market_id","timestamp_utc","fill_id"])
    rows=[]
    for (wallet,market), g in f.groupby(["wallet","market_id"],sort=True):
        groups=(g.timestamp_utc.diff()>pd.Timedelta(hours=gap_hours)).cumsum()
        for _, x in g.groupby(groups):
            entry=x.iloc[0]; exposure=x.signed_exposure.cumsum(); net=float(x.signed_exposure.sum()); total=float(x.notional.sum())
            eid=hashlib.sha256(f"{wallet}|{market}|{entry.timestamp_utc.isoformat()}|{VERSION}|{gap_hours}".encode()).hexdigest()
            rows.append(dict(episode_id=eid,wallet=wallet,market_id=market,direction="YES" if net>=0 else "NO",entry_time=entry.timestamp_utc,exit_time=x.iloc[-1].timestamp_utc,entry_price=float((x.price*x.notional).sum()/max(total,1e-9)),exit_price=float(x.iloc[-1].price),entry_notional=float(entry.notional),peak_open_notional=float(exposure.abs().max()),total_notional=total,trade_count=len(x),persistence=float(abs(net)/max(total,1e-9)),resolved=True,realized_pnl=0.0,data_quality_flags="",episode_version=f"{VERSION}-{gap_hours}h"))
    return pd.DataFrame(rows)

def rebuild(con,gap_hours=24):
    fills=con.execute("SELECT * FROM fills").fetchdf(); episodes=build_episodes_frame(fills,gap_hours)
    con.execute("DELETE FROM episodes")
    if not episodes.empty:
        # DuckDB TIMESTAMP is timezone-naive. Store UTC clock time without timezone
        # metadata so episode windows match the normalized fill timestamps exactly.
        for column in ("entry_time","exit_time"):
            episodes[column]=pd.to_datetime(episodes[column],utc=True).dt.tz_localize(None)
        con.register("episode_rows",episodes); con.execute("INSERT INTO episodes SELECT * FROM episode_rows")
        con.execute("UPDATE episodes e SET resolved=(m.status='resolved'), data_quality_flags=CASE WHEN m.status='resolved' THEN e.data_quality_flags ELSE concat_ws(';',nullif(e.data_quality_flags,''),'DQ05') END FROM markets m WHERE e.market_id=m.market_id")
        con.execute("""UPDATE episodes e SET realized_pnl=p.pnl FROM (
            SELECT e2.episode_id,sum(
              CASE WHEN upper(f.side)='BUY' THEN -f.notional ELSE f.notional END +
              CASE WHEN upper(f.outcome)=upper(m.resolved_token) THEN CASE WHEN upper(f.side)='BUY' THEN f.size ELSE -f.size END ELSE 0 END
            ) pnl
            FROM episodes e2 JOIN markets m USING(market_id) JOIN fills f ON f.market_id=e2.market_id AND f.wallet=e2.wallet AND f.timestamp_utc BETWEEN e2.entry_time AND e2.exit_time
            WHERE e2.resolved AND upper(m.resolved_token) IN ('YES','NO') GROUP BY e2.episode_id
        ) p WHERE e.episode_id=p.episode_id""")
    return len(episodes)
