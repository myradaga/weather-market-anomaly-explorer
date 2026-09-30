from app.clients.data_api import DataAPIClient
def fetch_trades(market,limit=10000): return DataAPIClient().trades(market,limit)

