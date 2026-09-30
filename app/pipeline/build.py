from app.db.database import connect
from app.config import get_settings
from app.episodes.builder import rebuild
from app.features.build import build_features
def build():
    with connect() as con: return {"episodes":rebuild(con,get_settings().episode_gap_hours),"features":build_features(con)}

