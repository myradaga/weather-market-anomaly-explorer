import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from app.clients.weather_news import GDELTNewsClient, NWSClient
from app.db.database import connect, initialize
from app.weather import classify_weather


def _dt(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(text.replace("Z", "+0000") if "%z" in fmt else text, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _id(source, url, published, title):
    return hashlib.sha256(f"{source}|{url}|{published}|{title}".encode()).hexdigest()


def ingest_weather_context(max_articles=100):
    initialize()
    now = datetime.now(timezone.utc)
    rows = []
    errors = []
    try:
        payload = NWSClient().active_alerts()
        for feature in payload.get("features", []):
            p = feature.get("properties") or {}
            title = p.get("headline") or p.get("event") or "National Weather Service alert"
            url = p.get("@id") or feature.get("id") or "https://api.weather.gov/alerts/active"
            published = _dt(p.get("sent") or p.get("effective") or p.get("onset")) or now
            location = p.get("areaDesc") or ""
            wtype = classify_weather(title, p.get("description"), p.get("instruction"))
            if wtype not in {"Temperature", "Rain & precipitation"}:
                continue
            rows.append((_id("NWS", url, published, title), "National Weather Service", "OFFICIAL_ALERT", title, url,
                         published, now, "weather.gov", wtype, location, 1.0, "live"))
    except Exception as exc:
        errors.append(f"NWS: {exc}")
    try:
        payload = GDELTNewsClient().weather_articles(max_records=max_articles)
        for article in payload.get("articles", []):
            title = article.get("title") or ""
            url = article.get("url") or ""
            if not title or not url:
                continue
            published = _dt(article.get("seendate")) or now
            wtype = classify_weather(title)
            if wtype not in {"Temperature", "Rain & precipitation"}:
                continue
            domain = article.get("domain") or urlparse(url).netloc
            rows.append((_id("GDELT", url, published, title), domain or "GDELT indexed news", "NEWS", title, url,
                         published, now, domain, wtype, "", 0.45, "live"))
    except Exception as exc:
        errors.append(f"GDELT: {exc}")
    with connect() as con:
        for row in rows:
            con.execute("INSERT OR REPLACE INTO weather_news_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", row)
        con.execute("DELETE FROM weather_news_items WHERE published_at < ?", [now - timedelta(days=30)])
    return {"items": len(rows), "official_alerts": sum(r[2] == "OFFICIAL_ALERT" for r in rows),
            "news_articles": sum(r[2] == "NEWS" for r in rows), "errors": errors}
