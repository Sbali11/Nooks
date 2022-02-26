
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import Installation
from pymongo import MongoClient
import os 
from functools import lru_cache
from dotenv import load_dotenv
import logging
load_dotenv()

MONGODB_LINK = os.environ["MONGODB_LINK"]

db = MongoClient(MONGODB_LINK).nooks_db

@lru_cache(maxsize=None)
def get_token(team_id):
    installation = db.tokens_2.find_one({"team_id": team_id})["installation"]
    if not installation:
        logging.error("Installation not found for " + team_id)
        return 0
    return installation["bot_token"]


class InstallationDB:
    def save(self, installation):
        self.db.tokens_2.update(
            {
                "team_id": installation.team_id,
                "user_id": installation.user_id,
            },
            {
                "team_id": installation.team_id,
                "user_id": installation.user_id,
                "time_zone": "America/New_York",
                "installation": vars(installation),
            },
            upsert=True,
        )
        pass

    def find_installation(
        self, enterprise_id=None, team_id=None, user_id=None, is_enterprise_install=None
    ):

        return Installation(
            **(self.db.tokens_2.find_one({"team_id": team_id})["installation"])
        )
    
    def __init__(self, db):
        self.db = db

