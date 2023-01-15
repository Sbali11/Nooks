from asyncio.log import logger
from email import message
from functools import lru_cache
import os
import logging
import traceback

from datetime import datetime, timezone, date
import pytz
import threading
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import numpy as np
from flask_apscheduler import APScheduler
import ast
from utils.constants import *
from utils.daily_functions import (
    remove_past_nooks,
    create_new_channels,
    post_reminders,
    update_nook_suggestions,
)
from installation import *

# set configuration values
class Config:
    SCHEDULER_API_ENABLED = True


logging.basicConfig(level=logging.INFO)


from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import Installation
from installation import InstallationDB, get_token


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

load_dotenv()

# load environment variables
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
CLIENT_SECRET = os.environ["SLACK_CLIENT_SECRET"]
REDIRECT_URI = os.environ["REDIRECT_URI"]
CLIENT_ID = os.environ["SLACK_CLIENT_ID"]


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

@slack_app.middleware 
def log_request(logger, body, next):
    logger.debug(body)
    return next()

@slack_app.view("success_close")
def handle_success_close(ack, body, client, view, logger):
    ack()


@slack_app.action("radio_buttons-action")
def handle_some_action(ack, body, logger):
    ack()


@slack_app.command("/reload_home")
def command(ack, body, respond):
    ack()
    user_id = body["user_id"]
    team_id = body["team_id"]
    token = get_token(body["team_id"])
    nooks_home.update_home_tab(
        client=slack_app.client,
        event={
            "user": user_id,
            "view": {"team_id": team_id},
        },
        token=token,
    )
    try:
        slack_app.client.chat_postMessage(
            token=get_token(team_id),
            link_names=True,
            channel=user_id,
            text="I've updated your app home page, head over to the home page to see it!",
        )
    except Exception as e:
        logging.error(e)

@slack_app.action("user_select")
def handle_user_selected(ack, body, logger):
    ack()

@slack_app.action("channel_selected")
def handle_channel_selected(ack, body, logger):
    ack()

@slack_app.action("member_selected")
def handle_some_action(ack, body, logger):
    ack()

@slack_app.action("go_to_website")
def handle_go_to_website(ack, body, logger):
    ack()

@slack_app.event("app_home_opened")
def update_home_tab(client, event, logger):
    if "view" in event:
        nooks_home.update_home_tab(client, event)

@slack_app.event("message")
def handle_message_events(body, logger):
    logger.info(body)

@slack_app.action("select_input-action")
def handle_select_input_action(ack, body, logger):
    ack()

@slack_app.view("send_dm")
def handle_send_dm(ack, body, client, view, logger):
    beyond_nooks.handle_send_dm(ack, body, client, view, logger)

@slack_app.action("customize_dm")
def customize_dm_modal(ack, body, client, view, logger): 
    beyond_nooks.customize_dm_modal(ack, body, client, view, logger)

@slack_app.view("send_message")
def handle_send_message(ack, body, client, view, logger):
    beyond_nooks.handle_send_message(ack, body, client, view, logger)

@slack_app.action("contact_person")
def handle_contact_person(ack, body, logger):
    beyond_nooks.handle_contact_person(ack, body, logger)

@slack_app.view("save_feedback")
def handle_save_feedback(ack, body, client, view, logger): 
    feedback.handle_save_feedback(ack, body, client, view, logger)

@slack_app.action("send_feedback")
def handle_send_feedback(ack, body, logger):
    feedback.handle_send_feedback(ack, body, logger)

@slack_app.command("/get_role")
def handle_get_role(ack, body, respond):
    guess_game.handle_get_role(ack, body, respond)

@slack_app.view("word_guessed")
def handle_word_guessed(ack, body, client, view, logger):
    guess_game.handle_word_guessed(ack, body, client, view, logger)

@slack_app.action("word_said")
def handle_word_said(ack, body, logger):
    guess_game.handle_word_said(ack, body, logger)
    
@slack_app.event("team_join")
def handle_team_joined(client, event, logger):
    onboarding.handle_team_joined(client, event, logger)

@slack_app.action("onboard_info")
def onboard_info(ack, body, logger):
    onboarding.onboard_info(ack, body, logger)

@slack_app.view("onboard_members")
def handle_onboard_members(ack, body, client, view, logger):
    onboarding.handle_onboard_members(ack, body, client, view, logger)

@slack_app.action("initiate_onboarding_modal")
def handle_onboard_request(ack, body, logger):
    onboarding.handle_onboard_request(ack, body, logger)

@slack_app.view("unselect_members_onboard")
def handle_unselect_members(ack, body, view, logger):
    onboarding.handle_unselect_members(ack, body, view, logger)

@slack_app.view("onboarding_selected")
def handle_onboarding(ack, body, view, logger):
    onboarding.handle_onboarding(ack, body, view, logger)

@slack_app.view("add_member")
def handle_signup(ack, body, client, view, logger):
    signup.handle_signup(ack, body, client, view, logger)

@slack_app.action("tell_me_more")
def handle_tell_me_more(ack, body, logger):
    signup.handle_tell_me_more(ack, body, logger)

@slack_app.action("learn_more")
def handle_learn_more(ack, body, logger):
    signup.handle_learn_more(ack, body, logger)

@slack_app.action("signup")
def signup_modal(ack, body, logger):
    signup.signup_modal(ack, body, logger)

@slack_app.view("signup_step_0")
def signup_modal_step_0(ack, body, view, logger):
    signup.signup_modal_step_0(ack, body, view, logger)

@slack_app.view("signup_step_1")
def signup_modal_step_1(ack, body, view, logger):
    signup.signup_modal_step_1(ack, body, view, logger)

@slack_app.view("signup_step_2")
def signup_modal_step_2(ack, body, view, logger):
    signup.signup_modal_step_2(ack, body, view, logger)

@slack_app.view("signup_step_3")
def signup_modal_step_3(ack, body, view, logger):
    signup.signup_modal_step_3(ack, body, view, logger)

@slack_app.view("update_timezone")
def handle_update_timezone(ack, body, client, view, logger):
    settings.handle_update_timezone(ack, body, client, view, logger)

@slack_app.view("update_locations")
def handle_update_timezone(ack, body, client, view, logger):
    settings.handle_update_timezone(ack, body, client, view, logger)

@slack_app.action("set_timezone")
def set_timezone_modal(ack, body, logger):
    settings.set_timezone_modal(ack, body, logger)

@slack_app.action("edit_location")
def set_locations_modal(ack, body, logger):
    settings.set_locations_modal(ack, body, logger)

@slack_app.action("team_settings")
def edit_team_settings(ack, body, logger):
    settings.edit_team_settings(ack, body, logger)

@slack_app.action("open_survey")
def handle_post_completion_survey(ack, body, view, logger):
    survey.handle_post_completion_survey(ack, body, view, logger)

@slack_app.view("submit_survey")
def handle_submit_survey(ack, body, client, view, logger):
    survey.handle_submit_survey(ack, body, client, view, logger)

@slack_app.action("join_without_interest")
def join_without_interest(ack, body, logger):
    nook_channels.join_without_interest(ack, body, logger)

@slack_app.event("member_joined_channel")
def handle_member_joined_channel_events(body, logger):
    pass

@slack_app.view("enter_channel")
def update_message(ack, body, client, view, logger):
    nook_channels.update_message(ack, body, client, view, logger)

@slack_app.view("new_nook")
def handle_new_nook(ack, body, client, view, logger):
    nook_channels.handle_new_nook(ack, body, client, view, logger)

@slack_app.action("create_nook")
def create_nook_modal(ack, body, logger):
    nook_channels.create_nook_modal(ack, body, logger)

@slack_app.action("new_sample_nook")
def update_random_nook(ack, body, logger):
    nook_channels.update_random_nook(ack, body, logger)

@slack_app.action("nook_interested")
def nook_int(ack, body, logger):
    swiping.nook_int(ack, body, logger)

@slack_app.action("nook_not_interested")
def nook_not_int(ack, body, logger):
    swiping.nook_not_int(ack, body, logger)

def remove_stories_periodic(all_team_ids):
    for team_id in all_team_ids:
        remove_past_nooks(slack_app, db, nooks_alloc, team_id=team_id)


def post_stories_periodic(all_team_ids):

    for team_id in all_team_ids:

        current_nooks = list(db.nooks.find({"status": "show", "team_id": team_id}))

        allocations, suggested_allocs = nooks_alloc.create_nook_allocs(
            nooks=current_nooks, team_id=team_id
        )
        print(allocations, suggested_allocs)
        create_new_channels(
            slack_app, db, current_nooks, allocations, suggested_allocs, team_id=team_id
        )
        nooks_home.reset(team_id=team_id)

        token = get_token(team_id)

        for i, member in enumerate(nooks_alloc.all_members_ids[team_id]):
            try:
                nooks_home.update_home_tab(
                    client=slack_app.client,
                    event={"user": member, "view": {"team_id": team_id}},
                    token=token,
                )
            except Exception as e:
                print(e)


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
        for member in nooks_alloc.all_members_ids[team_id]:
            try:
                nooks_home.update_home_tab(
                    client=slack_app.client,
                    event={"user": member, "view": {"team_id": team_id}},
                    token=token,
                )
            except Exception as e:
                logging.info(e)


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


from flask import Flask, request, redirect
import requests

app = Flask(__name__)
cron = APScheduler()
cron.init_app(app)
cron.start()
handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
handler.connect()

@cron.task("cron", second="0")
def send_survey():
    survey.send_survey()


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
    remove_stories_periodic(get_team_rows_timezone("12:00", skip_weekends=False))
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
        target=settings.update_home_tab_all,
        kwargs={"token": get_token(team_id), "installed_team": installed_team},
    )
    thread.start()

    return "Successfully installed"


def main(nooks_home_arg, nooks_alloc_arg, onboarding_arg, signup_arg, swiping_arg, nook_channels_arg, guess_game_arg, survey_arg, settings_arg, beyond_nooks_arg, feedback_arg):
    global nooks_home
    global nooks_alloc
    global onboarding
    global signup
    global swiping
    global nook_channels
    global guess_game
    global survey
    global settings
    global beyond_nooks
    global feedback

    nooks_home = nooks_home_arg
    nooks_alloc = nooks_alloc_arg
    onboarding = onboarding_arg
    signup = signup_arg
    swiping = swiping_arg
    nook_channels = nook_channels_arg
    guess_game = guess_game_arg
    survey = survey_arg
    settings = settings_arg
    beyond_nooks = beyond_nooks_arg
    feedback = feedback_arg

    if "user_swipes" not in db.list_collection_names():
        db.create_collection("user_swipes")