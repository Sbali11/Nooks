from utils.constants import *
from installation import *
from utils.ack_methods import *
import logging

class Swiping:
    def __init__(self, slack_app, db, nooks_home):
        self.slack_app = slack_app
        self.db = db
        self.nooks_home = nooks_home
    
    def nook_int(self, ack, body, logger):
        ack()
        user_id = body["user"]["id"]
        cur_pos = int(body["actions"][0]["value"])
        try:
            user_nook = self.nooks_home.suggested_nooks[body["team"]["id"]][cur_pos]
            self.db.user_swipes.update_one(
                {"user_id": user_id, "team_id": body["team"]["id"]},
                {"$set": {"cur_pos": cur_pos + 1}},
            )
            self.db.nooks.update(
                {"_id": user_nook["_id"], "team_id": body["team"]["id"]},
                {"$push": {"swiped_right": user_id}},
            )
        except Exception as e:
            logging.info(e)

        self.nooks_home.update_home_tab(
            self.slack_app.client,
            {"user": user_id, "view": {"team_id": body["team"]["id"]}},
            token=get_token(body["team"]["id"]),
        )

    def nook_not_int(self, ack, body, logger):
        ack()
        user_id = body["user"]["id"]
        cur_pos = int(body["actions"][0]["value"])
        try:
            user_nook = self.nooks_home.suggested_nooks[body["team"]["id"]][cur_pos]
            self.db.user_swipes.update_one(
                {"user_id": user_id, "team_id": body["team"]["id"]},
                {"$set": {"cur_pos": cur_pos + 1}},
            )
            self.db.nooks.update(
                {"_id": user_nook["_id"], "team_id": body["team"]["id"]},
                {"$push": {"swiped_left": user_id}},
            )
            self.nooks_home.update_home_tab(
                self.slack_app.client,
                {"user": user_id, "view": {"team_id": body["team"]["id"]}},
                token=get_token(body["team"]["id"]),
            )
        except Exception as e:
            logging.info(e)
