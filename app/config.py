from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    data_dir: Path = Path("/app/data")
    db_path: Path = Path("/app/data/polymarket.duckdb")
    gamma_base_url: str = "https://gamma-api.polymarket.com"
    data_api_base_url: str = "https://data-api.polymarket.com"
    clob_base_url: str = "https://clob.polymarket.com"
    kalshi_base_url: str = "https://external-api.kalshi.com/trade-api/v2"
    nws_base_url: str = "https://api.weather.gov"
    gdelt_base_url: str = "https://api.gdeltproject.org/api/v2/doc"
    request_timeout_seconds: float = 30
    max_retries: int = 5
    concurrency: int = 4
    episode_gap_hours: int = 24
    min_market_traders: int = 50
    min_market_notional: float = 25_000
    price_bucket_seconds: int = 300
    trade_limit: int = 2000
    s1_weight: float = 1
    s2_weight: float = 1
    s3_weight: float = 1
    s4_weight: float = 1
    s5_weight: float = 1

    def ensure_dirs(self):
        for name in ("raw", "normalized", "parquet", "snapshots", "exports"):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)

@lru_cache
def get_settings() -> Settings:
    return Settings()
