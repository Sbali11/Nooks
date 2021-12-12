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

db = MongoClient(MONGODB_LINK).nooks_db

app = App()

cron = BackgroundScheduler(daemon=True)
cron.start()


@app.view("new_story")
def handle_new_story(ack, body, client, view, logger):
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
        "swiped_right": [],
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
                        "type": "multi_conversations_select",
                    },
                },
            ],
        },
    )


@app.action("story_interested")
def nook_int(ack, body, logger):
    ack()
    user_id = body["user"]["id"]
    cur_pos = int(body["actions"][0]["value"])
    user_story = nooks_home.suggested_stories[cur_pos]
    db.user_swipes.update_one({"user_id": user_id}, {"$set": {"cur_pos": cur_pos + 1}})
    db.stories.update({"_id": user_story["_id"]}, {"$push": {"swiped_right": user_id}})
    nooks_home.update_home_tab(app.client, {"user": user_id})


@app.action("story_not_interested")
def nook_not_int(ack, body, logger):
    ack()
    user_id = body["user"]["id"]
    cur_pos = int(body["actions"][0]["value"])
    user_story = nooks_home.suggested_stories[cur_pos]
    db.user_swipes.update_one({"user_id": user_id}, {"$set": {"cur_pos": cur_pos + 1}})
    db.stories.update({"_id": user_story["_id"]}, {"$push": {"swiped_left": user_id}})
    nooks_home.update_home_tab(app.client, {"user": user_id})

@app.view("send_dm")
def handle_send_message(ack, body, client, view, logger):
    ack()
    # TODO create a new name if taken?
    input_data = view["state"]["values"]
    to_user = view["private_metadata"]
    message = input_data["message"]["plain_text_input-action"]["value"]

    app.client.chat_postMessage(
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


@app.action("customize_dm")
def customize_dm_modal(ack, body, client, view, logger):
    ack()
    
    # TODO create a new name if taken?
    from_user = body["user"]["id"]
    to_user = body["actions"][0]["value"]
    # db.personal_message.insert_one(new_story_info)
    # app.client.conversations_open(users=to_user)
    #return
    app.client.views_open(
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


@app.view("send_message")
def handle_send_message(ack, body, client, view, logger):
    ack()
    input_data = view["state"]["values"]
    from_user = body["user"]["id"]

    logging.info("BZZZZ")
    logging.info(view)

    to_user = view["private_metadata"]
    message = input_data["message"]["plain_text_input-action"]["value"]
    logging.info("VZZZ")
    logging.info(body)
    logging.info(view)
    new_story_info = {"message": message, "from_user": from_user, "to_user": to_user}
    db.personal_message.insert_one(new_story_info)
    app.client.chat_postMessage(
        link_names=True,
        channel=to_user,
        
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Hey @" + app.client.users_profile_get(user=from_user)["profile"][
                            "real_name"
                        ] + " loved talking to you and would like to talk more. Here's what they said!",
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


@app.action("contact_person")
def contact_modal(ack, body, logger):
    ack()
    from_user = body["user"]["id"]
    to_user = body["actions"][0]["value"]

    app.client.views_open(
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
                        "initial_value": "Hey! Will you be free for a quick Zoom call anytime soon?"

                        ,
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


@app.view("add_member")
def handle_signup(ack, body, client, view, logger):
    ack()
    # TODO create a new name if taken?
    input_data = view["state"]["values"]
    user = body["user"]["id"]
    new_member_info = {}
    for key in input_data:
        new_member_info[key] = input_data[key]["plain_text_input-action"]["value"]
    new_member_info["user_id"] = user
    new_member_info["member_vector"] = get_member_vector(new_member_info)
    db.member_vectors.insert_one(new_member_info)

    app.client.chat_postMessage(
        link_names=True,
        channel=user,
        text="You're all set! Create your first story ",
    )


@app.action("signup")
def signup_modal(ack, body, logger):
    ack()
    user = body["user"]["id"]
    if db.member_vector.find_one({"user_id": user}):
        app.client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "add_member",
                "title": {"type": "plain_text", "text": "Sign Up!"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Looks like you're already signed up! If you want to withdraw consent or change any information on your profile, contact sbali@andrew.cmu.edu",
                        },
                    },
                ],
            },
        )
        return

    # TODO check if member is already in database?
    app.client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "add_member",
            "title": {"type": "plain_text", "text": "Sign Up!"},
            "close": {"type": "plain_text", "text": "Close"},
            "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "To help me optimize your lists, tell me a bit about yourself",
                    },
                },
                {
                    "block_id": "gender",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "plain_text_input-action",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Gender",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "age",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "plain_text_input-action",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Age",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "yrs_org",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "plain_text_input-action",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Number of years in this organization",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "core_periphery",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "plain_text_input-action",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Do you consider yourself to be well connected in the organization?",
                        "emoji": True,
                    },
                },
            ],
        },
    )


@app.action("onboard_info")
def show_nooks_info(ack, body, logger):
    ack()
    user_id = body["user"]["id"]

    app.client.chat_postMessage(
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
                    "text": "*Sounds fun! How can I join a nook?*\nI will be back everyday with a list of nooks suggested by your coworkers, just click interested whenever you would want to join in on the conversation. Using some secret optimizations:test_tube: that aim to aid socialization, I'll allocate one nook to you the next day. \nPro Tip: Click interested on more nooks for more optimal results!",
                },
            },
            {
                "type": "image",
                "title": {"type": "plain_text", "text": "image1", "emoji": True},
                "image_url": "https://api.slack.com/img/blocks/bkb_template_images/onboardingComplex.jpg",
                "alt_text": "image1",
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*How can I create a nook?*\nAfter we've completed your onboarding, just head over to the NooksBot Home page to get started. \nP.S, I also have some sample topics here for :sparkles:inspiration:sparkles:",
                },
            },
            {
                "type": "image",
                "title": {"type": "plain_text", "text": "image1", "emoji": True},
                "image_url": "https://api.slack.com/img/blocks/bkb_template_images/onboardingComplex.jpg",
                "alt_text": "image1",
            },
            {"type": "divider"},
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


@app.command("/onboard")
def onboarding_modal(ack, body, logger):
    ack()
    for member in app.client.users_list()["members"]:
        app.client.chat_postMessage(
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
from flask import Flask, request

flask_app = Flask(__name__)
handler = SocketModeHandler(app, SLACK_APP_TOKEN)
handler.connect()


def remove_past_stories():
    active_stories = list(db.stories.find({"status": "active"}))
    # archive all channels of the past day
    for active_story in active_stories:
        try:
            chat_history = app.client.conversations_history(channel=active_story["channel_id"])["messages"]
            db.stories.update(
                {"_id": active_story["_id"]}, 
                {"$set": {"status": "archived",
                        "chat_history": chat_history}}
                        
            )
            

            app.client.conversations_archive(channel=active_story["channel_id"])

        except Exception as e:
            logging.error(traceback.format_exc())


def create_new_channels(new_stories, allocations):
    # create new channels for the day

    for new_story in new_stories:
        title =  new_story["title"]
        creator = new_story["creator"]
        desc = new_story["description"]
        try:
            logging.info("FRRRRE")
            logging.info(title)
            response = app.client.conversations_create(name=title, is_private=False)
            ep_channel = response["channel"]["id"]
            initial_thoughts_thread = app.client.chat_postMessage(
                link_names=True,
                channel=ep_channel,
                text="Super-excited to hear all of your thoughts :)",
            )
            logging.info("FRRRRE")
            logging.info(allocations[new_story["_id"]])
            
            app.client.conversations_invite(
                channel=ep_channel, users=allocations[new_story["_id"]]
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


def main():
    db.user_swipes.remove()
    if "user_swipes" not in db.list_collection_names():
        db.create_collection("user_swipes")

    # TODO shift to onboarding
    if "member_vectors" not in db.list_collection_names():
        db.create_collection("member_vectors")
        db.member_vectors.create_index("user_id")
        all_members = app.client.users_list()["members"]
        """
        member_vectors = np.random.randint(2, size=(len(all_members), MEMBER_FEATURES))
        db.member_vectors.insert_many(
            [
                {"user_id": member["id"], "member_vector": member_vectors[i].tolist()}
                for i, member in enumerate(all_members)
            ]
        )
        """

        db.create_collection("all_interacted")
        db.create_collection("temporal_interacted")
        counts = {member["id"]: 0 for member in all_members}
        db.all_interacted.insert_many(
            [
                {"user_id": member["id"], "counts": counts.copy()}
                for member in all_members
            ]
        )
        db.temporal_interacted.insert_many(
            [
                {"user_id": member["id"], "counts": counts.copy()}
                for member in all_members
            ]
        )


if __name__ == "__main__":
    main()
    nooks_home = NooksHome(db=db)
    nooks_alloc = NooksAllocation(db=db)
    flask_app.run(debug=True, use_reloader=False)
