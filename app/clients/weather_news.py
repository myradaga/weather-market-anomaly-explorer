from app.clients.base import PublicClient
from app.config import get_settings


class NWSClient(PublicClient):
    source = "nws-alerts"

    def __init__(self):
        super().__init__(get_settings().nws_base_url)

    def active_alerts(self):
        return self.get("/alerts/active", {"status": "actual", "message_type": "alert"})


class GDELTNewsClient(PublicClient):
    source = "gdelt-weather-news"

    def __init__(self):
        super().__init__(get_settings().gdelt_base_url)

    def weather_articles(self, max_records=100, timespan="7d"):
        query='("daily temperature" OR "record temperature" OR rainfall OR precipitation OR "heavy rain") sourcecountry:US'
        return self.get("/doc", {
            "query": query,
            "mode": "artlist",
            "maxrecords": max_records,
            "timespan": timespan,
            "sort": "datedesc",
            "format": "json",
        })
