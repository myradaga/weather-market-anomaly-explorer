from app.db.database import connect
from app.scoring.composite import score_all
def score():
    with connect() as con: return score_all(con)

