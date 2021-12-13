#TODO add via
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

logging.basicConfig(level=logging.DEBUG)

# load environment variables
load_dotenv()

MAX_STORIES_GLOBAL = 10
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
MONGODB_LINK = os.environ["MONGODB_LINK"]
db_client = MongoClient(MONGODB_LINK)
db = db_client.trial_individual

cron = BackgroundScheduler(daemon=True)
cron.start()
app = App()



def random_priority(creator, user, title, desc, to):
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
        "created_on": datetime.utcnow()
    }    
    db.stories.insert_one(new_story_info)
    app.client.chat_postMessage(link_names=True,channel=user,
                                text="Nice! I've added your story titled " + title + " to the queue. ")
   
    
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
    
    if body["actions"][0]["name"] == "next":
        metadata = body["actions"][0]["value"].split("`")
        
        ep_channel, chat_ts, user_id, cur_id_str = metadata[0], metadata[1], metadata[2], metadata[3]
        past_notifications = list(db.active_notifications.find({'channel': user_id}))
        for past_notification in past_notifications:
            try: 
                app.client.chat_delete(channel=past_notification['channel_id'], ts=past_notification['ts'])
                db.active_notifications.remove({"_id": past_notification["_id"]})

            except Exception as e:
                logging.error(traceback.format_exc())
        user_row = list(db.user_stories.find({"user_id": user_id}))[0]
        logging.info(user_row)
        #suggested_channels_info = [info.split('¢') for info in suggested_channels_info_str.split(',')]
        suggested_stories = list(db.stories.find({"status": "active", "_id": {"$in" : user_row["story_ids"]}}))
        logging.info(suggested_stories)
        #body["actions"][0]["suggested_channels_info"]
        cur_id = int(cur_id_str)
        cur_id += 1
        if cur_id >= len(suggested_stories):
            logging.info("EEWEDRE")
            story_notifs_response = app.client.chat_postMessage(link_names =True,channel=user_id,
                                text="You've exhausted all our recommendations for the day. I'll be back tomorrow with more :)")
            db.active_notifications.insert_one({'channel_id': user_id, 'ts': story_notifs_response['ts']})

        else:
            cur_display_card = suggested_stories[cur_id]
            logging.info("WEEWFREF")
            msg_attachments = []
            logging.info(app.client.conversations_members(channel=cur_display_card["channel_id"])["members"])
            if user_id not in app.client.conversations_members(channel=cur_display_card["channel_id"])["members"]:
                msg_attachments.append({"name": "join_in",
                                        "text": "Join In",
                                        "type": "button",
                                        "value": cur_display_card["channel_id"] + "`" + cur_display_card["ts"]
                                        })
            story_notifs_response = app.client.chat_postMessage(link_names =True,channel=body["original_message"]["user"],
                                text="I have more options!",
                                attachments = [
                                                {
                                                    "text" : cur_display_card["title"] + " by @" + app.client.users_profile_get(user=cur_display_card["creator"])["profile"]["real_name"] + "\n Description: " + cur_display_card["description"],
                                                    "fallback": "You are unable to join in",
                                                    "callback_id": "enter_story",
                                                    "color": "#3AA3E3",
                                                    "attachment_type": "default",
                                                    "actions": 
                                                        msg_attachments + [{
                                                            "name": "next",
                                                            "text": "Next",
                                                            "type": "button",
                                                            "value": cur_display_card["channel_id"] + "`" + cur_display_card["ts"] + "`" + user_id +  "`"  + str(cur_id),

                                                            #"value": cur_display_card[1] + ":" + cur_display_card[2],
                                                            #"suggested_channels_info": suggested_channels_info,
                                                            #"cur_id": 0
                                                        }
                                                    ]
                                            } 
                                ] )
            db.active_notifications.insert_one({'channel_id': user_id, 'ts': story_notifs_response['ts']})

    else: 
        app.client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "enter_channel", 
                "private_metadata": body["actions"][0]["value"],
                "title": {"type": "plain_text", "text": "Story"},
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
    private_data = view["private_metadata"].split('`')
    ep_channel, thread_ts = private_data[0], private_data[1]

    input_data = view["state"]["values"]
    user_id = body["user"]["id"]
    user = app.client.users_profile_get(user=user_id)
    initial_thoughts = input_data["initial_thoughts"]["plain_text_input-action"]["value"]
    try:
        app.client.conversations_invite(channel=ep_channel, users=user_id)
        app.client.chat_postMessage(link_names =True,channel=ep_channel, thread_ts=thread_ts, 
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
    #db.user_stories.find(
    db.user_stories.remove()

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

# TODO add partition-wise ranking?
def get_top_stories():
    user_stories = {}
    story_channel = {}
    final_user_stories = {}
    stories_ranking = collections.defaultdict(int)
    all_users = app.client.users_list()["members"]

    for user in all_users:
        user_id = user["id"]
        all_channels = [channel["id"] for channel in app.client.users_conversations(user=user_id)["channels"]]
        story_suggestions = list(db.stories.find({"status": "suggested", "to": {"$in": all_channels}}))        
        
        # TODO any way to vectorize this?
        for story in story_suggestions:
            p = random_priority(story['creator'], user_id, story['title'], story['description'], story['to'])
            story['priority'] = p
            stories_ranking[story['_id']] += p
        user_stories[user_id] = story_suggestions
    stories_list = [(stories_ranking[story], story) for story in stories_ranking]
    stories_to_add = sorted(stories_list, reverse=True)[:MAX_STORIES_GLOBAL]
    stories_to_add = {s for _, s in stories_to_add}
    for story_id in stories_to_add:
        suggested_story = list(db.stories.find({"_id": story_id}))[0]
        logging.info("ZZZZZ")
        logging.info(suggested_story)
        title = 'story_' + suggested_story["title"]
        creator = suggested_story["creator"]
        desc = suggested_story["description"]
        channels = suggested_story["to"]
        try:
            response = app.client.conversations_create(name=title, is_private=True)
            ep_channel = response["channel"]["id"]
            
            #app.client.conversations_invite(channel=ep_channel, users=creator)
            initial_thoughts_thread = app.client.chat_postMessage(link_names =True,channel=ep_channel, text="Hmm I'm not advanced enough to have thoughts of my own. But this is what everyone thought while joining")
            db.stories.update({"_id": suggested_story["_id"]},  {"$set" : {"status": "active", "channel_id": ep_channel, "ts": initial_thoughts_thread['ts']}})

        except Exception as e:
            logging.error(traceback.format_exc())

    # TODO vectorize this!! + decrease the duplication
    for user_id in user_stories:
        final_user_story = []
        for story in user_stories[user_id]:
            if story['_id'] in stories_to_add:
                final_user_story.append(story["_id"])
        if final_user_story:
            db.user_stories.insert_one({'user_id': user_id, 'story_ids': final_user_story})

# TODO change this to hour for final
@cron.scheduled_job("cron", second="10")
def post_stories():

    update_past_stories_and_notifs()
    get_top_stories()
    logging.info("XXXXX")
    for user_row in db.user_stories.find():
        # TODO needs to be a better way to do this
        channel = user_row["user_id"]
        logging.info(channel)
        suggested_stories = list(db.stories.find({"status": "active", "_id": {"$in" : user_row["story_ids"]}}))
        #suggested_story["title"] + " by @" + app.client.users_profile_get(user=suggested_story["creator"])["profile"]["real_name"] + "\n Description: " + suggested_story["description"], ep_channel, ts
        #db.stories.update({"_id": {"$in" : user_row["story_ids"]}},  {"$set" : {"status": "active", "channel_id": ep_channel}})

        #suggested_channels_info = [(suggested_story["title"] + " by @" + app.client.users_profile_get(user=suggested_story["creator"])["profile"]["real_name"] + "\n Description: " + suggested_story["description"], ep_channel, ts) for (suggested_story, ep_channel, ts) in channel_stories[channel]]
        if not suggested_stories:
            continue
        cur_display_card = suggested_stories[0]
        msg_attachments = []
        if user_row["user_id"] not in app.client.conversations_members(channel=cur_display_card["channel_id"]):
            msg_attachments.append({"name": "join_in",
                                    "text": "Join In",
                                    "type": "button",
                                    "value": cur_display_card["channel_id"] + "`" + cur_display_card["ts"]
                                })
        
        #suggested_story["title"] + " by @" + app.client.users_profile_get(user=suggested_story["creator"])["profile"]["real_name"] + "\n Description: " + suggested_story["description"]
        story_notifs_response = app.client.chat_postMessage(link_names =True,channel=channel,
                                text="Psss it's that :clock1: of the day again! I have new stories for you!",
                                attachments = [
                                                {
                                                    "text" : cur_display_card["title"] + " by @" + app.client.users_profile_get(user=cur_display_card["creator"])["profile"]["real_name"] + "\n Description: " + cur_display_card["description"],
                                                    "fallback": "You are unable to join in",
                                                    "callback_id": "enter_story",
                                                    "color": "#3AA3E3",
                                                    "attachment_type": "default",
                                                    "actions": 
                                                    msg_attachments + [
                                                        {
                                                            "name": "next",
                                                            "text": "Next",
                                                            "type": "button",
                                                            "value": cur_display_card["channel_id"] + "`" + cur_display_card["ts"] + "`" + user_row["user_id"] + "`" + str(0),

                                                            #"value": cur_display_card[1] + ":" + cur_display_card[2],
                                                            #"suggested_channels_info": suggested_channels_info,
                                                            #"cur_id": 0
                                                        }
                                                    ]
                                            } 
                                ] )

        db.active_notifications.insert_one({'channel_id': channel, 'ts': story_notifs_response['ts']})

atexit.register(lambda: cron.shutdown(wait=False))

if __name__ == "__main__":
    flask_app.run(debug=True, use_reloader=False)