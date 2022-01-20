from functools import lru_cache
import os
import logging
import atexit
import random
import collections
import traceback

from datetime import datetime, timezone
from utils import NooksHome, NooksAllocation, get_member_vector
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from pymongo import MongoClient
from bson import ObjectId
import numpy as np
from flask_apscheduler import APScheduler
import ast
from constants import *

# set configuration values
class Config:

    SCHEDULER_API_ENABLED = True


logging.basicConfig(level=logging.INFO)


# load environment variables
load_dotenv()
NUM_MEMBERS = 2
MEMBER_FEATURES = 2
MAX_STORIES_GLOBAL = 10
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
MONGODB_LINK = os.environ["MONGODB_LINK"]
REDIRECT_URI = os.environ["REDIRECT_URI"]
CLIENT_ID = os.environ["SLACK_CLIENT_ID"]

db = MongoClient(MONGODB_LINK).nooks_db

from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import Installation


class InstallationDB:
    def save(self, installation):
        # logging.info(vars(installation))
        db.tokens.insert_one(
            {
                "installation": vars(installation),
                "team_id": installation.team_id,
            }
        )
        pass

    def find_installation(
        self, enterprise_id=None, team_id=None, user_id=None, is_enterprise_install=None
    ):

        return Installation(
            **(db.tokens.find_one({"team_id": team_id})["installation"])
        )


@lru_cache(maxsize=None)
def get_token(team_id):
    return db.tokens.find_one({"team_id": team_id})["installation"]["bot_token"]


installation_store = InstallationDB()


oauth_settings = OAuthSettings(
    install_path="/slack/install",
    redirect_uri_path="/slack/oauth_redirect",
    client_id=CLIENT_ID,
    client_secret=os.environ["CLIENT_SECRET"],
    scopes=[
        "app_mentions:read",
        "channels:history",
        "channels:manage",
        "channels:read",
        "chat:write",
        "commands",
        "groups:history",
        "groups:read",
        "groups:write",
        "im:history",
        "im:read",
        "im:write",
        "mpim:read",
        "mpim:write",
        "users.profile:read",
        "users:read",
        "files:write",
        "files:read",
        "incoming-webhook&user_scope=channels:read",
        "channels:write",
        "chat:write",
        "files:read",
        "im:write",
        "users:read",
        "mpim:write",
        "groups:write",
    ],
    installation_store=installation_store,
)


slack_app = App(
    signing_secret=os.environ["SLACK_SIGNING_SECRET"], oauth_settings=oauth_settings
)


@slack_app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()


@slack_app.view("new_story")
def handle_new_story(ack, body, client, view, logger):
    ack()
    input_data = view["state"]["values"]
    user = body["user"]["id"]
    title = input_data["title"]["plain_text_input-action"]["value"]
    desc = input_data["desc"]["plain_text_input-action"]["value"]
    banned = input_data["banned"]["text1234"]["selected_users"]
    new_story_info = {
        "team_id": body["team"]["id"],
        "title": title,
        "creator": user,
        "description": desc,
        "banned": banned,
        "status": "suggested",
        "created_on": datetime.utcnow(),
        "swiped_right": [],
    }
    db.stories.insert_one(new_story_info)
    client.chat_postMessage(
        token=get_token(body["team"]["id"]),
        link_names=True,
        channel=user,
        text="Hey! I've added your story titled \"" + title + '" to the queue. ',
    )


# TODO
@slack_app.action("create_story")
def create_story_modal(ack, body, logger):
    ack()

    slack_app.client.views_open(
        token=get_token(body["team"]["id"]),
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "new_story",
            "title": {"type": "plain_text", "text": "Create a Nook!"},
            "close": {"type": "plain_text", "text": "Close"},
            "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
            "blocks": [
                {
                    "block_id": "title",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "plain_text_input-action",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "What do you want to talk about?",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "desc",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "plain_text_input-action",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Add some initial thoughts",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "banned",
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Are there any people you don't want to be a part of this conversation?",
                    },
                    "accessory": {
                        "action_id": "text1234",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select users you don't want included in this nook",
                            "emoji": True,
                        },
                        "type": "multi_users_select",
                    },
                },
            ],
        },
    )


@slack_app.action("story_interested")
def nook_int(ack, body, logger):
    ack()

    user_id = body["user"]["id"]
    cur_pos = int(body["actions"][0]["value"])
    logging.info("NFJKENWRKJ")
    logging.info(nooks_home.suggested_stories)
    user_story = nooks_home.suggested_stories[body["team"]["id"]][cur_pos]
    db.user_swipes.update_one(
        {"user_id": user_id, "team_id": body["team"]["id"]},
        {"$set": {"cur_pos": cur_pos + 1}},
    )
    db.stories.update(
        {"_id": user_story["_id"], "team_id": body["team"]["id"]},
        {"$push": {"swiped_right": user_id}},
    )
    nooks_home.update_home_tab(
        slack_app.client,
        {"user": user_id, "view": {"team_id": body["team"]["id"]}},
        token=get_token(body["team"]["id"]),
    )


@slack_app.action("new_sample_nook")
def update_random_nook(ack, body, logger):
    ack()

    user_id = body["user"]["id"]
    logging.info("UUHNIUN")
    vals = body["actions"][0]["value"].split("/")
    logging.info(body)
    team_id = body["team"]["id"]
    cur_pos = int(vals[0])
    total_len = int(vals[1])
    db.sample_nook_pos.update_one(
        {"user_id": user_id, "team_id": body["team"]["id"]},
        {"$set": {"cur_nook_pos": (cur_pos + 1) % total_len}},
    )

    nooks_home.update_home_tab(
        slack_app.client,
        {"user": user_id, "view": {"team_id": body["team"]["id"]}},
        token=get_token(team_id),
    )


@slack_app.action("story_not_interested")
def nook_not_int(ack, body, logger):
    ack()

    user_id = body["user"]["id"]
    cur_pos = int(body["actions"][0]["value"])
    user_story = nooks_home.suggested_stories[body["team"]["id"]][cur_pos]
    db.user_swipes.update_one(
        {"user_id": user_id, "team_id": body["team"]["id"]},
        {"$set": {"cur_pos": cur_pos + 1}},
    )
    db.stories.update(
        {"_id": user_story["_id"], "team_id": body["team"]["id"]},
        {"$push": {"swiped_left": user_id}},
    )
    nooks_home.update_home_tab(
        slack_app.client,
        {"user": user_id, "view": {"team_id": body["team"]["id"]}},
        token=get_token(body["team"]["id"]),
    )


@slack_app.view("send_dm")
def handle_send_message(ack, body, client, view, logger):
    ack()

    # TODO create a new name if taken?
    input_data = view["state"]["values"]
    to_user = view["private_metadata"]
    message = input_data["message"]["plain_text_input-action"]["value"]

    slack_app.client.chat_postMessage(
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


@slack_app.action("customize_dm")
def customize_dm_modal(ack, body, client, view, logger):
    ack()

    # TODO create a new name if taken?
    from_user = body["user"]["id"]
    to_user = body["actions"][0]["value"]
    response = slack_app.client.conversations_open(
        token=get_token(body["team"]["id"]),
        users=from_user + "," + to_user + ",U02HTEETX54",
    )
    channel_id = response["channel"]["id"]
    slack_app.client.chat_postMessage(
        token=get_token(body["team"]["id"]),
        link_names=True,
        channel=channel_id,
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Direct Message Trial"},
            },
        ],
    )
    # db.personal_message.insert_one(new_story_info)
    # slack_app.client.conversations_open(users=to_user)
    # return
    """
    slack_app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "send_dm",
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
    """


@slack_app.view("send_message")
def handle_send_message(ack, body, client, view, logger):
    ack()
    input_data = view["state"]["values"]
    from_user = body["user"]["id"]

    # logging.info("BZZZZ")
    # logging.info(view)

    to_user = view["private_metadata"]
    message = input_data["message"]["plain_text_input-action"]["value"]

    new_story_info = {
        "message": message,
        "from_user": from_user,
        "to_user": to_user,
        "team_id": body["team"]["id"],
    }
    db.personal_message.insert_one(new_story_info)
    slack_app.client.chat_postMessage(
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


@slack_app.action("contact_person")
def contact_modal(ack, body, logger):
    ack()
    from_user = body["user"]["id"]
    to_user = body["actions"][0]["value"]

    slack_app.client.views_open(
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


@slack_app.view("enter_channel")
def update_message(ack, body, client, view, logger):
    ack()

    story_id = view["private_metadata"]
    story = db.stories.find_one({"_id": ObjectId(story_id)})
    ep_channel, thread_ts = story["channel_id"], story["ts"]
    input_data = view["state"]["values"]
    user_id = body["user"]["id"]
    user = slack_app.client.users_profile_get(
        user=user_id, token=get_token(body["team"]["id"])
    )
    initial_thoughts = input_data["initial_thoughts"]["plain_text_input-action"][
        "value"
    ]
    try:
        slack_app.client.conversations_invite(
            token=get_token(body["team"]["id"]), channel=ep_channel, users=user_id
        )
        slack_app.client.chat_postMessage(
            token=get_token(body["team"]["id"]),
            link_names=True,
            channel=ep_channel,
            thread_ts=thread_ts,
            reply_broadcast=True,
            text=initial_thoughts,
        )
    except Exception as e:
        logging.error(traceback.format_exc())


@slack_app.event("app_home_opened")
def update_home_tab(client, event, logger):
    logging.info(event)
    if "view" in event:
        nooks_home.update_home_tab(client, event)


@slack_app.event("message")
def handle_message_events(body, logger):
    logger.info(body)


@slack_app.event("member_joined_channel")
def handle_message_events(client, event, logger):

    logger.info(event)
    for member in client.conversations_members(
        token=get_token(event["team"]), channel=event["channel"]
    )["members"]:
        # TODO add duplicate onboarding info
        slack_app.client.chat_postMessage(
            token=get_token(event["team"]),
            link_names=True,
            channel=member,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Hey there:wave: I'm *NooksBot*.\n_Remember the good old days where you could bump into people and start conversations?_ Nooks allow you to do exactly that but over slack!\n\n Your workplace admin invited me here and I'm ready to help you interact with your coworkers in a exciting new ways:partying_face:\n",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "action_id": "onboard_info",
                            "text": {
                                "type": "plain_text",
                                "text": "Tell me more!",
                                "emoji": True,
                            },
                            "style": "primary",
                            "value": "join",
                        }
                    ],
                },
            ],
        )


@slack_app.view("add_member")
def handle_signup(ack, body, client, view, logger):
    ack()
    # TODO create a new name if taken?
    logging.info("nvjkef")
    logging.info(body)
    input_data = view["state"]["values"]
    input_data.update(ast.literal_eval(body["view"]["private_metadata"]))
    user = body["user"]["id"]
    new_member_info = {}
    for key in input_data:
        if "plain_text_input-action" in input_data[key]:
            new_member_info[key] = input_data[key]["plain_text_input-action"]["value"]
        elif "select_input-action" in input_data[key]:
            new_member_info[key] = input_data[key]["select_input-action"][
                "selected_option"
            ]["value"]
    new_member_info["user_id"] = user
    new_member_info["member_vector"] = get_member_vector(new_member_info)
    new_member_info["team_id"] = body["team"]["id"]
    db.member_vectors.insert_one(new_member_info)
    nooks_home.update_home_tab(
        slack_app.client,
        {"user": user, "view": {"team_id": body["team"]["id"]}},
        token=get_token(body["team"]["id"]),
    )

    slack_app.client.chat_postMessage(
        token=get_token(body["team"]["id"]),
        link_names=True,
        channel=user,
        text="You're all set! Create your first story ",
    )


@slack_app.action("select_input-action")
def handle_some_action(ack, body, logger):
    ack()


@slack_app.action("learn_more")
def handle_learn_more(ack, body, logger):
    ack()

    user = body["user"]["id"]
    slack_app.client.views_open(
        token=get_token(body["team"]["id"]),
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "signup_step_1",
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


@slack_app.view("signup_step_2")
def signup_modal_step_2(ack, body, view, logger):
    user = body["user"]["id"]
    all_questions = SIGNUP_QUESTIONS["Step 2"]

    question_blocks = [
        {
            "block_id": question,
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": question,
                "emoji": True,
            },
            "accessory": {
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
            "callback_id": "add_member",
            "private_metadata": str(view["state"]["values"]),
            "title": {"type": "plain_text", "text": "Sign Up!"},
            "submit": {"type": "plain_text", "text": "Submit"},
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


@slack_app.view("signup_step_1")
def signup_modal_step_1(ack, body, view, logger):

    all_questions = SIGNUP_QUESTIONS["Step 1"]
    age_block = [
        {
            "type": "input",
            "block_id": "Age",
            "label": {"type": "plain_text", "text": "Age"},
            "element": {
                "type": "plain_text_input",
                "action_id": "plain_text_input-action",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Enter your Age",
                },
            },
        }
    ]
    question_blocks = age_block + [
        {
            "block_id": question,
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": question,
            },
            "accessory": {
                "type": "static_select",
                "action_id": "select_input-action",
                "options": [
                    {"value": value, "text": {"type": "plain_text", "text": value}}
                    for value in all_questions[question]
                ],
            },
        }
        for question in all_questions
    ]
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
                        "text": "To help me optimize your lists, tell me a bit about yourself",
                    },
                }
            ]
            + question_blocks,
        },
    )
    # logging.info(res)


@slack_app.action("signup")
def signup_modal(ack, body, logger):
    ack()

    user = body["user"]["id"]
    all_questions = SIGNUP_QUESTIONS["Step 1"]
    age_block = [
        {
            "type": "input",
            "block_id": "Age",
            "label": {"type": "plain_text", "text": "Age"},
            "element": {
                "type": "plain_text_input",
                "action_id": "plain_text_input-action",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Enter your Age",
                },
            },
        }
    ]
    question_blocks = age_block + [
        {
            "block_id": question,
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": question,
            },
            "accessory": {
                "type": "static_select",
                "action_id": "select_input-action",
                "options": [
                    {"value": value, "text": {"type": "plain_text", "text": value}}
                    for value in all_questions[question]
                ],
            },
        }
        for question in all_questions
    ]
    # TODO check if member is already in database?
    res = slack_app.client.views_open(
        token=get_token(body["team"]["id"]),
        trigger_id=body["trigger_id"],
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
                        "text": "To help me optimize your lists, tell me a bit about yourself",
                    },
                }
            ]
            + question_blocks,
        },
    )
    # logging.info(res)


@slack_app.action("join_without_interest")
def join_without_interest(ack, body, logger):
    ack()

    user = body["user"]["id"]
    ep_channel = body["actions"][0]["value"]
    slack_app.client.conversations_invite(
        token=get_token(body["team"]["id"]), channel=ep_channel, users=user
    )


@slack_app.action("onboard_info")
def show_nooks_info(ack, body, logger):
    ack()

    user_id = body["user"]["id"]

    slack_app.client.chat_postMessage(
        token=get_token(body["team"]["id"]),
        link_names=True,
        channel=user_id,
        blocks=[
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
                    "text": "*Would love some more details!*\For detailed onboarding instructions, you can visit https://nooks.vercel.app/member-onboarding!",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Note: I'm created as a part of a research project and I would be collecting data, however at no point would your details be disclosed. Participating and completing the signup counts as consent for this data collection(no data is collected otherwise). For more details regarding what data is collected, click here   ",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "signup",
                        "text": {
                            "type": "plain_text",
                            "text": "Sign me up!",
                            "emoji": True,
                        },
                        "style": "primary",
                    }
                ],
            },
        ],
    )


@slack_app.command("/onboard")
def onboarding_modal(ack, body, logger):
    ack()

    for member in slack_app.client.users_list()["members"]:
        slack_app.client.chat_postMessage(
            token=get_token(body["team"]["id"]),
            link_names=True,
            channel=member["id"],
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Hey there:wave: I'm *NooksBot*.\n_Remember the good old days where you could bump into people and start conversations?_ Nooks allow you to do exactly that but over slack!\n\n Your workplace admin invited me here and I'm ready to help you interact with your coworkers in a exciting new ways:partying_face:\n",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "action_id": "onboard_info",
                            "text": {
                                "type": "plain_text",
                                "text": "Tell me more!",
                                "emoji": True,
                            },
                            "style": "primary",
                            "value": "join",
                        }
                    ],
                },
            ],
        )


# Add functionality here
from flask import Flask, request, redirect
import requests

app = Flask(__name__)
cron = APScheduler()
cron.init_app(app)
cron.start()
handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
handler.connect()


@app.route("/")
def slack_install():
    return (
        "<a href='https://slack.com/oauth/v2/authorize?client_id="
        + CLIENT_ID
        + "&redirect_uri="
        + REDIRECT_URI
        + "&scope=app_mentions:read,channels:history,channels:manage,channels:read,chat:write,commands,groups:history,groups:read,groups:write,im:history,im:read,im:write,mpim:read,mpim:write,users.profile:read,users:read,files:write,files:read,incoming-webhook&user_scope=channels:read,channels:write,chat:write,files:read,im:write,users:read,mpim:write,groups:write'><img alt='Add to Slack' height='40' width='139' src='https://platform.slack-edge.com/img/add_to_slack.png'  /></a>"
    )


@app.route("/slack/oauth_redirect", methods=["POST", "GET"])
def slack_oauth():
    code = request.args.get("code")
    response = slack_app.client.oauth_v2_access(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        code=code,
        redirect_uri=REDIRECT_URI,
    )
    # logging.info("FEGREW")
    # logging.info(response)
    # slack_app = App()
    # os.environ["SLACK_BOT_TOKEN"] = response['access_token']
    installer = response["authed_user"]
    installation = Installation(
        app_id=response["access_token"],
        team_id=response["team"]["id"],
        team_name=response["team"]["name"],
        bot_token=response["access_token"],
        bot_id=None,
        user_id=installer["id"],
        bot_user_id=response["bot_user_id"],
        bot_scopes=response["scope"],  # comma-separated string
        user_token=installer["access_token"],
        user_scopes=installer["scope"],  # comma-separated string
        token_type=response["token_type"],
    )
    installation_store.save(installation)
    return "NEW"


def remove_past_stories():
    active_stories = list(db.stories.find({"status": "active"}))

    # archive all channels of the past day
    for active_story in active_stories:
        try:
            chat_history = slack_app.client.conversations_history(
                token=get_token(active_story["team_id"]),
                channel=active_story["channel_id"],
            )["messages"]
            db.stories.update(
                {"_id": active_story["_id"]},
                {"$set": {"status": "archived", "chat_history": chat_history}},
            )
            all_members = slack_app.client.conversations_members(
                token=get_token(active_story["team_id"]),
                channel=active_story["channel_id"],
            )["members"]
            for member_1 in all_members:
                for member_2 in all_members:
                    if not db.temporal_interacted.find(
                        {
                            "user1_id": member_1,
                            "user2_id": member_2,
                            "team_id": active_story["team_id"],
                        }
                    ):

                        db.temporal_interacted.insert_one(
                            {
                                "user1_id": member_1,
                                "user2_id": member_2,
                                "team_id": active_story["team_id"],
                                "count": 0,
                            }
                        )
                    if not db.all_interacted.find(
                        {
                            "user1_id": member_1,
                            "user2_id": member_2,
                            "team_id": active_story["team_id"],
                        }
                    ):

                        db.all_interacted.insert_one(
                            {
                                "user1_id": member_1,
                                "user2_id": member_2,
                                "team_id": active_story["team_id"],
                                "count": 0,
                            }
                        )

            db.temporal_interacted.update_many(
                {
                    "user1_id": {"$in": all_members},
                    "user2_id": {"$in": all_members},
                    "team_id": active_story["team_id"],
                },
                {"$inc": {"count": 1}},
            )
            db.all_interacted.update_many(
                {
                    "user1_id": {"$in": all_members},
                    "user2_id": {"$in": all_members},
                    "team_id": active_story["team_id"],
                },
                {"$inc": {"count": 1}},
            )
            nooks_alloc.update_interactions()
            slack_app.client.conversations_archive(
                token=get_token(active_story["team_id"]),
                channel=active_story["channel_id"],
            )

        except Exception as e:
            logging.error(traceback.format_exc())


def create_new_channels(new_stories, allocations, suggested_allocs):
    # create new channels for the day

    for i, new_story in enumerate(new_stories):
        now = datetime.now()  # current date and time
        date = now.strftime("%m-%d-%Y-%H-%M-%S")
        title = new_story["title"]
        creator = new_story["creator"]
        desc = new_story["description"]
        try:

            channel_name = "nook-" + date + "-" + str(i)

            response = slack_app.client.conversations_create(
                token=get_token(new_story["team_id"]),
                name=channel_name,
                is_private=True,
            )

            ep_channel = response["channel"]["id"]
            slack_app.client.conversations_setTopic(
                token=get_token(new_story["team_id"]), channel=ep_channel, topic=title
            )
            initial_thoughts_thread = slack_app.client.chat_postMessage(
                token=get_token(new_story["team_id"]),
                link_names=True,
                channel=ep_channel,
                text="Super-excited to hear all of your thoughts on "
                + title
                + "\n"
                + ">"
                + desc,
            )
            # logging.info("FRRRRE")
            # logging.info(allocations[new_story["_id"]])

            slack_app.client.conversations_invite(
                token=get_token(new_story["team_id"]),
                channel=ep_channel,
                users=allocations[new_story["_id"]],
            )

            db.stories.update(
                {"_id": new_story["_id"]},
                {
                    "$set": {
                        "status": "active",
                        "channel_id": ep_channel,
                        "ts": initial_thoughts_thread["ts"],
                    }
                },
            )
            for member in suggested_allocs[new_story["_id"]]:

                slack_app.client.chat_postMessage(
                    token=get_token(new_story["team_id"]),
                    link_names=True,
                    channel=member,
                    blocks=[
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "Hello! I saw that you didn't swipe right on any nook yesterday. However, in case you are still interested in getting in on the action, feel free to join in on the topic \""
                                + title
                                + '"\n>'
                                + desc,
                            },
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "action_id": "join_without_interest",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Interested!",
                                        "emoji": True,
                                    },
                                    "style": "primary",
                                    "value": ep_channel,
                                }
                            ],
                        },
                    ],
                )

        except Exception as e:
            logging.error(traceback.format_exc())
        return new_stories


def update_story_suggestions():
    # all stories
    suggested_stories = list(db.stories.find({"status": "suggested"}))
    # db.user_swipes.remove()
    if "user_swipes" not in db.list_collection_names():
        db.create_collection("user_swipes")
    for suggested_story in suggested_stories:
        try:
            # TODO don't need to do this if all are shown
            db.stories.update(
                {"_id": suggested_story["_id"]},
                {
                    "$set": {
                        "status": "show",
                    }
                },
            )
        except Exception as e:
            logging.error(traceback.format_exc())
    if suggested_stories:
        # TODO
        all_users = list(db.member_vectors.find())
        for user in all_users:
            try:
                slack_app.client.chat_postMessage(
                    token=get_token(user["team_id"]),
                    link_names=True,
                    channel=user["user_id"],
                    text="Hello! I've updated your Nook Cards List for today!",
                )
            except Exception as e:
                logging.error(traceback.format_exc())
    suggested_stories_per_team = collections.defaultdict(list)
    for story in suggested_stories:
        suggested_stories_per_team[story["team_id"]].append(story)
    return suggested_stories_per_team


# TODO change this to hour for final
@cron.task("cron", second="10")
def post_stories():
    remove_past_stories()

    current_stories = list(db.stories.find({"status": "show"}))
    allocations, suggested_allocs = nooks_alloc.create_nook_allocs(
        nooks=current_stories
    )
    create_new_channels(current_stories, allocations, suggested_allocs)
    suggested_stories = update_story_suggestions()
    nooks_home.update(suggested_stories=suggested_stories)
    # TODO

    for member in nooks_alloc.member_dict:
        # TODO change this in case there are overlaps in user ids
        team_id = db.member_vectors.find_one({"user_id": member})["team_id"]
        nooks_home.update_home_tab(
            client=slack_app.client,
            event={"user": member, "view": {"team_id": team_id}},
            token=get_token(team_id)
            #
        )


# TODO change this to hour for final
@cron.task("cron", day="1")
def reset_interactions():
    nooks_alloc.reset()


"""
#@cron.scheduled_job("cron", second="1")
def update_sample_nooks():
    nooks_home.update_sample_nooks()
"""

"""
#@cron.scheduled_job("cron", second="5")
def post_stories():
    # TODO change this to only members who have signed up
    for member in slack_app.client.users_list()["members"]:
        slack_app.client.chat_postMessage(
            link_names=True,
            channel=member["id"],
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Hey! Create nooks before to ",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "action_id": "onboard_info",
                            "text": {
                                "type": "plain_text",
                                "text": "Tell me more!",
                                "emoji": True,
                            },
                            "style": "primary",
                            "value": "join",
                        }
                    ],
                },
            ],
        )
"""


def main(nooks_home_arg, nooks_alloc_arg):
    global nooks_home
    global nooks_alloc
    nooks_home = nooks_home_arg
    nooks_alloc = nooks_alloc_arg

    # db.user_swipes.remove()
    if "user_swipes" not in db.list_collection_names():
        db.create_collection("user_swipes")
    '''
    # TODO shift to onboarding
    if "member_vectors" not in db.list_collection_names():
        db.create_collection("member_vectors")
        db.member_vectors.create_index("user_id")

        """
        member_vectors = np.random.randint(2, size=(len(all_members), MEMBER_FEATURES))
        db.member_vectors.insert_many(
            [
                {"user_id": member["id"], "member_vector": member_vectors[i].tolist()}
                for i, member in enumerate(all_members)
            ]
        )
        """
    all_members = slack_app.client.users_list()["members"]
    if "all_interacted" not in db.list_collection_names():
        db.create_collection("all_interacted")
        db.create_collection("temporal_interacted")
        counts = {member["id"]: 0 for member in all_members}

        db.all_interacted.insert_many(
            [
                {
                    "user_id": from_member["id"],
                    "counts": [
                        {"user_id": to_member["id"], "count": 0}
                        for to_member in all_members
                    ],
                }
                for from_member in all_members
            ]
        )
        db.temporal_interacted.insert_many(
            [
                {
                    "user_id": from_member["id"],
                    "counts": [
                        {"user_id": to_member["id"], "count": 0}
                        for to_member in all_members
                    ],
                }
                for from_member in all_members
            ]
        )
    '''
