def test_database_initialization(tmp_path,monkeypatch):
    monkeypatch.setenv("DATA_DIR",str(tmp_path)); monkeypatch.setenv("DB_PATH",str(tmp_path/"test.duckdb"))
    from app.config import get_settings; get_settings.cache_clear()
    from app.db.database import initialize,connect
    initialize()
    with connect() as con:
        assert con.execute("SELECT count(*) FROM markets").fetchone()[0]==0
        assert con.execute("SELECT count(*) FROM alerts").fetchone()[0]==0
