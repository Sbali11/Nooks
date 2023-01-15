from utils.constants import *
from installation import *
from utils.ack_methods import *
import logging
from utils.ui_text import SIGNUP_QUESTIONS, CONSENT_FORM
import ast 
from datetime import datetime
import traceback

class Signup:
    def __init__(self, slack_app, db, nooks_home, nooks_alloc):
        self.slack_app = slack_app
        self.db = db
        self.nooks_home = nooks_home
        self.nooks_alloc = nooks_alloc

    def get_consent_blocks(self):
        consent_details = CONSENT_FORM
        consent_blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Study Consent Form"},
            },
        ]
        for detail in consent_details:
            consent_blocks.append(
                {
                    "block_id": detail,
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*" + detail + "*\n" + consent_details[detail],
                    },
                }
            )

            consent_blocks.append({"type": "divider"})

        consent_blocks.append(
            {
                "type": "input",
                "block_id": "consent",
                "element": {
                    "type": "checkboxes",
                    "action_id": "checkboxes_input-action",
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "I'm age 18 or older",
                                "emoji": True,
                            },
                            "value": "old_enough",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "I have read and understand the information above",
                                "emoji": True,
                            },
                            "value": "read_all",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "I want to participate in this research and continue with the application ",
                                "emoji": True,
                            },
                            "value": "want_to_participate",
                        },
                    ],
                },
                "label": {
                    "type": "plain_text",
                    "text": "Please read the details above and respond to the questions below to continue",
                    "emoji": True,
                },
            }
        )
        return consent_blocks

    def handle_signup(self, ack, body, client, view, logger):
        success_modal_ack(
            ack, body, view, logger, message="Sign up successful!", title="Sign Up!"
        )
        input_data = view["state"]["values"]
        input_data.update(ast.literal_eval(body["view"]["private_metadata"]))
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

        new_member_info["user_id"] = user
        new_member_info["team_id"] = body["team"]["id"]
        new_member_info["created_on"] = datetime.utcnow()
        self.db.member_vectors.insert_one(new_member_info)
        self.db.blacklisted.update_one(
            {"user_id": user, "team_id": body["team"]["id"]},
            {
                "$set": {
                    "user_id": user,
                    "team_id": body["team"]["id"],
                    "black_list": new_member_info["black_list"],
                }
            },
            upsert=True,
        )

        for member in new_member_info["black_list"]:
            blacklist_row = self.db.blacklisted.find_one(
                {"user_id": member, "team_id": body["team"]["id"]}
            )
            if blacklist_row and "blacklisted_from" in blacklist_row:
                self.db.blacklisted.update_one(
                    {"user_id": member, "team_id": body["team"]["id"]},
                    {"$push": {"blacklisted_from": user}},
                )
            else:
                self.db.blacklisted.update_one(
                    {"user_id": member, "team_id": body["team"]["id"]},
                    {
                        "$set": {
                            "user_id": member,
                            "team_id": body["team"]["id"],
                            "blacklisted_from": [user],
                            "black_list": [],
                        }
                    },
                    upsert=True,
                )
        self.nooks_alloc._create_members(team_id=body["team"]["id"])
        self.nooks_home.update_home_tab(
            self.slack_app.client,
            {"user": user, "view": {"team_id": body["team"]["id"]}},
            token=get_token(body["team"]["id"]),
        )

        self.slack_app.client.chat_postMessage(
            token=get_token(body["team"]["id"]),
            link_names=True,
            channel=user,
            text="You're all set! Create your first nook! ",
        )

    def handle_tell_me_more(self, ack, body, logger):
        ack()
        user = body["user"]["id"]
        self.slack_app.client.views_open(
            token=get_token(body["team"]["id"]),
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "Tell me More!"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*What are nooks?*\nNooks are _anonymously created short-lived conversations_ (last for only a day) around specific topics.\n ",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Sounds fun! How can I join a nook?*\nI will be back everyday with a list of nooks suggested by your coworkers, just click interested whenever you would want to join in on the conversation. Using some secret optimizations:test_tube: that aim to aid workplace connectedness, I'll allocate one nook to you the next day. \nPro Tip: Click interested on more nooks for more optimal results!",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*How can I create a nook?*\nAfter we've completed your onboarding, just head over to the NooksBot Home page to get started.",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Would love some more details!*\nFor detailed onboarding instructions, you can visit https://nooks.vercel.app/member-onboarding!",
                        },
                    },
                ],
            },
        )

    def handle_learn_more(self, ack, body, logger):
        ack()

        user = body["user"]["id"]
        self.slack_app.client.views_open(
            token=get_token(body["team"]["id"]),
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "signup_step_0",
                "title": {"type": "plain_text", "text": "Learn More!"},
                "submit": {"type": "plain_text", "text": "Sign Up!"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*What are nooks?*\nNooks are _anonymously created short-lived conversations_ (last for only a day) around specific topics.\n ",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Sounds fun! How can I join a nook?*\nI will be back everyday with a list of nooks suggested by your coworkers, just click interested whenever you would want to join in on the conversation. Using some secret optimizations:test_tube: that aim to aid workplace connectedness, I'll allocate one nook to you the next day. \nPro Tip: Click interested on more nooks for more optimal results!",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*How can I create a nook?*\nAfter we've completed your onboarding, just head over to the NooksBot Home page to get started.",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Would love some more details!*\nFor detailed onboarding instructions, you can visit https://nooks.vercel.app/member-onboarding!",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Note: I'm created as a part of a research project and I would be collecting data, however at no point would your details be disclosed. Participating and completing the signup counts as consent for this data collection(no data is collected otherwise). For more details regarding what data is collected, click here   ",
                        },
                    },
                ],
            },
        )

    def signup_modal(self, ack, body, logger):
        ack()
        res = self.slack_app.client.views_open(
            token=get_token(body["team"]["id"]),
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "signup_step_1",
                "title": {"type": "plain_text", "text": "Sign Up!"},
                "submit": {"type": "plain_text", "text": "Next"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": self.get_consent_blocks(),
            },
        )

    def signup_modal_step_0(self, ack, body, view, logger):
        ack(
            response_action="update",
            view={
                "type": "modal",
                "callback_id": "signup_step_1",
                "title": {"type": "plain_text", "text": "Sign Up!"},
                "submit": {"type": "plain_text", "text": "Next"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": self.get_consent_blocks(),
            },
        )

    def signup_modal_step_1(self, ack, body, view, logger):
        input_data = view["state"]["values"]

        if len(input_data["consent"]["checkboxes_input-action"]["selected_options"]) < 3:
            ack(
                response_action="update",
                view={
                    "type": "modal",
                    "title": {"type": "plain_text", "text": "Sign Up!"},
                    "close": {"type": "plain_text", "text": "Close"},
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "Oops! You need to select all the options on the previous page to be eligible. ",
                            },
                        }
                    ],
                },
            )
            return

        all_questions = SIGNUP_QUESTIONS["Step 1"]
        team_row = self.db.tokens_2.find_one({"team_id": body["team"]["id"]})
        if "locations" not in team_row:
            current_locations = []
        else:
            current_locations = team_row["locations"]
        question_blocks = []
        for question in all_questions:
            question_blocks.append(
                {
                    "type": "input",
                    "block_id": question,
                    "label": {
                        "type": "plain_text",
                        "text": question,
                    },
                    "optional": False,
                    "element": {
                        "type": "static_select",
                        "action_id": "select_input-action",
                        "options": [
                            {"value": value, "text": {"type": "plain_text", "text": value}}
                            for value in all_questions[question]
                        ],
                    },
                }
            )
            if question == "Gender":
                question_blocks.append(
                    {
                        "block_id": "gender_self_describe",
                        "type": "input",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "plain_text_input-action",
                        },
                        "optional": True,
                        "label": {
                            "type": "plain_text",
                            "text": "If you prefer to self-describe, please elaborate here.",
                            "emoji": True,
                        },
                    },
                )

        # TODO change to only channel members
        top_interacted_block = {
            "block_id": "top_members",
            "type": "input",
            "label": {
                "type": "plain_text",
                "text": "Who are the top 5 people you talk the most with?",
            },
            "optional": False,
            "element": {
                "action_id": "user_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select the top 5 people you interact with",
                    "emoji": True,
                },
                "filter": {"include": ["im"], "exclude_bot_users": True},
                "max_selected_items": 5,
                "type": "multi_conversations_select",
            },
        }

        if current_locations:
            current_location_block = {
                "type": "input",
                "block_id": "Location",
                "label": {
                    "type": "plain_text",
                    "text": "Select your location(if you can't see your location, ask the user who installed the Nooks Bot to add it in!: this should be mentioned on your home page)",
                },
                "optional": False,
                "element": {
                    "type": "static_select",
                    "action_id": "select_input-action",
                    "options": [
                        {
                            "value": location,
                            "text": {"type": "plain_text", "text": location},
                        }
                        for location in current_locations
                    ],
                },
            }
            question_blocks.append(current_location_block)
        question_blocks.append(top_interacted_block)

        # TODO check if member is already in database?
        ack(
            response_action="update",
            view={
                "type": "modal",
                "callback_id": "signup_step_2",
                "title": {"type": "plain_text", "text": "Sign Up!"},
                "submit": {"type": "plain_text", "text": "Next"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "To help me optimize your Nooks experience, tell me a bit about yourself! P.S Your answers won't be shown to your teammates and are only used to match you to an optimal nook. ",
                        },
                    }
                ]
                + question_blocks,
            },
        )

    def signup_modal_step_2(self, ack, body, view, logger):
        user = body["user"]["id"]
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

        ack(
            response_action="update",
            view={
                "type": "modal",
                "callback_id": "signup_step_3",
                "private_metadata": str(view["state"]["values"]),
                "title": {"type": "plain_text", "text": "Sign Up!"},
                "submit": {"type": "plain_text", "text": "Next"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Some more :)",
                        },
                    }
                ]
                + question_blocks,
            },
        ),

    def signup_modal_step_3(self, ack, body, view, logger):
        input_data = view["state"]["values"]
        input_data.update(ast.literal_eval(body["view"]["private_metadata"]))
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
                    logging.info(input_data[key])
            except Exception as e:
                new_member_info[key] = []
                logging.error(traceback.format_exc())
        ack(
            response_action="update",
            view={
                "type": "modal",
                "callback_id": "add_member",
                "private_metadata": str(new_member_info),
                "title": {"type": "plain_text", "text": "Sign Up!"},
                "submit": {"type": "plain_text", "text": "Submit"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "block_id": "black_list",
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Are there any members you *don't* want to interact with?",
                        },
                        "accessory": {
                            "action_id": "user_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select any users you *don't* want included in conversations with you",
                                "emoji": True,
                            },
                            "filter": {"include": ["im"], "exclude_bot_users": True},
                            "type": "multi_conversations_select",
                        },
                    },
                ],
            },
        ),
