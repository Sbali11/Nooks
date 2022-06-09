from audioop import reverse
import collections
import logging
from multiprocessing import context
import time
import numpy as np
import random
from utils.constants import *


class NooksHome:
    def __init__(self, db):
        self.db = db

        self.suggested_nooks = collections.defaultdict(list)

        suggested_nooks = list(db.nooks.find({"status": "show"}).sort("created_on"))
        for suggested_nook in suggested_nooks:
            self.suggested_nooks[suggested_nook["team_id"]].append(suggested_nook)
        print(self.suggested_nooks)

        self.sample_nooks = db.sample_nooks.distinct("title")
        self.all_members = list(self.db.member_vectors.find())

    def update_sample_nooks(self):
        self.sample_nooks = self.db.sample_nooks.distinct("title")
        random.shuffle(self.sample_nooks)

    def reset(self, team_id):
        self.suggested_nooks[team_id] = []

    def update(self, suggested_nooks, team_id):
        self.suggested_nooks[team_id] += suggested_nooks

    def add_nook(self, nook, team_id):
        print("ADDED")
        self.suggested_nooks[team_id].append(nook)

    def get_context_block(self, user_id, team_id):
        team_row = self.db.tokens_2.find_one({"team_id": team_id})
        user_id_installer = team_row["user_id"]
        current_time_zone = team_row["time_zone"]
        if "locations" not in team_row:
            current_locations = []
        else:
            current_locations = team_row["locations"]
        set_timezone_block = []
        timezone_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "> The workspace's current time-zone is set as: "
                + current_time_zone,
            },
        }
        if current_locations:
            location_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "> The workspace's current locations are: \n"
                    + "".join(
                        ["> - " + location + "\n" for location in current_locations]
                    ),
                },
            }

        else:
            location_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "> Your workspace doesn't have any locations set yet",
                },
            }

        if user_id_installer == user_id:
            timezone_block["accessory"] = {
                "type": "button",
                "action_id": "set_timezone",
                "text": {
                    "type": "plain_text",
                    "text": "Change Time-Zone",
                    "emoji": True,
                },
            }
            location_block["accessory"] = {
                "type": "button",
                "action_id": "edit_location",
                "text": {
                    "type": "plain_text",
                    "text": "Edit Locations",
                    "emoji": True,
                },
            }
            reach_out_block = []

        else:
            reach_out_block = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Notice something wrong? Reach out to <@"
                        + user_id_installer
                        + "> to change workspace-wide settings!",
                    },
                }
            ]
        return (
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":gear: |   *NOOKS WORKSPACE*  | :gear: ",
                    },
                }
            ]
            + reach_out_block
            + [timezone_block, location_block]
            + [
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "action_id": "initiate_onboarding_modal",
                            "text": {
                                "type": "plain_text",
                                "text": "Onboard Members",
                                "emoji": True,
                            },
                            "style": "primary",
                            "value": "onboard",
                        },
                        {
                            "type": "button",
                            "action_id": "send_feedback",
                            "text": {
                                "type": "plain_text",
                                "text": "Send Feedback",
                                "emoji": True,
                            },
                            "value": "feedback",
                        },
                        {
                            "type": "button",
                            "action_id": "go_to_website",
                            "text": {
                                "type": "plain_text",
                                "text": "Visit Website",
                                "emoji": True,
                            },
                            "value": "website",
                            "url": "https://nooks.vercel.app/",
                        },
                    ],
                },
            ]
        )

    def get_interaction_blocks(self, client, user_id, team_id, token):
        all_connections = self.db.all_interacted.find(
            {"user1_id": user_id, "team_id": team_id}
        )

        interacted_with = []
        interaction_block_items = []

        if all_connections:
            for interaction_row in all_connections:
                interaction_counts = interaction_row["count"]
                if interaction_row["count"] > 0 and not (
                    interaction_row["user2_id"] == user_id
                ):
                    member = client.users_info(
                        token=token, user=interaction_row["user2_id"]
                    )["user"]
                    if member["is_bot"]:
                        continue

                    interacted_with.append(
                        (
                            interaction_row["count"],
                            member["name"],
                            interaction_row["user2_id"],
                        )
                    )
            interacted_with.sort(reverse=True)
            interacted_with = interacted_with[:MAX_NUM_CONNECTIONS]
            if interacted_with:
                interaction_block_items = (
                    [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": ":people_holding_hands: |   *CONNECT BEYOND NOOKS*  | :people_holding_hands: ",
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "You've spoken to these colleagues very often in Nooks!",
                            },
                        },
                    ]
                    + [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "> @" + member,
                            },
                            "accessory": {
                                "type": "button",
                                "action_id": "contact_person",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Send a Message",
                                    "emoji": True,
                                },
                                "value": member_user_id,
                                "style": "primary",
                            },
                        }
                        for _, member, member_user_id in interacted_with
                    ]
                    + [
                        {"type": "divider"},
                        {"type": "divider"},
                    ]
                )
        return interaction_block_items

    def get_create_a_nook_block(self, client, event, token):
        user_id = event["user"]
        sample_nook_pos = self.db.sample_nook_pos.find_one(
            {"user_id": user_id, "team_id": event["view"]["team_id"]}
        )
        if not sample_nook_pos:
            cur_nook_pos = 0
            self.db.sample_nook_pos.insert_one(
                {
                    "user_id": user_id,
                    "cur_nook_pos": cur_nook_pos,
                    "team_id": event["view"]["team_id"],
                }
            )
        else:
            cur_nook_pos = sample_nook_pos["cur_nook_pos"]
        num_samples = len(self.sample_nooks)
        current_sample_1 = self.sample_nooks[cur_nook_pos % num_samples]
        current_sample_2 = self.sample_nooks[(cur_nook_pos + 1) % num_samples]
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":pencil: |   *CREATE A NOOK*  | :pencil: ",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Want to feel more connected to your co-workers? Give me a topic and I'll help you find an audience :)\nP.S. all nooks are created anonymously, so you don't need to worry about starting conversations\n\n",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Create a nook",
                        "emoji": True,
                    },
                    "style": "primary",
                    "action_id": "create_nook",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": " ",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": " ",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n\n\n *Here are some samples to get you started !* ",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Get more samples",
                        "emoji": True,
                    },
                    "value": str(cur_nook_pos) + "/" + str(len(self.sample_nooks)),
                    "action_id": "new_sample_nook",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "> " + current_sample_1,
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Edit & Use",
                        "emoji": True,
                    },
                    "value": current_sample_1,
                    "action_id": "create_nook",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "> " + current_sample_2,
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Edit & Use",
                        "emoji": True,
                    },
                    "value": current_sample_2,
                    "action_id": "create_nook",
                },
            },
            {"type": "divider"},
            {"type": "divider"},
        ]
        return blocks

    def get_blocks_before_cards(self, client, event, token):
        user_id = event["user"]
        sample_nook_pos = self.db.sample_nook_pos.find_one(
            {"user_id": user_id, "team_id": event["view"]["team_id"]}
        )
        if not sample_nook_pos:
            cur_nook_pos = 0
            self.db.sample_nook_pos.insert_one(
                {
                    "user_id": user_id,
                    "cur_nook_pos": cur_nook_pos,
                    "team_id": event["view"]["team_id"],
                }
            )
        else:
            cur_nook_pos = sample_nook_pos["cur_nook_pos"]
        num_samples = len(self.sample_nooks)
        current_sample_1 = self.sample_nooks[cur_nook_pos % num_samples]
        current_sample_2 = self.sample_nooks[(cur_nook_pos + 1) % num_samples]
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "Nooks"}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Hey there "
                    + "<@"
                    + event["user"]
                    + ">! Nooks allow you to 'bump' into other workplace members over shared interests!",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Tell me more",
                        "emoji": True,
                    },
                    "action_id": "tell_me_more",
                },
            },
        ]
        return blocks

    def default_message(self, client, event, token):
        user_id = event["user"]
        interaction_block_items = self.get_interaction_blocks(
            client, user_id, team_id=event["view"]["team_id"], token=token
        )
        before_cards_block_items = self.get_blocks_before_cards(
            client, event, token=token
        )
        context_block_items = self.get_context_block(
            user_id=event["user"], team_id=event["view"]["team_id"]
        )
        create_a_nook_block = self.get_create_a_nook_block(client, event, token=token)

        client.views_publish(
            token=token,
            # Use the user ID associated with the event
            user_id=user_id,
            # Home tabs must be enabled in your app configuration
            view={
                "type": "home",
                "blocks": (
                    before_cards_block_items
                    + [
                        {"type": "divider"},
                        {"type": "divider"},
                    ]
                    + create_a_nook_block
                    + [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": ":calendar: |   *TODAY'S NOOK CARDS *  | :calendar: ",
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "Here are the nooks that we plan to have at 12 PM the next weekday!",
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": ">You've exhausted your list for the day. You'll be matched to your interested nooks at 12PM the next weekday and get a final list of updated cards at 4PM ! ",
                            },
                        },
                        {"type": "divider"},
                        {"type": "divider"},
                    ]
                    + interaction_block_items
                    + context_block_items
                ),
            },
        )

    def initial_message(self, client, event, token):
        context_block_items = self.get_context_block(
            user_id=event["user"], team_id=event["view"]["team_id"]
        )

        client.views_publish(
            token=token,
            # Use the user ID associated with the event
            user_id=event["user"],
            # Home tabs must be enabled in your app configuration
            view={
                "type": "home",
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": "Nooks"}},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Hey there"
                            + "<@"
                            + event["user"]
                            + "> :wave: I'm *NooksBot*.",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Create your profile now to start! ",
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
                            },
                        ],
                    },
                    {
                        "type": "divider",
                    },
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
                            "text": "*Sounds fun! How can I join a nook?*\nI will be back everyday with a list of nooks suggested by your coworkers for the next workday, just click interested whenever you would want to join in on the conversation. ",
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
                            "text": "*Some more details!*\nFor detailed onboarding instructions, you can visit https://nooks.vercel.app/member-onboarding!",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Note: I'm created as a part of a research project and I would be collecting some data as a part of the study(including your responses to the questionnaire), however at no point would your details be disclosed. Participating and completing the signup counts as consent for this data collection(no data is collected otherwise). No conversation data is collected ",
                        },
                    },
                    {
                        "type": "divider",
                    },
                    {
                        "type": "divider",
                    },
                ]
                + context_block_items,
            },
        )

    def update_home_tab(
        self, client, event, cur_pos=0, cur_nooks_pos=0, user_id=None, token=None
    ):
        if not user_id:
            user_id = event["user"]
        member = self.db.member_vectors.find_one(
            {"user_id": user_id, "team_id": event["view"]["team_id"]}
        )
        interaction_block_items = self.get_interaction_blocks(
            client, user_id, team_id=event["view"]["team_id"], token=token
        )
        context_block_items = self.get_context_block(
            user_id=user_id, team_id=event["view"]["team_id"]
        )
        if not member:
            self.initial_message(client, event, token=token)
            return

        swipes = self.db.user_swipes.find_one(
            {"user_id": user_id, "team_id": event["view"]["team_id"]}
        )

        swipes_to_insert = False
        sample_nook_to_insert = False
        if not swipes:
            cur_pos = 0
            swipes_to_insert = True
        else:
            cur_pos = swipes["cur_pos"]
        sample_nook_pos = self.db.sample_nook_pos.find_one(
            {"user_id": user_id, "team_id": event["view"]["team_id"]}
        )

        if not sample_nook_pos:
            cur_nook_pos = 0
            self.db.sample_nook_pos.insert_one(
                {
                    "user_id": user_id,
                    "cur_nook_pos": cur_nook_pos,
                    "team_id": event["view"]["team_id"],
                }
            )
        else:
            cur_nook_pos = sample_nook_pos["cur_nook_pos"]
        cur_sample = self.sample_nooks[cur_nook_pos]
        found_pos = cur_pos
        team_id = event["view"]["team_id"]

        suggested_nooks_current = self.suggested_nooks[team_id]
        while cur_pos < len(suggested_nooks_current):
            cur_display_card = suggested_nooks_current[cur_pos]
            if user_id not in cur_display_card["banned"]:
                break
            cur_pos += 1
        if cur_pos >= len(suggested_nooks_current):
            self.default_message(client, event, token=token)
            return
        if swipes_to_insert:
            self.db.user_swipes.insert_one(
                {
                    "user_id": user_id,
                    "team_id": event["view"]["team_id"],
                    "cur_pos": cur_pos,
                }
            )

        if not suggested_nooks_current or cur_pos >= len(suggested_nooks_current):
            self.default_message(client, event, token=token)
            return

        interaction_block_items = self.get_interaction_blocks(
            client, user_id, team_id=event["view"]["team_id"], token=token
        )
        before_cards_block_items = self.get_blocks_before_cards(
            client, event, token=token
        )
        create_a_nook_block = self.get_create_a_nook_block(client, event, token=token)

        client.views_publish(
            token=token,
            # Use the user ID associated with the event
            user_id=user_id,
            # Home tabs must be enabled in your app configuration
            view={
                "type": "home",
                "blocks": before_cards_block_items
                + [
                    {"type": "divider"},
                    {"type": "divider"},
                ]
                + create_a_nook_block
                + [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":calendar: |   *TODAY'S NOOK CARDS*  | :calendar: ",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Here are the nooks that we plan to have at 12 PM the next weekday! ",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "> *"
                            + cur_display_card["title"]
                            + "*"
                            + "\n"
                            + "> " + cur_display_card["description"],
                        },
                        "accessory": {
                            "type": "image",
                            "image_url": "https://api.slack.com/img/blocks/bkb_template_images/approvalsNewDevice.png",
                            "alt_text": "computer thumbnail",
                        },
                        "actions": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Not for me :x:",
                                    "emoji": True,
                                },
                                "action_id": "nook_not_interested",
                                "value": str(cur_pos),
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Interested :heavy_check_mark:",
                                    "emoji": True,
                                },
                                "action_id": "nook_interested",
                                "value": str(cur_pos),
                            },
                        ],
                    
                    },

                    {"type": "divider"},
                    {"type": "divider"},
                ]
                + interaction_block_items
                + context_block_items,
            },
        )
