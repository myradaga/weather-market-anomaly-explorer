import pandas as pd
from app.features.kalshi_events import build_activity_events,candidate_market_match

def test_groups_flagged_trades_and_describes_impact():
    rows=[]
    for i,(minute,price,flag) in enumerate([(0,.30,False),(5,.45,True),(10,.55,True),(20,.35,False)]):
        rows.append(dict(trade_id=str(i),ticker="KX",timestamp_utc=pd.Timestamp("2026-01-01",tz="UTC")+pd.Timedelta(minutes=minute),price=price,notional=500,contracts=100,is_anomaly=flag,anomaly_score=.97,k1_size=.9,k2_price=.9,k3_burst=.9,k4_concentration=.9,k5_behavior=.9,close_time=pd.Timestamp("2026-01-02",tz="UTC"),title="Rain in NYC?",subtitle="Above 1 inch",event_ticker="E",weather_type="Rain"))
    result=build_activity_events(pd.DataFrame(rows))
    assert len(result)==1
    assert result.iloc[0].total_notional==2000
    assert result.iloc[0].evidence_grade=="HIGH"

def test_candidate_match_is_cautious():
    question,score=candidate_market_match("Rain in Miami in September?",["Rain in Miami during September?","Temperature in Boston?"])
    assert "Miami" in question and score>.4
