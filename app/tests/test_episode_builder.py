import pandas as pd
from app.episodes.builder import build_episodes_frame
def rows(hours):
    return pd.DataFrame([dict(fill_id=str(i),wallet="w",market_id="m",timestamp_utc=pd.Timestamp("2025-01-01",tz="UTC")+pd.Timedelta(hours=h),price=.5,notional=10.,signed_exposure=10.) for i,h in enumerate(hours)])
def test_continuous_and_split():
    assert len(build_episodes_frame(rows([0,1,23]),24))==1
    assert len(build_episodes_frame(rows([0,25]),24))==2
def test_sensitivity_and_ordering():
    assert len(build_episodes_frame(rows([14,0,7]),6))==3
    assert len(build_episodes_frame(rows([49,0]),48))==2
