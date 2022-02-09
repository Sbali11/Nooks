
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import Installation
from pymongo import MongoClient
import os 

from functools import lru_cache

class InstallationDB:
    def save(self, installation):
        # logging.info(vars(installation))
        self.db.tokens_2.update(
            {
                "team_id": installation.team_id,
                "user_id": installation.user_id,
            },
            {
                "team_id": installation.team_id,
                "user_id": installation.user_id,
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


@lru_cache(maxsize=None)
def get_token(team_id):
    # return "xoxb-2614289134036-2605490949174-dJLZ9jgZKSNEd96SjcdTtDAM"
    return db.tokens_2.find_one({"team_id": team_id})["installation"]["bot_token"]


def get_bot_id(team_id):
    # return "xoxb-2614289134036-2605490949174-dJLZ9jgZKSNEd96SjcdTtDAM"
    return db.tokens_2.find_one({"team_id": team_id})["installation"]["bot_user_id"]
