# Polymarket Informed-Trading Detector

A fully local, single-container research prototype that converts public Polymarket activity into deterministic wallet × market episodes, five explainable anomaly signals, and a human review queue. It does **not** determine whether a wallet is an insider or whether conduct is illegal. Scores are research-prioritization signals.

## Manual setup

### 1. Install Docker

Install Docker Desktop on macOS, Docker Desktop + WSL2 where required on Windows, or Docker Engine + the Compose plugin on Linux.

```bash
docker --version
docker compose version
```

No host Python installation is required.

### 2. Clone/create the repository

```bash
git clone <repository-url>
cd polymarket-detector
```

If generated locally, place these files in a directory named `polymarket-detector`.

### 3. Build

```bash
docker compose build
```

### 4. Initialize

```bash
docker compose run --rm polymarket-detector python -m app.cli.main init
```

This creates the persistent directories, DuckDB tables, and pipeline metadata storage.

### 5. Test

```bash
docker compose run --rm polymarket-detector pytest -q
```

### 6. Start and stop

```bash
docker compose up -d
docker compose down
```

Open <http://localhost:8501>. Data remains in `./data`.

## First live-data workflow

```bash
docker compose exec polymarket-detector python -m app.cli.main ingest --markets 25
docker compose exec polymarket-detector python -m app.cli.main build
docker compose exec polymarket-detector python -m app.cli.main score
```

To ingest currently open markets across diversified categories instead of resolved history:

```bash
docker compose exec polymarket-detector python -m app.cli.main ingest --markets 100 --active
docker compose exec polymarket-detector python -m app.cli.main build
docker compose exec polymarket-detector python -m app.cli.main score
```

Open Streamlit and verify markets, trades, and episodes. Review candidate public events and manually confirm important timestamps; defensible event provenance requires this manual action. Then run the larger sample:

```bash
docker compose exec polymarket-detector python -m app.cli.main run-all --markets 1000
```

No cloud account, paid service, API credential, or production infrastructure is required. Upstream limitations are recorded and affected signals are suppressed rather than fabricated.

## Commands

`init`, `ingest --markets N`, `ingest --markets N --active`, `build`, `score`, `run-all --markets N`, `backtest`, `health`, and `export --format parquet` are available through `python -m app.cli.main`.

Exports include `episodes.parquet`, `features.parquet`, `alerts.csv`, `alerts.parquet`, `public_events.csv`, and `reviews.csv` under `data/exports`.

## Research safeguards

Raw HTTP responses and metadata are immutable files under `data/raw`. Fill and episode IDs are stable; ingestion is idempotent; wallet history is calculated as-of episode entry; missing modules are excluded rather than scored zero; and data-quality flags explain suppression. Public wallet identifiers are not enriched or deanonymized. Alert thresholds are provisional.

Official interface references: [market data overview](https://docs.polymarket.com/market-data/overview), [market discovery](https://docs.polymarket.com/market-data/discover-markets), [prices/order books](https://docs.polymarket.com/market-data/prices-order-books), and [analytics](https://docs.polymarket.com/market-data/public-analytics).
