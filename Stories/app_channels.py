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

logging.basicConfig()

# load environment variables
load_dotenv()

MAX_STORIES_GLOBAL = 4
MAX_STORIES_CHANNEL = 1
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
MONGODB_LINK = os.environ["MONGODB_LINK"]

cron = BackgroundScheduler(daemon=True)
cron.start()
app = App()
db_client = MongoClient(MONGODB_LINK)
db = db_client.trial_channels_3


def random_priority(user, title, desc, to):
    p = random.randint(0, 2)
    return p

@app.view("new_story")
def handle_submission(ack, body, client, view, logger):
    ack()
    #TODO create a new name if taken?
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
        "priority": random_priority(user, title, desc, to), 
        "created_on": datetime.utcnow()
    }    
    db.stories.insert_one(new_story_info)
   
    
@app.command("/create_story")
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
                        "text": "Let's start discussing :smile:."
                    }
                },
		        {
                    "block_id": "title",
			        "type": "input",
			        "element": {
				        "type": "plain_text_input",
				        "action_id": "plain_text_input-action"
			        },
			        "label": {
				        "type": "plain_text",
				        "text": "Give your story an interesting title",
				        "emoji": True
			        }
		        }, 
		        {
                    "block_id": "desc",
			        "type": "input",
			        "element": {
				        "type": "plain_text_input",
				        "multiline": True,
				        "action_id": "plain_text_input-action"
			        },
			        "label": {
				        "type": "plain_text",
				        "text": "Add some initial thoughts",
				        "emoji": True
			        }
		        },
                {
                    "block_id": "to",
                    "type": "section",
                    "text": 
                    {
                        "type": "mrkdwn",
                        "text": "Pick conversations to send the story to"
                    },
                    "accessory": 
                    {
                        "action_id": "text1234",
                        "type": "multi_conversations_select",
                        "placeholder": 
                        {
                            "type": "plain_text",
                            "text": "Select conversations"
                        }
                    }
                }
            ]
        }
    )

@app.action("enter_story")
def initial_thoughts_modal(ack, body, logger):
    ack()
    app.client.views_open(
        trigger_id=body["trigger_id"],
        
        view={
            "type": "modal",
            "callback_id": "enter_channel", 
            "private_metadata": body["actions"][0]["value"],
            "title": {"type": "plain_text", "text": "Noice"},
            "close": {"type": "plain_text", "text": "Close"},
            "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
            "blocks": [
                {
                    
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Yay, we're all excited to learn more about your thoughts. "
                    }
                },
		        {
                    "block_id": "initial_thoughts",
			        "type": "input",
			        "element": {
				        "type": "plain_text_input",
				        "multiline": True,
				        "action_id": "plain_text_input-action"
			        },
			        "label": {
				        "type": "plain_text",
				        "text": "Add some initial thoughts",
				        "emoji": True
			        }
		        },
            ]
        }
    )

@app.view("enter_channel")
def update_message(ack, body, client, view, logger):
    ack()
    private_data = view["private_metadata"].split(':')
    ep_channel, thread_ts = private_data[0], private_data[1]

    input_data = view["state"]["values"]
    user_id = body["user"]["id"]
    user = app.client.users_profile_get(user=user_id)
    initial_thoughts = input_data["initial_thoughts"]["plain_text_input-action"]["value"]
    try:
        app.client.conversations_invite(channel=ep_channel, users=user_id)
        app.client.chat_postMessage(channel=ep_channel, thread_ts=thread_ts, 
                                    username=user["profile"]["real_name"], 
                                    icon_url=user["profile"]["image_24"],
                                    reply_broadcast=True,
                                    text=initial_thoughts)
    except Exception as e:
        logging.error(traceback.format_exc())

# Add functionality here
from flask import Flask, request

flask_app = Flask(__name__)
handler = SocketModeHandler(app, SLACK_APP_TOKEN)
handler.connect()


def update_past_stories_and_notifs():
    active_stories = list(db.stories.find({'status': 'active'}))
    for active_story in active_stories:
        try: 
            app.client.conversations_archive(channel=active_story["channel_id"])
            db.stories.update({"_id": active_story["_id"]},  {"$set" : {"status": "archived"}})

        except Exception as e:
            logging.error(traceback.format_exc())
    past_notifications = list(db.active_notifications.find())
    for past_notification in past_notifications:
        try: 
            app.client.chat_delete(channel=past_notification['channel_id'], ts=past_notification['ts'])
            db.active_notifications.remove({"_id": past_notification["_id"]})

        except Exception as e:
            logging.error(traceback.format_exc())

def get_top_stories():
    channel_stories = collections.defaultdict(list)
    stories_to_add = set([])
    all_channels = app.client.conversations_list()["channels"]

    for channel in all_channels:
        channel_id = channel["id"]
        story_suggestions = list(db.stories.find({"status": "suggested", "to": channel_id}).sort("priority",-1).limit(MAX_STORIES_CHANNEL))
        stories_to_add = stories_to_add.union({suggested_story["_id"] for suggested_story in story_suggestions})
    logging.info("TZZZZ")
    logging.info(stories_to_add)

    for story_id in stories_to_add:
        suggested_story = db.stories.find({"_id": story_id})[0]
        title = 'story_' + suggested_story["title"]
        creator = suggested_story["creator"]
        desc = suggested_story["description"]
        channels = suggested_story["to"]
        logging.info("TITLE_Z")
        logging.info(title)
        try:
            response = app.client.conversations_create(name=title, is_private=True)
            ep_channel = response["channel"]["id"]
            #app.client.conversations_invite(channel=ep_channel, users=creator)
            initial_thoughts_thread = app.client.chat_postMessage(channel=ep_channel, text="Hmm I'm not advanced enough to have thoughts of my own. But this is what everyone thought while joining")
            db.stories.update({"_id": suggested_story["_id"]},  {"$set" : {"status": "active", "channel_id": ep_channel}})
            for channel in channels:
                channel_stories[channel].append((suggested_story, ep_channel, initial_thoughts_thread['ts']))
            

        except Exception as e:
            logging.info("TEEZZ")
            logging.info(title)
            logging.error(traceback.format_exc())
    logging.info(channel_stories)
    return channel_stories

# TODO change this to hour for final
@cron.scheduled_job("cron", second="10")
def post_stories():

    update_past_stories_and_notifs()
    channel_stories = get_top_stories()
    
    for channel in channel_stories:
        story_notifs_response = app.client.chat_postMessage(channel=channel,
                                text="Psss it's that :clock1: of the day again! I have new stories for you!",
                                attachments = [
                                                {
                                                    "text" : suggested_story["title"] + " by @" + app.client.users_profile_get(user=suggested_story["creator"])["profile"]["real_name"] + "\n Description: " + suggested_story["description"],
                                                    "fallback": "You are unable to join in",
                                                    "callback_id": "enter_story",
                                                    "color": "#3AA3E3",
                                                    "attachment_type": "default",
                                                    "actions": 
                                                    [
                                                        {
                                                            "name": "join_in",
                                                            "text": "Join In",
                                                            "type": "button",
                                                            "value": ep_channel + ":" + ts
                                                        }

                                                    ]
                                            } for suggested_story, ep_channel, ts in channel_stories[channel]
                                ] )
        db.active_notifications.insert_one({'channel_id': channel, 'ts': story_notifs_response['ts']})

atexit.register(lambda: cron.shutdown(wait=False))

if __name__ == "__main__":
    flask_app.run(debug=True, use_reloader=False)