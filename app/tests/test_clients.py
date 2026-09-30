import httpx,pytest
from app.clients.base import PublicClient
def test_client_class_configuration(): assert PublicClient("https://example.test").base_url=="https://example.test"

def test_diversified_market_selection():
    from app.pipeline.ingest import diversified_markets
    events=[
        {"id":"sports","tags":[{"label":"Sports"}],"markets":[{"id":f"s{i}"} for i in range(10)]},
        {"id":"politics","tags":[{"label":"Politics"}],"markets":[{"id":f"p{i}"} for i in range(10)]},
        {"id":"crypto","tags":[{"label":"Crypto"}],"markets":[{"id":f"c{i}"} for i in range(10)]},
    ]
    selected=diversified_markets(events,6)
    assert len(selected)==6
    assert {row[2] for row in selected}=={"Sports","Politics","Crypto"}
    assert max(sum(1 for row in selected if row[0]["id"]==event) for event in ("sports","politics","crypto"))==2

def test_weather_classification_uses_event_metadata_and_avoids_team_names():
    from app.weather import classify_weather
    assert classify_weather({"title":"Daily high temperature in New York"},{"question":"Will it be above 90°F?"})=="Temperature"
    assert classify_weather({"category":"Climate and Weather"},{"title":"Seattle rainfall bracket"})=="Rain & precipitation"
    assert classify_weather({"title":"Miami Heat vs Boston Celtics"}) is None
    assert classify_weather({"title":"Will the minimum WTI price reach $60?"}) is None
    assert classify_weather({"title":"Will Brazil annual inflation be above 5%?"}) is None
    assert classify_weather({"title":"Will a ski resort open before December?"}) is None
    assert classify_weather({"title":"Will the temp in Los Angeles be above 70°?"})=="Temperature"

def test_weather_ingest_requires_a_meteorological_visible_question():
    from app.pipeline.ingest import is_weather_question
    assert is_weather_question("Will NYC rainfall exceed 2 inches?")
    assert not is_weather_question("Natural Disaster in 2026?")

def test_gamma_pagination_uses_offsets(monkeypatch):
    from app.clients.gamma import GammaClient
    client=GammaClient(); calls=[]
    def fake_events(limit,closed,tag_id,offset):
        calls.append(offset)
        return [{"id":offset+i} for i in range(limit)] if offset<4 else []
    monkeypatch.setattr(client,"events",fake_events)
    rows=client.all_events(page_size=2,max_events=10)
    assert len(rows)==4
    assert calls==[0,2,4]
