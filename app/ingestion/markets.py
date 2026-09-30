from app.clients.gamma import GammaClient
def fetch_markets(limit=25): return GammaClient().events(limit=limit,closed=True)

