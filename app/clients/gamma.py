from app.config import get_settings
from .base import PublicClient
class GammaClient(PublicClient):
    source="gamma"
    def __init__(self): super().__init__(get_settings().gamma_base_url)
    def events(self, limit=25, closed=True, tag_id=None, offset=0):
        params={"limit":limit,"offset":offset,"closed":str(closed).lower(),"order":"volume","ascending":"false"}
        if tag_id is not None: params["tag_id"]=tag_id
        return self.get("/events",params)
    def all_events(self, closed=True, tag_id=None, page_size=100, max_events=5000):
        rows=[]
        while len(rows)<max_events:
            page=self.events(min(page_size,max_events-len(rows)),closed,tag_id,len(rows))
            page=page.get("events",page.get("data",[])) if isinstance(page,dict) else page
            if not page: break
            rows.extend(page)
            if len(page)<page_size: break
        return rows
