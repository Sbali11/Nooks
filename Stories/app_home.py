# TODO add via
import os
import logging
import atexit
import random
import collections
import traceback
from datetime import datetime, timezone
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt.adapter.socket_mode import SocketModeHandler
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from bson import ObjectId

logging.basicConfig(level=logging.DEBUG)

# load environment variables
load_dotenv()

MAX_STORIES_GLOBAL = 10
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
MONGODB_LINK = os.environ["MONGODB_LINK"]
db_client = MongoClient(MONGODB_LINK)
db = db_client.trial_home

cron = BackgroundScheduler(daemon=True)
cron.start()
app = App()


def random_priority(creator, user, title, desc, to):
    p = random.randint(0, 2)
    return p

@app.event("app_home_opened")
def update_home_tab(client, event, logger):
    def default_message():
            client.views_publish(
                # Use the user ID associated with the event
                user_id=user_id,
                # Home tabs must be enabled in your app configuration
                view={
                    "type": "home",
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Welcome home, <@"
                                + event["user"]
                                + "> :house:*",
                            },
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "action_id": "create_story",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Create a new story!",
                                        "emoji": True,
                                    },
                                    "style": "primary",
                                    "value": "join",
                                }
                            ],
                        },
                        {"type": "divider"},
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": "You've exhausted your list for the day. I'll be back tomorrow :)  ",
                                "emoji": True,
                            },
                        },
                    ],
                },
            )
    user_id = event["user"]
    logging.info("UZZZ")
    all_stories = list(db.user_stories.find({"user_id": user_id, "status": "active"}))
    logging.info(all_stories)
    if not all_stories:
        default_message()
        return
    for stories_row in all_stories:
        # TODO do we need to do priority twice?
        logging.info("DZZZ")
        logging.info(type(stories_row["_id"]))
        cur_display_card = db.stories.find_one(
            {"status": "active", "_id": stories_row["story_id"]}
        )

        # db.stories.update({"_id": {"$in" : user_row["story_ids"]}},  {"$set" : {"status": "active", "channel_id": ep_channel}})
        # suggested_channels_info = [(suggested_story["title"] + " by @" + app.client.users_profile_get(user=suggested_story["creator"])["profile"]["real_name"] + "\n Description: " + suggested_story["description"], ep_channel, ts) for (suggested_story, ep_channel, ts) in channel_stories[channel]]
        logging.info("EEEZZZ")
        logging.info(cur_display_card)
        if not cur_display_card:
            default_message()
            return
        logging.info("TZZZ")
        client.views_publish(
            # Use the user ID associated with the event
            user_id=user_id,
            # Home tabs must be enabled in your app configuration
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Welcome home, <@" + event["user"] + "> :house:*",
                        },
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "action_id": "create_story",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Create a new story!",
                                    "emoji": True,
                                },
                                "style": "primary",
                                "value": "join",
                            }
                        ],
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "plain_text",
                            "text": "P.S People want to hear your thoughts in these spaces. Join in soon (they only last a day!)  ",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "text",
                                "text": {
                                    "type": "plain_text",
                                    "text": cur_display_card["title"]
                                    + "\n Description: "
                                    + cur_display_card["description"],
                                },
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Pass :x:",
                                    "emoji": True,
                                },
                                "value": str(stories_row["_id"]),
                                "action_id": "story_interested",
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Join in :heavy_check_mark:",
                                    "emoji": True,
                                },
                                "value": str(stories_row["_id"]),
                                "action_id": "pass_story",
                            },
                        ],
                    },
                ],
            },
        )


@app.view("new_story")
def handle_submission(ack, body, client, view, logger):
    ack()
    # TODO create a new name if taken?
    input_data = view["state"]["values"]
    user = body["user"]["id"]
    title = input_data["title"]["plain_text_input-action"]["value"]
    desc = input_data["desc"]["plain_text_input-action"]["value"]
    to = input_data["to"]["text1234"]["selected_conversations"]

    new_story_info = {
        "title": title,
        "creator": user,
        "description": desc,
        "to": to,
        "status": "suggested",
        "created_on": datetime.utcnow(),
    }
    db.stories.insert_one(new_story_info)
    app.client.chat_postMessage(
        link_names=True,
        channel=user,
        text="Nice! I've added your story titled " + title + " to the queue. ",
    )


@app.action("create_story")
def create_story_modal(ack, body, logger):
    ack()
    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "new_story",
            "title": {"type": "plain_text", "text": "Create a Story!"},
            "close": {"type": "plain_text", "text": "Close"},
            "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Let's start discussing :smile:.",
                    },
                },
                {
                    "block_id": "title",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "plain_text_input-action",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Give your story an interesting title",
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
                    "block_id": "to",
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Pick conversations to send the story to",
                    },
                    "accessory": {
                        "action_id": "text1234",
                        "type": "multi_conversations_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select conversations",
                        },
                    },
                },
            ],
        },
    )


@app.action("story_interested")
def initial_thoughts_modal(ack, body, logger):
    ack()
    user_story_id = body["actions"][0]["value"]
    user_story = db.user_stories.find_one({"_id": ObjectId(user_story_id)})

    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "enter_channel",
            "private_metadata": user_story["story_id"],
            "title": {"type": "plain_text", "text": "Story"},
            "close": {"type": "plain_text", "text": "Close"},
            "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Yay, we're all excited to learn more about your thoughts. ",
                    },
                },
                {
                    "block_id": "initial_thoughts",
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
            ],
        },
    )

    db.user_stories.update(
        {"_id": ObjectId(user_story_id)}, {"$set": {"status": "entered"}}
    )


@app.view("enter_channel")
def update_message(ack, body, client, view, logger):
    ack()
    story_id = view["private_metadata"]
    story = db.stories.find_one({"_id": ObjectId(story_id)})
    ep_channel, thread_ts = story["channel_id"], story["ts"]
    input_data = view["state"]["values"]
    user_id = body["user"]["id"]
    user = app.client.users_profile_get(user=user_id)
    initial_thoughts = input_data["initial_thoughts"]["plain_text_input-action"][
        "value"
    ]
    try:
        app.client.conversations_invite(channel=ep_channel, users=user_id)
        app.client.chat_postMessage(
            link_names=True,
            channel=ep_channel,
            thread_ts=thread_ts,
            username=user["profile"]["real_name"],
            icon_url=user["profile"]["image_24"],
            reply_broadcast=True,
            text=initial_thoughts,
        )
    except Exception as e:
        logging.error(traceback.format_exc())


# Add functionality here
from flask import Flask, request

flask_app = Flask(__name__)
handler = SocketModeHandler(app, SLACK_APP_TOKEN)
handler.connect()


def update_past_stories_and_notifs():
    active_stories = list(db.stories.find({"status": "active"}))
    # db.user_stories.find(
    db.user_stories.remove()

    for active_story in active_stories:
        try:
            app.client.conversations_archive(channel=active_story["channel_id"])
            db.stories.update(
                {"_id": active_story["_id"]}, {"$set": {"status": "archived"}}
            )

        except Exception as e:
            logging.error(traceback.format_exc())
    past_notifications = list(db.active_notifications.find())
    for past_notification in past_notifications:
        try:
            app.client.chat_delete(
                channel=past_notification["channel_id"], ts=past_notification["ts"]
            )
            db.active_notifications.remove({"_id": past_notification["_id"]})

        except Exception as e:
            logging.error(traceback.format_exc())


# TODO add partition-wise ranking?
def get_top_stories():
    user_stories = {}
    stories_ranking = collections.defaultdict(int)
    all_users = app.client.users_list()["members"]

    for user in all_users:
        user_id = user["id"]
        all_channels = [
            channel["id"]
            for channel in app.client.users_conversations(user=user_id)["channels"]
        ]
        story_suggestions = list(
            db.stories.find({"status": "suggested", "to": {"$in": all_channels}})
        )

        # TODO any way to vectorize this?
        for story in story_suggestions:
            p = random_priority(
                story["creator"],
                user_id,
                story["title"],
                story["description"],
                story["to"],
            )
            story["priority"] = p
            stories_ranking[story["_id"]] += p
        user_stories[user_id] = story_suggestions
    stories_list = [(stories_ranking[story], story) for story in stories_ranking]
    stories_to_add = sorted(stories_list, reverse=True)[:MAX_STORIES_GLOBAL]
    stories_to_add = {s for _, s in stories_to_add}

    for story_id in stories_to_add:
        suggested_story = db.stories.find_one({"_id": story_id})
        title = "story_" + suggested_story["title"]
        creator = suggested_story["creator"]
        desc = suggested_story["description"]
        to_channels = suggested_story["to"]
        try:
            logging.info("FZZZ")
            response = app.client.conversations_create(name=title, is_private=True)
            ep_channel = response["channel"]["id"]
            initial_thoughts_thread = app.client.chat_postMessage(
                link_names=True,
                channel=ep_channel,
                text="Hmm I'm not advanced enough to have thoughts of my own. But this is what everyone thought while joining",
            )
            # TODO do we need this anymore?
            db.stories.update(
                {"_id": story_id},
                {
                    "$set": {
                        "status": "active",
                        "channel_id": ep_channel,
                        "ts": initial_thoughts_thread["ts"],
                    }
                },
            )
            all_users = set([])
            for channel in to_channels:
                all_users = all_users.union(
                    set(app.client.conversations_members(channel=channel)["members"])
                )
            logging.info("TZZZ")
            logging.info(all_users)
            db.user_stories.insert(
                {"user_id": user_id, "story_id": story_id, "status": "active"}
                for user_id in all_users
            )

        except Exception as e:
            logging.error(traceback.format_exc())


# TODO change this to hour for final
@cron.scheduled_job("cron", second="10")
def post_stories():

    update_past_stories_and_notifs()
    get_top_stories()
    def default_message():
            client.views_publish(
                # Use the user ID associated with the event
                user_id=user_id,
                # Home tabs must be enabled in your app configuration
                view={
                    "type": "home",
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Welcome home, <@"
                                + event["user"]
                                + "> :house:*",
                            },
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "action_id": "create_story",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Create a new story!",
                                        "emoji": True,
                                    },
                                    "style": "primary",
                                    "value": "join",
                                }
                            ],
                        },
                        {"type": "divider"},
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": "You've exhausted your list for the day. I'll be back tomorrow :)  ",
                                "emoji": True,
                            },
                        },
                    ],
                },
            )
    user_id = event["user"]
    logging.info("UZZZ")
    all_stories = list(db.user_stories.find({"user_id": user_id, "status": "active"}))
    logging.info(all_stories)
    if not all_stories:
        default_message()
        return
    for stories_row in all_stories:
        # TODO do we need to do priority twice?
        logging.info("DZZZ")
        logging.info(type(stories_row["_id"]))
        cur_display_card = db.stories.find_one(
            {"status": "active", "_id": stories_row["story_id"]}
        )

        # db.stories.update({"_id": {"$in" : user_row["story_ids"]}},  {"$set" : {"status": "active", "channel_id": ep_channel}})
        # suggested_channels_info = [(suggested_story["title"] + " by @" + app.client.users_profile_get(user=suggested_story["creator"])["profile"]["real_name"] + "\n Description: " + suggested_story["description"], ep_channel, ts) for (suggested_story, ep_channel, ts) in channel_stories[channel]]
        logging.info("EEEZZZ")
        logging.info(cur_display_card)
        if not cur_display_card:
            default_message()
            return
        logging.info("TZZZ")
        client.views_publish(
            # Use the user ID associated with the event
            user_id=user_id,
            # Home tabs must be enabled in your app configuration
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Welcome home, <@" + event["user"] + "> :house:*",
                        },
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "action_id": "create_story",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Create a new story!",
                                    "emoji": True,
                                },
                                "style": "primary",
                                "value": "join",
                            }
                        ],
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "plain_text",
                            "text": "P.S People want to hear your thoughts in these spaces. Join in soon (they only last a day!)  ",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "text",
                                "text": {
                                    "type": "plain_text",
                                    "text": cur_display_card["title"]
                                    + "\n Description: "
                                    + cur_display_card["description"],
                                },
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Pass :x:",
                                    "emoji": True,
                                },
                                "value": str(stories_row["_id"]),
                                "action_id": "story_interested",
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Join in :heavy_check_mark:",
                                    "emoji": True,
                                },
                                "value": str(stories_row["_id"]),
                                "action_id": "pass_story",
                            },
                        ],
                    },
                ],
            },
        )


atexit.register(lambda: cron.shutdown(wait=False))

if __name__ == "__main__":
    flask_app.run(debug=True, use_reloader=False)
