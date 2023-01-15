from utils.constants import *
from installation import *
from utils.ack_methods import *
import logging
from datetime import datetime
import pytz
import traceback
from utils.ui_text import SIGNUP_QUESTIONS, CONSENT_FORM



class Survey:
    def __init__(self, slack_app, db):
        self.slack_app = slack_app
        self.db = db 

    def is_survey_time(self, time_zone):
        tz = pytz.timezone(ALL_TIMEZONES[time_zone])
        timezone_time = datetime.now(tz).strftime("%m:%d:%Y:%H:%M")
        if timezone_time == "08:04:2022:14:30":
            return True
        return False

    def send_survey(self):
        for team_id in []:
            if not self.is_survey_time("EST"):
                return 

            token = get_token(team_id)
            all_users = list(db.member_vectors.find({"team_id": team_id}))
            for user in set([user["user_id"] for user in all_users]):
                try:
                    self.slack_app.client.chat_postMessage(
                        token=token,
                        link_names=True,
                        channel=user,
                        blocks=[
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Thanks for signing up for Nooks! Let us know what you about your experience here :)",
                                },
                            },
                            {
                                "type": "actions",
                                "elements": [
                                    {
                                        "type": "button",
                                        "action_id": "open_survey",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "Post Deployment Survey",
                                            "emoji": True,
                                        },
                                        "style": "primary",
                                    }
                                ],
                            },
                        ],
                    )

                except Exception as e:
                    logging.error(traceback.format_exc())


    def handle_post_completion_survey(self, ack, body, view, logger):
        all_questions = SIGNUP_QUESTIONS["Step 2"]
        question_blocks = [
            {
                "block_id": question,
                "type": "input",
                "label": {
                    "type": "plain_text",
                    "text": question,
                    "emoji": True,
                },
                "optional": False,
                "element": {
                    "type": "static_select",
                    "action_id": "select_input-action",
                    "options": [
                        {
                            "value": "1",
                            "text": {"type": "plain_text", "text": "1: Strongly Disagree"},
                        },
                        {"value": "2", "text": {"type": "plain_text", "text": "2"}},
                        {"value": "3", "text": {"type": "plain_text", "text": "3"}},
                        {"value": "4", "text": {"type": "plain_text", "text": "4"}},
                        {
                            "value": "5",
                            "text": {"type": "plain_text", "text": "5: Strongly Agree"},
                        },
                    ],
                },
            }
            for question in all_questions
        ]

        free_response = [
            {
                "block_id": "compare",
                "type": "input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "plain_text_input-action",
                    "multiline": True,
                },
                "optional": True, 
                "label": {
                    "type": "plain_text",
                    "text": "How would you compare the experience of having conversation in Nooks vs. outside?",
                    "emoji": True,
                },
            },
            {
                "block_id": "means",
                "type": "input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "plain_text_input-action",
                    "multiline": True,
                },
                "optional": True, 
                "label": {
                    "type": "plain_text",
                    "text": "How does Nooks compare with the other means you have to have conversations with the REUs?",
                    "emoji": True,
                },
            },
            {
                "block_id": "outside",
                "type": "input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "plain_text_input-action",
                    "multiline": True,
                },
                "optional": True, 
                "label": {
                    "type": "plain_text",
                    "text": "Did Nooks lead to conversations outside nooks?",
                    "emoji": True,
                },
            },
            {
                "block_id": "help",
                "type": "input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "plain_text_input-action",
                    "multiline": True,
                },
                "optional": True, 
                "label": {
                    "type": "plain_text",
                    "text": "Did nooks help you and in what way?",
                    "emoji": True,
                },
            },
        ]
        question_blocks += free_response
        ack()
        self.slack_app.client.views_open(
                    token=get_token(body["team"]["id"]),
            trigger_id=body["trigger_id"],
            view={

                "type": "modal",
                "callback_id": "submit_survey",
                "title": {"type": "plain_text", "text": "Post-Deployment Survey"},
                "submit": {"type": "plain_text", "text": "Submit"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": 
                question_blocks,
            }
        )

    def handle_submit_survey(self, ack, body, client, view, logger):
        success_modal_ack(
            ack,
            body,
            view,
            logger,
            message="Survey Submitted",
            title="Post-Deployment Survey",
        )
        input_data = view["state"]["values"]
        user = body["user"]["id"]
        new_member_info = {}
        for key in input_data:
            try:
                if "plain_text_input-action" in input_data[key]:
                    new_member_info[key] = input_data[key]["plain_text_input-action"][
                        "value"
                    ]
                elif "select_input-action" in input_data[key]:
                    new_member_info[key] = input_data[key]["select_input-action"][
                        "selected_option"
                    ]["value"]
                elif "user_select" in input_data[key]:
                    new_member_info[key] = input_data[key]["user_select"][
                        "selected_conversations"
                    ]
                else:
                    new_member_info[key] = input_data[key]
            except Exception as e:
                new_member_info[key] = []
                logging.error(traceback.format_exc())

        new_member_info["created_on"] = datetime.utcnow()
        self.db.member_vectors.update_one(
            {"user_id": user, "team_id": body["team"]["id"]},
            {"$set": {"post_completion": new_member_info}},
        )

        self.slack_app.client.chat_postMessage(
            token=get_token(body["team"]["id"]),
            link_names=True,
            channel=user,
            text="Hey there! Thank you for submitting the survey! ",
        )
