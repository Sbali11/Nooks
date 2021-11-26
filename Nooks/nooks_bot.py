# TODO do we need to store current user swipes?
# TODO add don't send the story to
# TODO valid story title
# TODO convert to bulk ops?
# TODO error correcting on NooksHome in case server breaks?
# TODO save channel history
import os
import logging
import atexit
import random
import collections
import traceback
from datetime import datetime, timezone
from utils import NooksHome, NooksAllocation
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt.adapter.socket_mode import SocketModeHandler
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from bson import ObjectId
import numpy as np

logging.basicConfig(level=logging.DEBUG)

# load environment variables
load_dotenv()
NUM_MEMBERS = 2
MEMBER_FEATURES = 2
MAX_STORIES_GLOBAL = 10
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
MONGODB_LINK = os.environ["MONGODB_LINK"]

db = MongoClient(MONGODB_LINK).nooks
app = App()     

cron = BackgroundScheduler(daemon=True)
cron.start()


def random_priority(creator, user, title, desc, to):
    p = random.randint(0, 2)
    return p

@app.view("new_story")
def handle_submission(ack, body, client, view, logger):
    ack()
    # TODO create a new name if taken?
    input_data = view["state"]["values"]
    user = body["user"]["id"]
    title = input_data["title"]["plain_text_input-action"]["value"]
    desc = input_data["desc"]["plain_text_input-action"]["value"]
    banned = input_data["banned"]["text1234"]["selected_conversations"]
    new_story_info = {
        "title": title,
        "creator": user,
        "description": desc,
        "banned": banned,
        "status": "suggested",
        "created_on": datetime.utcnow(),
        "swiped_right": []
    }
    db.stories.insert_one(new_story_info)
    app.client.chat_postMessage(
        link_names=True,
        channel=user,
        text="Hey! I've added your story titled " + title + " to the queue. ",
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
                    "block_id": "banned",
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
                            "text": "Are there any people you don't want to be a part of this conversations",
                        },
                    },
                },
            ],
        },
    )


@app.action("story_interested")
def initial_thoughts_modal(ack, body, logger):
    ack()
    user_id = body["user"]["id"]
    cur_pos = int(body["actions"][0]["value"])
    user_story = nooks_home.suggested_stories[cur_pos]
    db.user_swipes.update_one(
                {"user_id": user_id},
                {"$set":{"cur_pos": cur_pos+1}}
    )
    db.stories.update(
        {"_id": user_story["_id"]}, 
        {
        "$push": {
            "swiped_right": user_id
        }}
    )
    nooks_home.update_home_tab(app.client, {"user": user_id})

@app.action("story_not_interested")
def initial_thoughts_modal(ack, body, logger):
    ack()
    user_id = body["user"]["id"]
    cur_pos = int(body["actions"][0]["value"])
    user_story = nooks_home.suggested_stories[cur_pos]
    db.user_swipes.update_one(
                {"user_id": user_id},
                {"$set":{"cur_pos": cur_pos+1}}
    )
    db.stories.update(
        {"_id": user_story["_id"]}, 
        {
        "$push": {
            "swiped_left": user_id
        }}
    )
    nooks_home.update_home_tab(app.client, {"user": user_id})


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


@app.event("app_home_opened")
def update_home_tab(client, event, logger):
    nooks_home.update_home_tab(client, event, logger)

# Add functionality here
from flask import Flask, request

flask_app = Flask(__name__)
handler = SocketModeHandler(app, SLACK_APP_TOKEN)
handler.connect()

def remove_past_stories():
    active_stories = list(db.stories.find({"status": "active"}))
    # archive all channels of the past day
    for active_story in active_stories:
        try:
            db.stories.update(
                {"_id": active_story["_id"]}, 
                {
                    "$set": {
                        "status": "archived"
                    }
                }
            )
            app.client.conversations_archive(channel=active_story["channel_id"])

        except Exception as e:
            logging.error(traceback.format_exc())

def create_new_channels(new_stories, allocations):
    # create new channels for the day
    
    for new_story in new_stories:
        title = "sok_" + new_story["title"]
        creator = new_story["creator"]
        desc = new_story["description"]
        try:
            response = app.client.conversations_create(name="pkk", is_private=False)
            ep_channel = response["channel"]["id"]
            initial_thoughts_thread = app.client.chat_postMessage(
                link_names=True,
                channel=ep_channel,
                text="Hmm I'm not advanced enough to have thoughts of my own. But this is what everyone thought while joining",
            )
            app.client.conversations_invite(channel=ep_channel, users=allocations[new_story["_id"]])
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
        except Exception as e:
            logging.error(traceback.format_exc())
        return new_stories

def update_story_suggestions():
    # all stories
    suggested_stories = list(db.stories.find({"status": "suggested"}))
    #db.user_swipes.remove()
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
    return suggested_stories

# TODO change this to hour for final
@cron.scheduled_job("cron", second="10")
def post_stories():
    
    remove_past_stories()
    current_stories = list(db.stories.find({"status": "show"}))
    allocations = nooks_alloc.create_nook_allocs(nooks=current_stories)
    create_new_channels(current_stories, allocations)
    
    suggested_stories = update_story_suggestions()
    nooks_home.update(suggested_stories=suggested_stories)

    
atexit.register(lambda: cron.shutdown(wait=False))

if __name__ == "__main__":
    db.user_swipes.remove()
    if "user_swipes" not in db.list_collection_names():
        db.create_collection("user_swipes")
    
    #db.member_vectors.remove()
    #db.all_interacted.remove()
    #db.temporal_interacted.remove()
    # TODO shift to onboarding
    if "member_vectors" not in db.list_collection_names():
        db.create_collection("member_vectors")
        db.member_vectors.create_index("user_id")
        all_members =  app.client.users_list()["members"]
        
        member_vectors = np.random.randint(2, size=(len(all_members), MEMBER_FEATURES))
        db.member_vectors.insert_many([{"user_id": member["id"], "member_vector": member_vectors[i].tolist()} for i, member in enumerate(all_members)])
        
        member_interacted = np.zeros((len(all_members), len(all_members)))
        db.create_collection("all_interacted")
        db.create_collection("temporal_interacted")
        
        db.all_interacted.insert_many([{"user_id": member["id"], "counts": member_interacted[i].tolist()} for i, member in enumerate(all_members)])
        db.temporal_interacted.insert_many([{"user_id": member["id"], "counts": member_interacted[i].tolist()} for i, member in enumerate(all_members)])

    nooks_home = NooksHome(db=db)
    nooks_alloc = NooksAllocation(db=db)
    flask_app.run(debug=True, use_reloader=False)

