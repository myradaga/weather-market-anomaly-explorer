from app.config import get_settings
from .base import PublicClient
class ClobClient(PublicClient):
    source="clob"
    def __init__(self): super().__init__(get_settings().clob_base_url)
    def midpoint(self, token_id): return self.get("/midpoint", {"token_id":token_id})

