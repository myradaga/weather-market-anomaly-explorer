import hashlib, json, logging, uuid
from datetime import datetime, timezone
from pathlib import Path
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential
from app.config import get_settings
from app.db.database import connect

log = logging.getLogger(__name__)
class RetryableHTTP(Exception): pass

class PublicClient:
    source = "public"
    def __init__(self, base_url): self.base_url = base_url.rstrip("/"); self.settings = get_settings()

    @retry(retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, RetryableHTTP)), wait=wait_random_exponential(min=1,max=30), stop=stop_after_attempt(5), reraise=True)
    def get(self, path, params=None):
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.settings.request_timeout_seconds, follow_redirects=True) as client:
                response = client.get(url, params=params)
            if response.status_code == 429 or response.status_code in (500,502,503,504): raise RetryableHTTP(str(response.status_code))
            response.raise_for_status(); payload=response.json(); self._snapshot(path, params, response.status_code, payload, None); return payload
        except Exception as exc:
            if not isinstance(exc, RetryableHTTP): self._snapshot(path, params, getattr(getattr(exc,"response",None),"status_code",0), None, str(exc))
            raise

    def _snapshot(self, endpoint, params, status, payload, error):
        now=datetime.now(timezone.utc); body=json.dumps(payload, sort_keys=True, default=str) if payload is not None else ""
        sid=hashlib.sha256(f"{self.source}|{endpoint}|{now.isoformat()}|{body}".encode()).hexdigest()
        folder=self.settings.data_dir/"raw"/self.source/now.strftime("%Y-%m-%d"); folder.mkdir(parents=True,exist_ok=True)
        (folder/f"{sid}.json").write_text(json.dumps({"metadata":{"snapshot_id":sid,"source":self.source,"endpoint":endpoint,"retrieved_at_utc":now.isoformat(),"request_parameters":params or {},"http_status":status,"response_hash":hashlib.sha256(body.encode()).hexdigest()},"response":payload,"error":error},default=str))
        count=len(payload) if isinstance(payload,list) else len(payload.get("events",[])) if isinstance(payload,dict) else 0
        with connect() as con: con.execute("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?,?,?,?)",[sid,self.source,endpoint,now,json.dumps(params or {}),status,hashlib.sha256(body.encode()).hexdigest(),count,error])
        return sid

