from utils.constants import *
from installation import *
from utils.ack_methods import *
from datetime import datetime

class BeyondNooks:
    def __init__(self, slack_app, db):
        self.slack_app = slack_app 
        self.db = db

    def handle_send_dm(self, ack, body, client, view, logger):
        success_modal_ack(
            ack, body, view, logger, message="DM sent!", title="Connect beyond Nooks"
        )
        input_data = view["state"]["values"]
        to_user = view["private_metadata"]
        message = input_data["message"]["plain_text_input-action"]["value"]
        self.slack_app.client.chat_postMessage(
            token=get_token(body["team"]["id"]),
            link_names=True,
            channel=to_user,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message,
                    },
                }
            ],
        )


    def customize_dm_modal(self, ack, body, client, view, logger):
        ack()
        from_user = body["user"]["id"]
        to_user = body["actions"][0]["value"]
        response = self.slack_app.client.conversations_open(
            token=get_token(body["team"]["id"]),
            users=from_user + "," + to_user,
        )
        channel_id = response["channel"]["id"]
        self.slack_app.client.chat_postMessage(
            token=get_token(body["team"]["id"]),
            link_names=True,
            channel=channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Hey There!"},
                },
            ],
        )

    def handle_send_message(self, ack, body, client, view, logger):
        success_modal_ack(
            ack, body, view, logger, message="Message sent!", title="Connect beyond Nooks"
        )
        input_data = view["state"]["values"]
        from_user = body["user"]["id"]

        to_user = view["private_metadata"]
        message = input_data["message"]["plain_text_input-action"]["value"]

        personal_message_info = {
            "message": message,
            "from_user": from_user,
            "to_user": to_user,
            "team_id": body["team"]["id"],
            "created_on": datetime.utcnow(),
        }
        self.db.personal_message.insert_one(personal_message_info)
        self.slack_app.client.chat_postMessage(
            token=get_token(body["team"]["id"]),
            link_names=True,
            channel=to_user,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Hey @"
                        + client.users_info(
                            user=from_user, token=get_token(body["team"]["id"])
                        )["user"]["name"]
                        + " loved talking to you and would like to talk more. Here's what they said!",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ">" + message,
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "action_id": "customize_dm",
                            "value": from_user,
                            "text": {
                                "type": "plain_text",
                                "text": "Send them a DM!",
                                "emoji": True,
                            },
                            "style": "primary",
                        }
                    ],
                },
            ],
        )

    def handle_contact_person(self, ack, body, logger):
        ack()
        from_user = body["user"]["id"]
        to_user = body["actions"][0]["value"]

        self.slack_app.client.views_open(
            token=get_token(body["team"]["id"]),
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "send_message",
                "title": {"type": "plain_text", "text": "Connect beyond Nooks"},
                "close": {"type": "plain_text", "text": "Close"},
                "submit": {"type": "plain_text", "text": "Send", "emoji": True},
                "private_metadata": to_user,
                "blocks": [
                    {
                        "block_id": "message",
                        "type": "input",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "plain_text_input-action",
                            "multiline": True,
                            "initial_value": "Hey! Will you be free for a quick Zoom call anytime soon?",
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "Customize message",
                            "emoji": True,
                        },
                    },
                ],
            },
        )
