from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from utils.constants import *
from installation import *
from utils.ack_methods import *

ps = PorterStemmer()

class GuessGame:
    def __init__(self, slack_app, db):
        self.slack_app = slack_app
        self.db = db

    def handle_get_role(self, ack, body, respond):
        ack()
        user_id = body["user_id"]
        team_id = body["team_id"]
        channel_id = body["channel_id"]
        token = get_token(body["team_id"])
        nook_row = self.db.nooks.find_one({"channel_id": channel_id})
        if not nook_row:
            self.slack_app.client.chat_postEphemeral(
                user=body["user_id"],
                token=token,
                channel=channel_id,
                text="Oops! You can only call this command from a nook channel. ",
            )
            return
        allocated_row = db.allocated_roles_words.find_one(
            {"team_id": team_id, "channel_id": channel_id, "user_id": user_id}
        )

        if not allocated_row:

            word = list(
                self.db.random_words_collaborative.aggregate([{"$sample": {"size": 1}}])
            )[0]["word"]
            self.db.allocated_roles_words.insert_one(
                {
                    "team_id": team_id,
                    "user_id": user_id,
                    "word": word,
                    "channel_id": channel_id,
                }
            )
        else:
            word = allocated_row["word"]

        self.slack_app.client.chat_postEphemeral(
            user=body["user_id"],
            token=token,
            channel=body["channel_id"],
            text="Hey! You have a secret mission for today! Try to make use of this word in one of your messages: "
            + word,
        )

    def handle_word_guessed(self, ack, body, client, view, logger):
        ack()
        token = get_token(body["team"]["id"])
        team_id = body["team"]["id"]
        channel_id = view["private_metadata"]
        input_data = view["state"]["values"]
        member_id = input_data["member"]["member_selected"]["selected_option"]["value"]
        word = input_data["word"]["plain_text_input-action"]["value"]
        allocated_row = db.allocated_roles_words.find_one(
            {"team_id": team_id, "channel_id": channel_id, "user_id": member_id}
        )

        if ps.stem(word) == ps.stem(allocated_row["word"]):
            self.slack_app.client.chat_postMessage(
                token=token,
                link_names=True,
                channel=channel_id,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Yay! Looks like <@"
                            + body["user"]["id"]
                            + "> correctly guessed "
                            + "<@"
                            + member_id
                            + ">'s word ("
                            + word
                            + ")",
                        },
                    },
                ],
            )
        else:
            self.slack_app.client.chat_postMessage(
                token=token,
                link_names=True,
                channel=channel_id,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Oops! <@"
                            + body["user"]["id"]
                            + "> incorrectly guessed "
                            + "<@"
                            + member_id
                            + ">'s word as "
                            + word
                            + ". Does anyone else want to give a shot?",
                        },
                    },
                ],
            )
        self.db.guesses.insert_one(
            {
                "channel_id": channel_id,
                "user_id": body["user"]["id"],
                "for_id": member_id,
                "word": word,
                "team_id": team_id,
            }
        )


    def handle_word_said(self, ack, body, logger):
        ack()
        token = get_token(body["team"]["id"])
        channel_id = body["actions"][0]["value"]
        channel_members_list = list(
            self.db.allocated_roles_words.find(
                {"team_id": body["team"]["id"], "channel_id": channel_id}
            )
        )
        channel_members = [
            {
                "text": {
                    "type": "plain_text",
                    "text": self.slack_app.client.users_info(token=token, user=obj["user_id"])[
                        "user"
                    ]["name"],
                },
                "value": obj["user_id"],
            }
            for obj in channel_members_list
        ]
        self.slack_app.client.views_open(
            token=token,
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "word_guessed",
                "private_metadata": channel_id,
                "title": {"type": "plain_text", "text": "Guess Secret Word"},
                "close": {"type": "plain_text", "text": "Close"},
                "submit": {
                    "type": "plain_text",
                    "text": "Submit Guess",
                    "emoji": True,
                },
                "blocks": [
                    {
                        "block_id": "member",
                        "type": "input",
                        "label": {
                            "type": "plain_text",
                            "text": "Select member(only members allocated a role are shown here!)",
                        },
                        "optional": False,
                        "element": {
                            "action_id": "member_selected",
                            "type": "static_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select member",
                            },
                            "options": channel_members,
                        },
                    },
                    {
                        "block_id": "word",
                        "type": "input",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "plain_text_input-action",
                        },
                        "optional": False,
                        "label": {
                            "type": "plain_text",
                            "text": "What word do you think they sneaked in?",
                            "emoji": True,
                        },
                    },
                ],
            },
        )

