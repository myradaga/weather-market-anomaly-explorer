import duckdb
from app.config import get_settings
from .schema import SCHEMA

def connect(read_only=False):
    s = get_settings(); s.ensure_dirs()
    return duckdb.connect(str(s.db_path), read_only=read_only)

def initialize():
    with connect() as con:
        con.execute(SCHEMA)
        for column in ("k1_size","k2_price","k3_burst","k4_concentration","k5_behavior"):
            con.execute(f"ALTER TABLE kalshi_weather_trades ADD COLUMN IF NOT EXISTS {column} DOUBLE")
        con.execute("ALTER TABLE markets ADD COLUMN IF NOT EXISTS weather_type VARCHAR")
        con.execute("ALTER TABLE kalshi_weather_markets ADD COLUMN IF NOT EXISTS weather_type VARCHAR")
        con.execute("""CREATE TABLE IF NOT EXISTS weather_news_items(
            item_id VARCHAR PRIMARY KEY, source_name VARCHAR, source_type VARCHAR, title VARCHAR, url VARCHAR,
            published_at TIMESTAMP, retrieved_at TIMESTAMP, source_domain VARCHAR, weather_type VARCHAR,
            location_text VARCHAR, reliability DOUBLE, raw_snapshot_id VARCHAR)""")
    return get_settings().db_path

def scalar(con, sql, params=None):
    row = con.execute(sql, params or []).fetchone()
    return row[0] if row else None
