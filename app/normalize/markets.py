import json
def token_ids(market):
    raw=market.get("clobTokenIds") or market.get("clob_token_ids") or []
    if isinstance(raw,str):
        try: raw=json.loads(raw)
        except Exception: raw=[]
    return (str(raw[0]),str(raw[1])) if len(raw)>=2 else (None,None)

