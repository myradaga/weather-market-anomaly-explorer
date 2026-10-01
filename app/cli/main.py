import hashlib, json, shutil
from datetime import datetime,timezone
import typer
from app.config import get_settings
from app.db.database import initialize,connect
from app.pipeline.ingest import ingest as do_ingest
from app.pipeline.build import build as do_build
from app.pipeline.score import score as do_score
from app.pipeline.run_all import run_all as do_run_all
app=typer.Typer(no_args_is_help=True)
@app.command()
def init():
    path=initialize(); now=datetime.now(timezone.utc); run_id=hashlib.sha256(f"init|{now.isoformat()}".encode()).hexdigest()
    with connect() as con:
        con.execute("INSERT INTO pipeline_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",[run_id,now,now,"init","SUCCESS",0,0,0,0,0,0,"unknown",hashlib.sha256(str(get_settings().model_dump()).encode()).hexdigest()])
    print(f"Successful initialization: {path}")
@app.command()
def ingest(markets:int=typer.Option(25,"--markets"), active:bool=typer.Option(False,"--active",help="Ingest currently open markets instead of resolved markets"), weather_only:bool=typer.Option(False,"--weather-only",help="Use Polymarket's Weather tag and strict meteorological question matching")):
    try: print(json.dumps(do_ingest(markets,closed=not active,weather_only=weather_only),indent=2))
    except Exception as exc: print(f"Upstream API limitation/failure; local data remains intact: {exc}"); raise typer.Exit(2)
@app.command()
def build(): print(json.dumps(do_build(),indent=2))
@app.command()
def score(): print(f"alerts created: {do_score()}")
@app.command("ingest-kalshi-weather")
def ingest_kalshi_weather(markets:int=typer.Option(100,"--markets")):
    from app.pipeline.kalshi import ingest_kalshi_weather as run
    print(json.dumps(run(max_markets=markets),indent=2))
@app.command("ingest-weather-context")
def ingest_weather_context(articles:int=typer.Option(100,"--articles")):
    """Collect official NWS alerts and lower-weight weather news context."""
    from app.pipeline.weather_news import ingest_weather_context as run
    print(json.dumps(run(max_articles=articles),indent=2))
@app.command("run-all")
def run_all(markets:int=typer.Option(25,"--markets")): print(json.dumps(do_run_all(markets),indent=2))
@app.command()
def health():
    initialize(); s=get_settings(); result={"Application":"OK","Database":"OK","Data directory":"OK"}
    with connect() as con:
        for table in ("markets","fills","price_observations","episodes","public_events","alerts"): result[table]=con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        result["API failures"]=con.execute("SELECT count(*) FROM snapshots WHERE error IS NOT NULL").fetchone()[0]
    print(json.dumps(result,indent=2))
@app.command()
def backtest():
    from app.backtest.time_split import run
    with connect() as con: print(json.dumps(run(con),indent=2))
@app.command()
def export(format:str=typer.Option("parquet","--format")):
    initialize(); out=get_settings().data_dir/"exports"; out.mkdir(parents=True,exist_ok=True)
    with connect() as con:
        con.execute(f"COPY episodes TO '{out/'episodes.parquet'}' (FORMAT PARQUET)"); con.execute(f"COPY episode_features TO '{out/'features.parquet'}' (FORMAT PARQUET)"); con.execute(f"COPY alerts TO '{out/'alerts.parquet'}' (FORMAT PARQUET)"); con.execute(f"COPY alerts TO '{out/'alerts.csv'}' (HEADER, DELIMITER ',')"); con.execute(f"COPY public_events TO '{out/'public_events.csv'}' (HEADER, DELIMITER ',')"); con.execute(f"COPY reviews TO '{out/'reviews.csv'}' (HEADER, DELIMITER ',')")
    print(f"Exports written to {out}")
if __name__=="__main__": app()
