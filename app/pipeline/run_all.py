from .ingest import ingest
from .build import build
from .score import score
def run_all(markets=25): return {"ingest":ingest(markets),"build":build(),"alerts":score()}

