from app.clients.data_api import DataAPIClient
def fetch_prices(token_id): return DataAPIClient().prices(token_id)

