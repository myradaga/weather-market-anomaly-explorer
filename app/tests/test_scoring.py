import pytest
from app.scoring.composite import composite,alert_band
def test_missing_and_reliability():
    score,count=composite([1,None,.5],[1,1,.5]); assert score==pytest.approx(.99); assert count==2
def test_converging_signals_reinforce_and_conflicts_cancel():
    converging,_=composite([.8,.8,.8,.8],[1,1,1,1])
    conflict,_=composite([.9,.1,.5,.5],[1,1,1,1])
    assert converging>.95
    assert conflict==pytest.approx(.5)
def test_thresholds():
    assert alert_band(.92,5,True)=="PRIORITY"
    assert alert_band(.85,4)=="REVIEW"
    assert alert_band(.75,4)=="MONITOR"
    assert alert_band(.99,3)=="NONE"
    assert alert_band(.74,5,True)=="NONE"
