from datetime import datetime, timezone
import logging
import atexit
import random
import collections
import traceback
from utils.slack_app_backend.installation import get_token


def remove_past_nooks(slack_app, db, nooks_alloc, team_id):
    active_nooks = list(db.nooks.find({"status": "active", "team_id": team_id}))
    token = get_token(team_id)
    # archive all channels of the past day
    for active_nook in active_nooks:
        try:
            all_members = slack_app.client.conversations_members(
                token=token,
                channel=active_nook["channel_id"],
            )["members"]
            db.nooks.update(
                {"_id": active_nook["_id"]},
                {"$set": {"status": "archived", "members": all_members}},
            )

            for member_1 in all_members:
                for member_2 in all_members:

                    if not db.temporal_interacted.find_one(
                        {
                            "user1_id": member_1,
                            "user2_id": member_2,
                            "team_id": active_nook["team_id"],
                        }
                    ):

                        db.temporal_interacted.insert_one(
                            {
                                "user1_id": member_1,
                                "user2_id": member_2,
                                "team_id": active_nook["team_id"],
                                "count": 0,
                            }
                        )
                    if not db.all_interacted.find_one(
                        {
                            "user1_id": member_1,
                            "user2_id": member_2,
                            "team_id": active_nook["team_id"],
                        }
                    ):

                        db.all_interacted.insert_one(
                            {
                                "user1_id": member_1,
                                "user2_id": member_2,
                                "team_id": active_nook["team_id"],
                                "count": 0,
                            }
                        )

            db.temporal_interacted.update_many(
                {
                    "user1_id": {"$in": all_members},
                    "user2_id": {"$in": all_members},
                    "team_id": active_nook["team_id"],
                },
                {"$inc": {"count": 1}},
            )
            db.all_interacted.update_many(
                {
                    "user1_id": {"$in": all_members},
                    "user2_id": {"$in": all_members},
                    "team_id": active_nook["team_id"],
                },
                {"$inc": {"count": 1}},
            )

            slack_app.client.conversations_archive(
                token=get_token(active_nook["team_id"]),
                channel=active_nook["channel_id"],
            )

        except Exception as e:
            logging.error(traceback.format_exc())
        #nooks_alloc.update_interactions()


def post_reminders(slack_app, db, team_id):
    active_nooks = list(db.nooks.find({"status": "active", "team_id": team_id}))
    token = get_token(team_id)
    # post reminder messages
    for active_nook in active_nooks:
        try:
            nook_allocated_roles = db.allocated_roles_words.find_one(
                {
                    "team_id": active_nook["team_id"],
                    "channel_id": active_nook["channel_id"],
                }
            )

            if nook_allocated_roles:
                slack_app.client.chat_postMessage(
                    token=token,
                    link_names=True,
                    channel=active_nook["channel_id"],
                    blocks=[
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "Only two hours left before this chat is archived! Can you guess any of the member's secret words they were asked to add in their chats"
                            },
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "action_id": "word_said",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "I'm ready to guess!",
                                        "emoji": True,
                                    },
                                    "style": "primary",
                                    "value": active_nook["channel_id"]
                                }
                            ],
                        },
                    ],
                )
            else:
                slack_app.client.chat_postMessage(
                    token=token,
                    link_names=True,
                    channel=active_nook["channel_id"],
                    text="Pssst don't forget to post your final thoughts before this chat is archived in 2 hours!",
                )
        except Exception as e:
            logging.error(traceback.format_exc())

def create_new_channels(
    slack_app, db, new_nooks, allocations, suggested_allocs, team_id
):
    # create new channels for the day
    db.user_swipes.remove({"team_id": team_id})
    if "user_swipes" not in db.list_collection_names():
        db.create_collection("user_swipes")
    
    nooks = list(db.nooks.find({"status": "show", "team_id": team_id}))
    print(nooks, allocations)
    for i, new_nook in enumerate(nooks):
        #new_nook = db.nooks.find_one({"_id": new_nook_id})
        now = datetime.now()  # current date and time
        token = get_token(new_nook["team_id"])
        date = now.strftime("%m-%d-%Y-%H-%M-%S")
        title = new_nook["title"]
        channel_name = new_nook["channel_name"]
        desc = new_nook["description"]

        if (new_nook["_id"] not in allocations or not allocations[new_nook["_id"]]):
            db.nooks.update(
                {"_id": new_nook["_id"]},
                {
                    "$set": {
                        "status": "not_selected",
                    }
                },
            )
            '''
            slack_app.client.chat_postMessage(
                    token=token,
                    link_names=True,
                    channel=new_nook["creator"],
                    blocks=[
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "Hey there! Unfortunately, I wasn't able to create your channel titled \""
                                + title + "\" today because of not finding enough members for the nook."
                                
                            },
                        }
                    ],
                )
                
            '''
            print("not_selected", new_nook)


            continue
        if allocations[new_nook["_id"]]:
            members = allocations[new_nook["_id"]]
        else:
            members = new_nook["members"]
        try:
            channel_name = "nook-" + channel_name.lower() + "-" + date + "-" + str(i)
            token = get_token(new_nook["team_id"])
            response = slack_app.client.conversations_create(
                token=token,
                name=channel_name,
                is_private=True,
            )

            ep_channel = response["channel"]["id"]
            slack_app.client.conversations_setTopic(
                token=token, channel=ep_channel, topic=title
            )

            initial_thoughts_thread = slack_app.client.chat_postMessage(
                token=token,
                link_names=True,
                channel=ep_channel,
                text="Super-excited to hear all of your thoughts on \n *"
                + title
                + "*\n"
                + ">"
                + desc
                + "\n"
                + "Remember this chat will be automatically archived at 12PM tomorrow :clock1: \n P.S type in */get_role* for your task of the day!",
            )
            slack_app.client.pins_add(
                token=token, channel=ep_channel, timestamp=initial_thoughts_thread["ts"]
            )

            slack_app.client.conversations_invite(
                token=token,
                channel=ep_channel,
                users=members,
            )

            db.nooks.update(
                {"_id": new_nook["_id"]},
                {
                    "$set": {
                        "status": "active",
                        "channel_id": ep_channel,
                        "ts": initial_thoughts_thread["ts"],
                    }
                },
            )
            if new_nook["_id"] not in suggested_allocs:
                continue
            for member in suggested_allocs[new_nook["_id"]]:
                slack_app.client.chat_postMessage(
                    token=token,
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
        return new_nooks


def update_nook_suggestions(slack_app, db, team_id):
    # all stories
    suggested_nooks = list(db.nooks.find({"status": "suggested", "team_id": team_id}))
    print(suggested_nooks)
    token = get_token(team_id)
    for suggested_nook in suggested_nooks:
        try:
            # TODO don't need to do this if all are shown
            db.nooks.update(
                {"_id": suggested_nook["_id"]},
                {
                    "$set": {
                        "status": "show",
                    }
                },
            )
        except Exception as e:
            logging.error(traceback.format_exc())
    new_suggested = suggested_nooks
    suggested_nooks = list(db.nooks.find({"status": "show", "team_id": team_id}))
    if suggested_nooks :
        # TODO
        all_users = list(db.member_vectors.find({"team_id": team_id}))
        for user in all_users:
            try:
                slack_app.client.chat_postMessage(
                    token=token,
                    link_names=True,
                    channel=user["user_id"],
                    text="Hello! I've updated your Nook Cards List for today. Head over to the Nooks Home Tab to see the cards for today!",
                )
            except Exception as e:
                logging.error(traceback.format_exc())
    suggested_nooks_per_team = collections.defaultdict(list)
    for nook in suggested_nooks:
        suggested_nooks_per_team[nook["team_id"]].append(nook)
    return new_suggested
