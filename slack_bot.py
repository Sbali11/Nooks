from asyncio.log import logger
from email import message
from functools import lru_cache
import os
import logging
import atexit
import random
import collections
import traceback

from datetime import datetime, timezone, date
import pytz

import threading

from utils.slack_app_backend.app_home import NooksHome
from utils.matching_algorithm.nooks_alloc import NooksAllocation

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from pymongo import MongoClient
from bson import ObjectId
import numpy as np
from flask_apscheduler import APScheduler
import ast
from utils.constants import *
from utils.slack_app_backend.daily_functions import (
    remove_past_nooks,
    create_new_channels,
    post_reminders,
    update_nook_suggestions,
)
from utils.slack_app_backend.ui_text import SIGNUP_QUESTIONS, CONSENT_FORM
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize

ps = PorterStemmer()
# set configuration values
class Config:
    SCHEDULER_API_ENABLED = True


logging.basicConfig(level=logging.INFO)


# load environment variables
load_dotenv()
NUM_MEMBERS = 2
MEMBER_FEATURES = 2
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
CLIENT_SECRET = os.environ["SLACK_CLIENT_SECRET"]
MONGODB_LINK = os.environ["MONGODB_LINK"]
REDIRECT_URI = os.environ["REDIRECT_URI"]
CLIENT_ID = os.environ["SLACK_CLIENT_ID"]

db = MongoClient(MONGODB_LINK).nooks_db

from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import Installation
from utils.slack_app_backend.installation import InstallationDB, get_token


installation_store = InstallationDB(db)
scopes = [
    "app_mentions:read",
    "pins:write",
    "channels:manage",
    "channels:read",
    "chat:write",
    "commands",
    "groups:read",
    "groups:write",
    "im:read",
    "im:write",
    "mpim:read",
    "mpim:write",
    "users.profile:read",
    "users:read",
    "files:write",
    "files:read",
]

user_scopes = [
    "channels:read",
    "channels:write",
    "chat:write",
    "files:read",
    "groups:write",
    "pins:write",
    "im:write",
    "mpim:write",
    "users:read",
]

oauth_settings = OAuthSettings(
    install_path="/slack/install",
    redirect_uri_path="/slack/oauth_redirect",
    client_id=CLIENT_ID,
    client_secret=os.environ["SLACK_CLIENT_SECRET"],
    scopes=scopes,
    user_scopes=user_scopes,
    installation_store=installation_store,
)


slack_app = App(
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    oauth_settings=oauth_settings,
    installation_store=installation_store,
)


def get_member_vector(member_info):
    member_vector = [0] * (len(HOMOPHILY_FACTORS))

    for i, homophily_factor in enumerate(sorted(HOMOPHILY_FACTORS)):
        member_vector[i] = HOMOPHILY_FACTORS[homophily_factor][
            member_info[homophily_factor]
        ]
    return member_vector


@slack_app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()


@slack_app.view("success_close")
def handle_signup(ack, body, client, view, logger):
    ack()


@slack_app.action("radio_buttons-action")
def handle_some_action(ack, body, logger):
    ack()


@slack_app.command("/reload_home")
def command(ack, body, respond):
    ack()
    user_id = body["user_id"]
    team_id = body["team_id"]
    channel_id = body["channel_id"]
    token = get_token(body["team_id"])
    nooks_home.update_home_tab(
        client=slack_app.client,
        event={
            "user": user_id,
            "view": {"team_id": team_id},
        },
        token=token,
    )


@slack_app.command("/get_role")
def command(ack, body, respond):
    ack()
    user_id = body["user_id"]
    team_id = body["team_id"]
    channel_id = body["channel_id"]
    token = get_token(body["team_id"])
    nook_row = db.nooks.find_one({"channel_id": channel_id})
    if not nook_row:
        slack_app.client.chat_postEphemeral(
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
            db.random_words_collaborative.aggregate([{"$sample": {"size": 1}}])
        )[0]["word"]
        db.allocated_roles_words.insert_one(
            {
                "team_id": team_id,
                "user_id": user_id,
                "word": word,
                "channel_id": channel_id,
            }
        )
    else:
        word = allocated_row["word"]

    slack_app.client.chat_postEphemeral(
        user=body["user_id"],
        token=token,
        channel=body["channel_id"],
        text="Hey! You have a secret mission for today! Try to make use of this word in one of your messages: "
        + word,
    )


def success_modal_ack(ack, body, view, logger, message, title="Success"):
    ack(
        response_action="update",
        view={
            "type": "modal",
            "callback_id": "success_close",
            "title": {"type": "plain_text", "text": title},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message,
                    },
                }
            ],
        },
    )


def get_create_nook_blocks(initial_title, initial_desc=""):
    if initial_desc:
        desc_element = {
            "type": "plain_text_input",
            "multiline": True,
            "action_id": "plain_text_input-action",
            "initial_value": initial_desc,
            "placeholder": {
                "type": "plain_text",
                "text": "Use this space to add in some initial thoughts, related links or a detailed description of the nook topic!",
                "emoji": True,
            },
        }
    else:
        desc_element = {
            "type": "plain_text_input",
            "multiline": True,
            "action_id": "plain_text_input-action",
            "initial_value": initial_desc,
        }
    return [
        {
            "block_id": "title",
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "plain_text_input-action",
                "initial_value": initial_title,
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
            "element": desc_element,
            "label": {
                "type": "plain_text",
                "text": "Add some initial thoughts",
                "emoji": True,
            },
        },
        {
            "block_id": "channel_name",
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "plain_text_input-action",
            },
            "label": {
                "type": "plain_text",
                "text": "Add a channel title for the nook(use less than less 60 characters and only letters/dashes)",
                "emoji": True,
            },
        },
        {
            "block_id": "banned",
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Are there any members you don't want to be a part of this conversation?*",
            },
            "accessory": {
                "action_id": "user_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select users you don't want included in this nook",
                    "emoji": True,
                },
                "filter": {"include": ["im"], "exclude_bot_users": True},
                "type": "multi_conversations_select",
            },
        },
        {
            "type": "input",
            "block_id": "allow_two_members",
            "element": {
                "type": "radio_buttons",
                "action_id": "radio_buttons-action",
                "initial_option": {
                    "text": {
                        "type": "plain_text",
                        "text": "Don't create nook if there is only one additional member",
                        "emoji": True,
                    },
                    "value": "dont_allow_two_member",
                },
                "options": [
                    {
                        "text": {
                            "type": "plain_text",
                            "text": "Don't create nook if there is only one additional member",
                            "emoji": True,
                        },
                        "value": "dont_allow_two_member",
                    },
                    {
                        "text": {
                            "type": "plain_text",
                            "text": "Allow nook to be created with only one additional additional member.",
                            "emoji": True,
                        },
                        "value": "allow_two_member",
                    },
                ],
            },
            "label": {
                "type": "plain_text",
                "text": "By default, I only create nooks with atleast 3 total members to hide the creator's identity. Nooks that don't satisfy this condition are not created. ",
                "emoji": True,
            },
        },
    ]


@slack_app.view("new_nook")
def handle_new_nook(ack, body, client, view, logger):
    input_data = view["state"]["values"]
    user = body["user"]["id"]
    title = input_data["title"]["plain_text_input-action"]["value"]
    desc = input_data["desc"]["plain_text_input-action"]["value"]

    channel_name = input_data["channel_name"]["plain_text_input-action"]["value"]
    invalid_channel_name = False
    if len(channel_name) > 60:
        invalid_channel_name = True
    else:
        for letter in channel_name:
            if not (
                ("0" <= letter <= "9")
                or ("a" <= letter <= "z")
                or ("A" <= letter <= "Z")
                or letter == "-"
            ):
                invalid_channel_name = True
                break

    if invalid_channel_name:
        ack(
            response_action="update",
            view={
                "type": "modal",
                "callback_id": "new_nook",
                "private_metadata": str(view["state"]["values"]),
                "title": {"type": "plain_text", "text": "Create a Nook"},
                "submit": {
                    "type": "plain_text",
                    "text": "Add nook to the queue",
                    "emoji": True,
                },
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Oops! That is not a valid channel name* \n",
                        },
                    }
                ]
                + get_create_nook_blocks(initial_title=title, initial_desc=desc),
            },
        ),

        return

    success_modal_ack(
        ack,
        body,
        view,
        logger,
        message="Nook added to the queue",
        title="Create a Nook",
    )

    allow_two_members = (
        input_data["allow_two_members"]["radio_buttons-action"]["selected_option"][
            "value"
        ]
        == "allow_two_member"
    )
    banned = input_data["banned"]["user_select"]["selected_conversations"]

    new_nook_info = {
        "team_id": body["team"]["id"],
        "title": title,
        "creator": user,
        "channel_name": channel_name,
        "description": desc,
        "allow_two_members": allow_two_members,
        "banned": banned,
        "created_on": datetime.utcnow(),
        "swiped_right": [],
    }

    token = get_token(body["team"]["id"])
    tz = pytz.timezone(
        ALL_TIMEZONES[
            db.tokens_2.find_one({"team_id": body["team"]["id"]})["time_zone"]
        ]
    )
    team_time = datetime.now(tz).strftime("%H:%M")
    day = datetime.now(tz).weekday()
    if (day in [5, 6]) or ((day == 4) and team_time > "16:00"):
        client.chat_postMessage(
            token=get_token(body["team"]["id"]),
            link_names=True,
            channel=user,
            text="Hey! I've added your nook titled \""
            + title
            + '" to the queue! The nook will be shown to your teammates on Monday(at 12PM)!',
        )
        new_nook_info["status"] = "suggested"
    elif team_time > "16:00":
        client.chat_postMessage(
            token=get_token(body["team"]["id"]),
            link_names=True,
            channel=user,
            text="Hey! I've added your nook titled \""
            + title
            + '" to the queue! The nook will be shown to your teammates tomorrow at 12PM!',
        )
        new_nook_info["status"] = "suggested"
    elif team_time < "12:00":
        client.chat_postMessage(
            token=get_token(body["team"]["id"]),
            link_names=True,
            channel=user,
            text="Hey! I've added your nook titled \""
            + title
            + '" to the queue! The nook will be shown to your teammates today at 12PM!',
        )
        new_nook_info["status"] = "suggested"
    else:
        client.chat_postMessage(
            token=get_token(body["team"]["id"]),
            link_names=True,
            channel=user,
            text="Hey! I've added your nook titled \"" + title + '" to the queue! ',
        )

        nooks_home.add_nook(nook=new_nook_info, team_id=body["team"]["id"])

        for member in nooks_alloc.member_dict[body["team"]["id"]]:
            nooks_home.update_home_tab(
                client=slack_app.client,
                event={"user": member, "view": {"team_id": body["team"]["id"]}},
                token=token,
            )
        new_nook_info["status"] = "show"

    db.nooks.insert_one(new_nook_info)


def create_default_nook(title, desc, channel_name, bot_id, team_id):
    new_nook_info = {
        "team_id": team_id,
        "title": title,
        "creator": bot_id,
        "channel_name": channel_name,
        "description": desc+"\n\n(P.S. This nook has been created by the nook admins and is inspired by nooks created in other workspaces)",
        "allow_two_members": True,
        "banned": [],
        "created_on": datetime.utcnow(),
        "swiped_right": [],
    }
    new_nook_info["status"] = "show"
    db.nooks.insert_one(new_nook_info)
    
    token = get_token(team_id)
    nooks_home.add_nook(nook=new_nook_info, team_id=team_id)
    for member in nooks_alloc.member_dict[team_id]:
        nooks_home.update_home_tab(
            client=slack_app.client,
            event={"user": member, "view": {"team_id": team_id}},
            token=token,
        )


@slack_app.action("create_nook")
def create_nook_modal(ack, body, logger):
    ack()

    if "value" in body["actions"][0]:
        initial_title = body["actions"][0]["value"]
    else:
        initial_title = ""

    slack_app.client.views_open(
        token=get_token(body["team"]["id"]),
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "new_nook",
            "title": {"type": "plain_text", "text": "Create a Nook"},
            "close": {"type": "plain_text", "text": "Close"},
            "submit": {
                "type": "plain_text",
                "text": "Add nook to the queue",
                "emoji": True,
            },
            "blocks": get_create_nook_blocks(initial_title),
        },
    )


@slack_app.action("user_select")
def handle_user_selected(ack, body, logger):
    ack()


@slack_app.action("channel_selected")
def handle_channel_selected(ack, body, logger):
    ack()


@slack_app.action("member_selected")
def handle_some_action(ack, body, logger):
    ack()


@slack_app.view("word_guessed")
def handle_word_guessed(ack, body, client, view, logger):
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
    # print("HERE")
    if ps.stem(word) == ps.stem(allocated_row["word"]):
        slack_app.client.chat_postMessage(
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
        slack_app.client.chat_postMessage(
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


@slack_app.action("word_said")
def handle_word_said(ack, body, logger):
    ack()
    token = get_token(body["team"]["id"])
    channel_id = body["actions"][0]["value"]
    channel_members_list = list(
        db.allocated_roles_words.find(
            {"team_id": body["team"]["id"], "channel_id": channel_id}
        )
    )
    channel_members = [
        {
            "text": {
                "type": "plain_text",
                "text": slack_app.client.users_info(token=token, user=obj["user_id"])[
                    "user"
                ]["name"],
            },
            "value": obj["user_id"],
        }
        for obj in channel_members_list
    ]
    slack_app.client.views_open(
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


@slack_app.view("onboard_members")
def handle_onboard_members(ack, body, client, view, logger):
    input_data = view["state"]["values"]
    # input_data.update(ast.literal_eval(body["view"]["private_metadata"]))
    success_modal_ack(
        ack,
        body,
        view,
        logger,
        message="Yay! I'm now sending the onboarding invites to members",
        title="Onboard Members",
    )
    onboard_type = view["private_metadata"]
    all_members = set([])
    token = get_token(body["team"]["id"])
    if onboard_type == "onboard_channels":

        conversations_all = input_data["members"]["channel_selected"][
            "selected_options"
        ]
        conversations_ids = [conv["value"] for conv in conversations_all]
        conversations_names = [conv["text"]["text"] for conv in conversations_all]
        dont_include_list = input_data["dont_include"]["channel_selected"][
            "selected_conversations"
        ]
        dont_include = set(dont_include_list)

        all_registered_users = {
            row["user_id"]
            for row in list(db.member_vectors.find({"team_id": body["team"]["id"]}))
        }
        for conversation in conversations_ids:

            for member in slack_app.client.conversations_members(
                token=token, channel=conversation
            )["members"]:
                if member in dont_include or member in all_registered_users:
                    continue
                all_members.add(member)
        message_text = "Hey there! Thank you for initiating the onboarding-process for the following channels: "
        if dont_include:
            dont_include_text = " but I didn't sent the message to " + ",".join(
                [str("<@" + member + ">") for member in dont_include]
            )
        else:
            dont_include_text = ""

    else:
        all_members = set(
            input_data["include"]["channel_selected"]["selected_conversations"]
        )
        conversations_names = [str("<@" + member + ">") for member in all_members]
        message_text = "Hey there! Thank you for initiating the onboarding-process for the following members: "
        dont_include_text = ""

    client.chat_postMessage(
        token=token,
        link_names=True,
        channel=body["user"]["id"],
        text=message_text + ",".join(conversations_names) + dont_include_text,
    )
    for member in all_members:
        try:
            slack_app.client.chat_postMessage(
                token=token,
                link_names=True,
                channel=member,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Hey there:wave: I'm *NooksBot*.\n I've been invited here to help you interact with your co-workers in exciting new ways:partying_face:, and <@"
                            + body["user"]["id"]
                            + "> wants you to sign-up!",
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
        except Exception as e:
            logging.info(e)


@slack_app.view("unselect_members_onboard")
def handle_unselect_members(ack, body, view, logger):
    user = body["user"]["id"]
    input_data = view["state"]["values"]

    conversations_all = input_data["members"]["channel_selected"]["selected_options"]
    conversations_ids = [conv["value"] for conv in conversations_all]
    token = get_token(body["team"]["id"])
    all_members = set([])

    for conversation in conversations_ids:
        for member in slack_app.client.conversations_members(
            token=token, channel=conversation
        )["members"]:
            user_info = slack_app.client.users_info(user=member, token=token)["user"]
            if not user_info["is_bot"]:
                all_members.add((member, user_info["name"]))

    channel_options = [
        {
            "text": {
                "type": "plain_text",
                "text": member_name,
            },
            "value": member,
        }
        for member, member_name in all_members
    ]
    ack(
        response_action="update",
        view={
            "type": "modal",
            "callback_id": "onboard_members",
            "private_metadata": str(view["state"]["values"]),
            "title": {"type": "plain_text", "text": "Onboard Members"},
            "submit": {"type": "plain_text", "text": "Onboard"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "block_id": "dont_include",
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Select members you don't want to include in the onboarding*\nBy default, I'll send a onboarding message to everyone in the channels selected. Let me know if you would like to exclude some members",
                    },
                    "accessory": {
                        "filter": {"include": ["im"], "exclude_bot_users": True},
                        "type": "multi_conversations_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select members not to include in onboarding",
                            "emoji": True,
                        },
                        "action_id": "channel_selected",
                    },
                },
            ],
        },
    ),


def get_onboard_members_blocks(token):

    blocks = [
        {
            "block_id": "include",
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Select members you want to onboard*",
            },
            "accessory": {
                "filter": {"include": ["im"], "exclude_bot_users": True},
                "type": "multi_conversations_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select members to onboard",
                    "emoji": True,
                },
                "action_id": "channel_selected",
            },
        },
    ]
    return blocks


@slack_app.action("go_to_website")
def handle_go_to_website(ack, body, logger):
    ack()


@slack_app.action("initiate_onboarding_modal")
def handle_onboard_request(ack, body, logger):
    ack()
    token = get_token(body["team"]["id"])

    slack_app.client.views_open(
        token=token,
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "onboarding_selected",
            "title": {"type": "plain_text", "text": "Onboard Members"},
            "close": {"type": "plain_text", "text": "Close"},
            "submit": {
                "type": "plain_text",
                "text": "Next",
                "emoji": True,
            },
            "blocks": [
                {
                    "block_id": "onboard_selected",
                    "type": "actions",
                    "elements": [
                        {
                            "type": "radio_buttons",
                            "action_id": "radio_buttons-action",
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Onboard members from Channels",
                                        "emoji": True,
                                    },
                                    "value": "onboard_channels",
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Onboard Individual Members",
                                        "emoji": True,
                                    },
                                    "value": "onboard_ind_members",
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    )


def get_onboard_channels_blocks(token):

    channel_options = [
        {
            "text": {
                "type": "plain_text",
                "text": channel["name"],
            },
            "value": channel["id"],
        }
        for channel in slack_app.client.users_conversations(
            token=token, types="public_channel,private_channel", exclude_archived=True
        )["channels"]
    ][:100]
    if not len(channel_options):
        blocks = [
            {
                "block_id": "members",
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Select channels whose members you want to onboard!*\n\n The Nooks bot isn't added to any channel right now. Add the bot to a channel to get started",
                },
            },
        ]

    else:
        blocks = [
            {
                "block_id": "members",
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Select channels whose members you want to onboard*\n To add more channels to this list, just add me to the channel",
                },
                "accessory": {
                    "action_id": "channel_selected",
                    "type": "multi_static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select channels",
                    },
                    "options": channel_options,
                },
            },
            {
                "block_id": "dont_include",
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Select members you don't want to include in the onboarding*\nBy default, I'll send a onboarding message to everyone in the channels selected. Let me know if you would like to exclude some members",
                },
                "accessory": {
                    "filter": {"include": ["im"], "exclude_bot_users": True},
                    "type": "multi_conversations_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select members not to include in onboarding",
                        "emoji": True,
                    },
                    "action_id": "channel_selected",
                },
            },
        ]
    return blocks


@slack_app.view("onboarding_selected")
def handle_onboarding(ack, body, view, logger):
    input_data = view["state"]["values"]
    onboard_type = input_data["onboard_selected"]["radio_buttons-action"][
        "selected_option"
    ]["value"]
    token = get_token(body["team"]["id"])
    if onboard_type == "onboard_channels":
        blocks = get_onboard_channels_blocks(token)
    else:
        blocks = get_onboard_members_blocks(token)
    ack(
        response_action="update",
        view={
            "type": "modal",
            "callback_id": "onboard_members",
            "private_metadata": onboard_type,
            "title": {"type": "plain_text", "text": "Onboard Members"},
            "submit": {"type": "plain_text", "text": "Onboard"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": blocks,
        },
    ),


@slack_app.view("save_feedback")
def handle_save_feedback(ack, body, client, view, logger):

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
    db.feedback.insert_one(feedback)


@slack_app.action("send_feedback")
def handle_send_feedback(ack, body, logger):
    ack()
    slack_app.client.views_open(
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


@slack_app.action("nook_interested")
def nook_int(ack, body, logger):
    ack()

    user_id = body["user"]["id"]
    cur_pos = int(body["actions"][0]["value"])
    try:
        user_nook = nooks_home.suggested_nooks[body["team"]["id"]][cur_pos]
        db.user_swipes.update_one(
            {"user_id": user_id, "team_id": body["team"]["id"]},
            {"$set": {"cur_pos": cur_pos + 1}},
        )
        db.nooks.update(
            {"_id": user_nook["_id"], "team_id": body["team"]["id"]},
            {"$push": {"swiped_right": user_id}},
        )
    except Exception as e:
        logging.info(e)

    nooks_home.update_home_tab(
        slack_app.client,
        {"user": user_id, "view": {"team_id": body["team"]["id"]}},
        token=get_token(body["team"]["id"]),
    )


@slack_app.action("nook_not_interested")
def nook_not_int(ack, body, logger):
    ack()

    user_id = body["user"]["id"]
    cur_pos = int(body["actions"][0]["value"])
    user_nook = nooks_home.suggested_nooks[body["team"]["id"]][cur_pos]
    db.user_swipes.update_one(
        {"user_id": user_id, "team_id": body["team"]["id"]},
        {"$set": {"cur_pos": cur_pos + 1}},
    )
    db.nooks.update(
        {"_id": user_nook["_id"], "team_id": body["team"]["id"]},
        {"$push": {"swiped_left": user_id}},
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
    vals = body["actions"][0]["value"].split("/")
    team_id = body["team"]["id"]
    cur_pos = int(vals[0])
    total_len = int(vals[1])
    db.sample_nook_pos.update_one(
        {"user_id": user_id, "team_id": body["team"]["id"]},
        {"$set": {"cur_nook_pos": (cur_pos + 2) % total_len}},
    )

    nooks_home.update_home_tab(
        slack_app.client,
        {"user": user_id, "view": {"team_id": body["team"]["id"]}},
        token=get_token(team_id),
    )


@slack_app.view("send_dm")
def handle_send_dm(ack, body, client, view, logger):
    success_modal_ack(
        ack, body, view, logger, message="DM sent!", title="Connect beyond Nooks"
    )

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
        users=from_user + "," + to_user,
    )
    channel_id = response["channel"]["id"]
    slack_app.client.chat_postMessage(
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


@slack_app.view("send_message")
def handle_send_message(ack, body, client, view, logger):
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
    db.personal_message.insert_one(personal_message_info)
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
def handle_contact_person(ack, body, logger):
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

    nook_id = view["private_metadata"]
    nook = db.nooks.find_one({"_id": ObjectId(nook_id)})
    ep_channel, thread_ts = nook["channel_id"], nook["ts"]
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


@slack_app.event("team_join")
def team_joined(client, event, logger):
    if "user" in event:
        nooks_home.update_home_tab(
            client,
            {
                "user": event["user"]["id"],
                "view": {"team_id": event["user"]["team_id"]},
            },
        )


@slack_app.event("app_home_opened")
def update_home_tab(client, event, logger):
    if "view" in event:
        nooks_home.update_home_tab(client, event)


@slack_app.event("message")
def handle_message_events(body, logger):
    logger.info(body)


@slack_app.view("add_member")
def handle_signup(ack, body, client, view, logger):
    success_modal_ack(
        ack, body, view, logger, message="Sign up successful!", title="Sign Up!"
    )
    # TODO create a new name if taken?
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
    # new_member_info["member_vector"] = get_member_vector(new_member_info)
    new_member_info["team_id"] = body["team"]["id"]
    new_member_info["created_on"] = datetime.utcnow()
    db.member_vectors.insert_one(new_member_info)
    db.blacklisted.update_one(
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
        blacklist_row = db.blacklisted.find_one(
            {"user_id": member, "team_id": body["team"]["id"]}
        )
        if blacklist_row and "blacklisted_from" in blacklist_row:
            db.blacklisted.update_one(
                {"user_id": member, "team_id": body["team"]["id"]},
                {"$push": {"blacklisted_from": user}},
            )
        else:
            db.blacklisted.update_one(
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

    nooks_home.update_home_tab(
        slack_app.client,
        {"user": user, "view": {"team_id": body["team"]["id"]}},
        token=get_token(body["team"]["id"]),
    )

    slack_app.client.chat_postMessage(
        token=get_token(body["team"]["id"]),
        link_names=True,
        channel=user,
        text="You're all set! Create your first nook! ",
    )


@slack_app.action("select_input-action")
def handle_select_input_action(ack, body, logger):
    ack()


@slack_app.action("tell_me_more")
def handle_tell_me_more(ack, body, logger):
    ack()

    user = body["user"]["id"]
    slack_app.client.views_open(
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


@slack_app.action("learn_more")
def handle_learn_more(ack, body, logger):
    ack()

    user = body["user"]["id"]
    slack_app.client.views_open(
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


@slack_app.view("signup_step_3")
def signup_modal_step_3(ack, body, view, logger):
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


def get_consent_blocks():
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


@slack_app.view("signup_step_2")
def signup_modal_step_2(ack, body, view, logger):
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


@slack_app.view("signup_step_1")
def signup_modal_step_1(ack, body, view, logger):
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
    team_row = db.tokens_2.find_one({"team_id": body["team"]["id"]})
    if "locations" not in team_row:
        current_locations = []
    else:
        current_locations = team_row["locations"]
    question_blocks = [
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
        for question in all_questions
    ]
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
                        "text": "To help me optimize your Nooks experience, tell me a bit about yourself!",
                    },
                }
            ]
            + question_blocks,
        },
    )


@slack_app.view("signup_step_0")
def signup_modal_step_0(ack, body, view, logger):

    # TODO check if member is already in database?
    ack(
        response_action="update",
        view={
            "type": "modal",
            "callback_id": "signup_step_1",
            "title": {"type": "plain_text", "text": "Sign Up!"},
            "submit": {"type": "plain_text", "text": "Next"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": get_consent_blocks(),
        },
    )


@slack_app.action("signup")
def signup_modal(ack, body, logger):
    ack()
    # TODO check if member is already in database?
    res = slack_app.client.views_open(
        token=get_token(body["team"]["id"]),
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "signup_step_1",
            "title": {"type": "plain_text", "text": "Sign Up!"},
            "submit": {"type": "plain_text", "text": "Next"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": get_consent_blocks(),
        },
    )


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


@slack_app.view("update_timezone")
def handle_update_timezone(ack, body, client, view, logger):
    input_data = view["state"]["values"]
    user_id = body["user"]["id"]
    team_id = body["team"]["id"]
    time_zone = input_data["timezone_id"]["select_input-action"]["selected_option"][
        "value"
    ]
    success_modal_ack(
        ack,
        body,
        view,
        logger,
        message="Time Zone for the workspace updated to " + time_zone,
        title="Set Time-Zone",
    )
    # TODO create a new name if taken?

    db.tokens_2.update(
        {
            "team_id": team_id,
        },
        {
            "$set": {
                "time_zone": time_zone,
            }
        },
    )
    update_home_tab_all(token=get_token(team_id), installed_team=body["team"])


@slack_app.view("update_locations")
def handle_update_timezone(ack, body, client, view, logger):
    input_data = view["state"]["values"]
    user_id = body["user"]["id"]
    team_id = body["team"]["id"]
    if "past_locations" in input_data:
        past_locations = [
            options["text"]["text"]
            for options in input_data["past_locations"]["location_checkboxes"][
                "selected_options"
            ]
        ]
    else:
        past_locations = []
    if "new_location" in input_data:
        if input_data["new_location"]["plain_text_input-action"]["value"]:
            new_locations = input_data["new_location"]["plain_text_input-action"][
                "value"
            ].split(",")
        else:
            new_locations = []
    else:
        new_locations = []
    success_modal_ack(
        ack,
        body,
        view,
        logger,
        message="Location options updated! ",
        title="Edit Location Options",
    )
    # TODO create a new name if taken?

    db.tokens_2.update(
        {
            "team_id": team_id,
        },
        {
            "$set": {
                "locations": past_locations + new_locations,
            }
        },
    )
    update_home_tab_all(token=get_token(team_id), installed_team=body["team"])


@slack_app.action("set_timezone")
def set_timezone_modal(ack, body, logger):
    ack()
    common_timezones = set([])

    timezone_options = [
        {
            "value": timezone,
            "text": {"type": "plain_text", "text": timezone},
        }
        for timezone in ALL_TIMEZONES
    ]

    slack_app.client.views_open(
        token=get_token(body["team"]["id"]),
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "update_timezone",
            "title": {"type": "plain_text", "text": "Set Time-Zone"},
            "submit": {"type": "plain_text", "text": "Set Time-Zone"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "block_id": "timezone_id",
                    "type": "input",
                    "label": {
                        "type": "plain_text",
                        "text": "Select a timezone for the workspace",
                    },
                    "element": {
                        "type": "static_select",
                        "action_id": "select_input-action",
                        "options": timezone_options,
                    },
                },
            ],
        },
    )


@slack_app.action("edit_location")
def set_locations_modal(ack, body, logger):
    ack()
    common_timezones = set([])
    team_row = db.tokens_2.find_one({"team_id": body["team"]["id"]})
    current_time_zone = team_row["time_zone"]
    if "locations" not in team_row:
        current_location_options = []

    else:
        current_location_options = [
            {
                "value": str(i),
                "text": {"type": "plain_text", "text": location},
            }
            for i, location in enumerate(team_row["locations"])
        ]
    if current_location_options:
        current_location_block = [
            {
                "type": "input",
                "block_id": "past_locations",
                "label": {
                    "type": "plain_text",
                    "text": "Unselect any location you want to delete",
                },
                "optional": True,
                "element": {
                    "type": "checkboxes",
                    "action_id": "location_checkboxes",
                    "initial_options": current_location_options,
                    "options": current_location_options,
                },
            }
        ]
    else:
        current_location_block = []

    slack_app.client.views_open(
        token=get_token(body["team"]["id"]),
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "update_locations",
            "title": {"type": "plain_text", "text": "Edit Location Options"},
            "submit": {"type": "plain_text", "text": "Submit Changes"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": current_location_block
            + [
                {
                    "block_id": "new_location",
                    "type": "input",
                    "label": {
                        "type": "plain_text",
                        "text": "Add location options for the workspace(to add in multiple locations separate them by commas)",
                    },
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "plain_text_input-action",
                    },
                },
            ],
        },
    )


@slack_app.action("team_settings")
def edit_team_settings(ack, body, logger):
    ack()

    slack_app.client.views_open(
        token=get_token(body["team"]["id"]),
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "update_timezone",
            "title": {"type": "plain_text", "text": "Edit Team Settings"},
            "submit": {"type": "plain_text", "text": "Set Time-Zone"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "action_id": "set_timezone",
                            "text": {
                                "type": "plain_text",
                                "text": "Change Team Timezone",
                                "emoji": True,
                            },
                            "style": "primary",
                        },
                        {
                            "type": "button",
                            "action_id": "location_choices",
                            "text": {
                                "type": "plain_text",
                                "text": "Add a Location Choices",
                                "emoji": True,
                            },
                            "style": "primary",
                        },
                    ],
                },
            ],
        },
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


@app.route("/slack/install")
def slack_install():
    return (
        "<a href='https://slack.com/oauth/v2/authorize?client_id="
        + CLIENT_ID
        + "&redirect_uri="
        + REDIRECT_URI
        + "&scope="
        + ",".join(scopes)
        + ",incoming-webhook"
        + "&user_scope="
        + ",".join(user_scopes)
        + "'><img alt='Add to Slack' height='40' width='139' src='https://platform.slack-edge.com/img/add_to_slack.png'  /></a>"
    )


def update_home_tab_all(token, installed_team):
    for member in slack_app.client.users_list(token=token)["members"]:
        try:
            nooks_home.update_home_tab(
                client=slack_app.client,
                event={
                    "user": member["id"],
                    "view": {"team_id": installed_team.get("id")},
                },
                token=get_token(installed_team.get("id")),
            )
        except Exception as e:
            logging.error(e)


@app.route("/slack/oauth_redirect", methods=["POST", "GET"])
def slack_oauth():
    code = request.args.get("code")
    oauth_response = slack_app.client.oauth_v2_access(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        code=code,
        redirect_uri=REDIRECT_URI,
    )
    installed_enterprise = {}
    # oauth_response.get("enterprise", {})
    is_enterprise_install = oauth_response.get("is_enterprise_install")
    installed_team = oauth_response.get("team", {})
    installer = oauth_response.get("authed_user", {})
    incoming_webhook = oauth_response.get("incoming_webhook", {})

    bot_token = oauth_response.get("access_token")
    # NOTE: oauth.v2.access doesn't include bot_id in response
    bot_id = None
    enterprise_url = None

    installation = Installation(
        app_id=oauth_response.get("app_id"),
        enterprise_id=installed_enterprise.get("id"),
        enterprise_name=installed_enterprise.get("name"),
        enterprise_url=enterprise_url,
        team_id=installed_team.get("id"),
        team_name=installed_team.get("name"),
        bot_token=bot_token,
        bot_id=bot_id,
        bot_user_id=oauth_response.get("bot_user_id"),
        bot_scopes=oauth_response.get("scope"),  # comma-separated string
        user_id=installer.get("id"),
        user_token=installer.get("access_token"),
        user_scopes=installer.get("scope"),  # comma-separated string
        incoming_webhook_url=incoming_webhook.get("url"),
        incoming_webhook_channel=incoming_webhook.get("channel"),
        incoming_webhook_channel_id=incoming_webhook.get("channel_id"),
        incoming_webhook_configuration_url=incoming_webhook.get("configuration_url"),
        is_enterprise_install=is_enterprise_install,
        token_type=oauth_response.get("token_type"),
    )

    # Store the installation
    installation_store.save(installation)
    team_id = installed_team.get("id")
    thread = threading.Thread(
        target=update_home_tab_all,
        kwargs={"token": get_token(team_id), "installed_team": installed_team},
    )
    thread.start()

    return "Successfully installed"


def remove_stories_periodic(all_team_ids):
    for team_id in all_team_ids:
        remove_past_nooks(slack_app, db, nooks_alloc, team_id=team_id)


def post_stories_periodic(all_team_ids):

    for team_id in all_team_ids:
        current_nooks = list(db.nooks.find({"status": "show", "team_id": team_id}))
        allocations, suggested_allocs = nooks_alloc.create_nook_allocs(
            nooks=current_nooks, team_id=team_id
        )
        create_new_channels(
            slack_app, db, current_nooks, allocations, suggested_allocs, team_id=team_id
        )
        nooks_home.reset(team_id=team_id)

        token = get_token(team_id)

        for i, member in enumerate(nooks_alloc.member_dict[team_id]):
            nooks_home.update_home_tab(
                client=slack_app.client,
                event={"user": member, "view": {"team_id": team_id}},
                token=token,
            )


def update_stories_periodic(all_team_ids, end_time=False):
    for team_id in all_team_ids:
        if end_time:
            default_nook = db.nooks_default.find_one(
                {"team_id": team_id, "status": "show"}
            )

            bot_id = db.tokens_2.find_one({"team_id": team_id})["installation"][
                "bot_user_id"
            ]
            if default_nook:
                create_default_nook(
                    default_nook["title"],
                    default_nook["description"],
                    default_nook["channel_name"],
                    bot_id=bot_id,
                    team_id=team_id,
                )
                default_nook["status"] = "used"
                db.nooks_default.update(
                    {"_id": default_nook["_id"], "team_id": team_id}, default_nook
                )
        suggested_nooks = update_nook_suggestions(slack_app, db, team_id)
        nooks_home.update(suggested_nooks=suggested_nooks, team_id=team_id)
        token = get_token(team_id)
        for member in nooks_alloc.member_dict[team_id]:
            nooks_home.update_home_tab(
                client=slack_app.client,
                event={"user": member, "view": {"team_id": team_id}},
                token=token,
            )


def post_reminder_periodic(all_team_ids):
    for team_id in all_team_ids:
        post_reminders(slack_app, db, team_id)


def get_team_rows_timezone(time, skip_weekends=True):
    all_team_rows = []
    all_time_zones = set([])
    for time_zone in ALL_TIMEZONES:
        tz = pytz.timezone(ALL_TIMEZONES[time_zone])
        timezone_time = datetime.now(tz).strftime("%H:%M")
        if timezone_time == time and (
            (not skip_weekends) or datetime.now(tz).weekday() not in [5, 6]
        ):
            all_time_zones.add(time_zone)

    for time_zone in all_time_zones:
        all_team_rows += list(db.tokens_2.find({"time_zone": time_zone}))
    team_ids = set([])
    for team_row in all_team_rows:
        team_ids.add(team_row["team_id"])

    return team_ids


@cron.task("cron", minute="0")
def post_stories_0():
    remove_stories_periodic(get_team_rows_timezone("12:00", skip_weekends=False))
    all_team_rows_no_weekend = get_team_rows_timezone("12:00")
    post_stories_periodic(all_team_rows_no_weekend)
    update_stories_periodic(all_team_rows_no_weekend)


@cron.task("cron", minute="30")
def post_stories_30():
    remove_stories_periodic(get_team_rows_timezone("12:00", skip_weekends=False))
    all_team_rows_no_weekend = get_team_rows_timezone("12:00")
    post_stories_periodic(all_team_rows_no_weekend)
    update_stories_periodic(all_team_rows_no_weekend)


@cron.task("cron", minute="45")
def post_stories_45():

    remove_stories_periodic(get_team_rows_timezone("12:04", skip_weekends=False))
    all_team_rows_no_weekend = get_team_rows_timezone("12:00")
    post_stories_periodic(all_team_rows_no_weekend)
    update_stories_periodic(all_team_rows_no_weekend)


@cron.task("cron", minute="0")
def post_reminder_message_0():
    post_reminder_periodic(get_team_rows_timezone("10:00", skip_weekends=False))


@cron.task("cron", minute="30")
def post_reminder_message_30():
    post_reminder_periodic(get_team_rows_timezone("10:00", skip_weekends=False))


@cron.task("cron", minute="45")
def post_reminder_message_45():
    post_reminder_periodic(get_team_rows_timezone("10:00", skip_weekends=False))


@cron.task("cron", minute="0")
def update_stories_0():
    update_stories_periodic(get_team_rows_timezone("16:00"), end_time=True)


@cron.task("cron", minute="30")
def update_stories_30():
    update_stories_periodic(get_team_rows_timezone("16:00"), end_time=True)


@cron.task("cron", minute="45")
def update_stories_45():
    update_stories_periodic(get_team_rows_timezone("16:00"), end_time=True)


@cron.task("cron", day_of_week="6")
def reset_interactions():
    nooks_alloc.reset()


@slack_app.event("member_joined_channel")
def handle_member_joined_channel_events(body, logger):
    pass


def main(nooks_home_arg, nooks_alloc_arg):
    global nooks_home
    global nooks_alloc
    nooks_home = nooks_home_arg
    nooks_alloc = nooks_alloc_arg

    # db.user_swipes.remove()
    if "user_swipes" not in db.list_collection_names():
        db.create_collection("user_swipes")
