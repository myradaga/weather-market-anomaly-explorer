from app.config import get_settings
from .base import PublicClient
class DataAPIClient(PublicClient):
    source="data"
    def __init__(self): super().__init__(get_settings().data_api_base_url)
    def trades(self, condition_id, limit=10000):
        rows=[]; cursor=None
        while len(rows)<limit:
            params={"condition":condition_id,"limit":min(1000,limit-len(rows))}
            if cursor: params["cursor"]=cursor
            page=self.get("/v2/trades",params)
            batch=page.get("data",[]) if isinstance(page,dict) else page
            rows.extend(batch or [])
            pagination=page.get("pagination",{}) if isinstance(page,dict) else {}
            cursor=pagination.get("next_cursor")
            if not pagination.get("has_more") or not cursor: break
        return {"data":rows}
    def prices(self, token_id, start=None, end=None, bucket_seconds=None):
        p={"token_id":str(token_id)}
        if start:
            p.update(start=int(start.timestamp()),end=int(end.timestamp()))
            if bucket_seconds: p["bucket_seconds"]=bucket_seconds
        else:
            p["interval"]="max"
        return self.get("/v2/prices-history",p)
