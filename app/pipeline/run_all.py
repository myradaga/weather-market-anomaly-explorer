from .ingest import ingest
from .build import build
from .score import score
def run_all(markets=25):
    result={"ingest":ingest(markets),"build":build(),"alerts":score()}
    try:
        from .weather_news import ingest_weather_context
        result["weather_context"]=ingest_weather_context()
    except Exception as exc:
        result["weather_context"]={"items":0,"errors":[str(exc)]}
    return result
