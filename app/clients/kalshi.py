from app.clients.base import PublicClient
from app.config import get_settings

class KalshiClient(PublicClient):
    source = "kalshi"
    def __init__(self): super().__init__(get_settings().kalshi_base_url)
    def series(self, category=None, cursor=None, limit=200):
        params={"include_volume":"true"}
        if category: params["category"]=category
        if cursor: params["cursor"]=cursor
        params["limit"]=limit
        return self.get("/series",params)
    def _all(self,path,key,params,max_records=10000):
        rows=[]; cursor=None; seen_cursors=set()
        while len(rows)<max_records:
            query=dict(params,limit=min(1000,max_records-len(rows)))
            if cursor: query["cursor"]=cursor
            payload=self.get(path,query); batch=payload.get(key,[]) if isinstance(payload,dict) else []
            rows.extend(batch); cursor=payload.get("cursor") if isinstance(payload,dict) else None
            if not cursor or not batch or cursor in seen_cursors: break
            seen_cursors.add(cursor)
        return rows
    def all_series(self): return self._all("/series","series",{"include_volume":"true"})
    def markets(self, series_ticker, status="open", limit=10000):
        return {"markets":self._all("/markets","markets",{"series_ticker":series_ticker,"status":status},limit)}
    def trades(self, ticker, limit=10000):
        return {"trades":self._all("/markets/trades","trades",{"ticker":ticker},limit)}
