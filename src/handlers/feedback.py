from utils.constants import *
from installation import *
from utils.ack_methods import *
from datetime import datetime

class Feedback :
    def __init__(self, slack_app, db):
        self.slack_app = slack_app 
        self.db = db
    
    def handle_save_feedback(self, ack, body, client, view, logger):
        input_data = view["state"]["values"]
        feedback = input_data["feedback"]["plain_text_input-action"]["value"]
        feedback = {
            "team_id": body["team"]["id"],
            "user_id": body["user"]["id"],
            "feedback": feedback,
            "created_on": datetime.utcnow(),
        }
        success_modal_ack(
            ack,
            body,
            view,
            logger,
            message="Thank you! I've saved your feedback",
            title="Send Feedback",
        )
        self.db.feedback.insert_one(feedback)

    def handle_send_feedback(self, ack, body, logger):
        ack()
        self.slack_app.client.views_open(
            token=get_token(body["team"]["id"]),
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "save_feedback",
                "title": {"type": "plain_text", "text": "Send Feedback"},
                "close": {"type": "plain_text", "text": "Close"},
                "submit": {
                    "type": "plain_text",
                    "text": "Send Feedback",
                    "emoji": True,
                },
                "blocks": [
                    {
                        "block_id": "feedback",
                        "type": "input",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "plain_text_input-action",
                            "multiline": True,
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "Nooks is a part of an ongoing research project and we would love to hear feedback from our initial users!",
                            "emoji": True,
                        },
                    },
                ],
            },
        )
