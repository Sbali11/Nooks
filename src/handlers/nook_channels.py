from utils.constants import *
from installation import *
from utils.ack_methods import *
import logging
from datetime import datetime
import pytz
import traceback 
from bson.objectid import ObjectId



class NookChannels:
    def __init__(self, slack_app, db, nooks_home, nooks_alloc):
        self.slack_app = slack_app
        self.db = db
        self.nooks_home = nooks_home
        self.nooks_alloc = nooks_alloc

    def join_without_interest(self, ack, body, logger):
        ack()
        user = body["user"]["id"]
        ep_channel = body["actions"][0]["value"]
        self.slack_app.client.conversations_invite(
            token=get_token(body["team"]["id"]), channel=ep_channel, users=user
        )

    def handle_member_joined_channel_events(self, body, logger):
        pass

    def get_create_nook_blocks(self, initial_title, initial_desc=""):
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
                                "text": "Allow nook to be created with only one additional member.",
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

    def update_message(self, ack, body, client, view, logger):
        ack()

        nook_id = view["private_metadata"]
        nook = self.db.nooks.find_one({"_id": ObjectId(nook_id)})
        ep_channel, thread_ts = nook["channel_id"], nook["ts"]
        input_data = view["state"]["values"]
        user_id = body["user"]["id"]
        user = self.slack_app.client.users_profile_get(
            user=user_id, token=get_token(body["team"]["id"])
        )
        initial_thoughts = input_data["initial_thoughts"]["plain_text_input-action"][
            "value"
        ]
        try:
            self.slack_app.client.conversations_invite(
                token=get_token(body["team"]["id"]), channel=ep_channel, users=user_id
            )
            self.slack_app.client.chat_postMessage(
                token=get_token(body["team"]["id"]),
                link_names=True,
                channel=ep_channel,
                thread_ts=thread_ts,
                reply_broadcast=True,
                text=initial_thoughts,
            )
        except Exception as e:
            logging.error(traceback.format_exc())

    def handle_new_nook(self, ack, body, client, view, logger):
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
                    + self.get_create_nook_blocks(initial_title=title, initial_desc=desc),
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
                self.db.tokens_2.find_one({"team_id": body["team"]["id"]})["time_zone"]
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

            self.nooks_home.add_nook(nook=new_nook_info, team_id=body["team"]["id"])
            new_nook_info["status"] = "show"
            for member in self.nooks_alloc.all_members_ids[body["team"]["id"]]:
                self.nooks_home.update_home_tab(
                    client=self.slack_app.client,
                    event={"user": member, "view": {"team_id": body["team"]["id"]}},
                    token=token,
                )

        self.db.nooks.insert_one(new_nook_info)

    def create_default_nook(self, title, desc, channel_name, bot_id, team_id):
        new_nook_info = {
            "team_id": team_id,
            "title": title,
            "creator": bot_id,
            "channel_name": channel_name,
            "description": desc
            + "\n\n(P.S. This is a default nook created by the nook bot)",
            "allow_two_members": True,
            "banned": [],
            "created_on": datetime.utcnow(),
            "swiped_right": [],
        }
        new_nook_info["status"] = "show"
        self.db.nooks.insert_one(new_nook_info)

        token = get_token(team_id)
        self.nooks_home.add_nook(nook=new_nook_info, team_id=team_id)
        for member in self.nooks_alloc.all_members_ids[team_id]:
            self.nooks_home.update_home_tab(
                client=self.slack_app.client,
                event={"user": member, "view": {"team_id": team_id}},
                token=token,
            )

    def create_nook_modal(self, ack, body, logger):
        ack()

        if "value" in body["actions"][0]:
            initial_title = body["actions"][0]["value"]
        else:
            initial_title = ""

        self.slack_app.client.views_open(
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
                "blocks": self.get_create_nook_blocks(initial_title),
            },
        )

    def update_random_nook(self, ack, body, logger):
        ack()

        user_id = body["user"]["id"]
        vals = body["actions"][0]["value"].split("/")
        team_id = body["team"]["id"]
        cur_pos = int(vals[0])
        total_len = int(vals[1])
        self.db.sample_nook_pos.update_one(
            {"user_id": user_id, "team_id": body["team"]["id"]},
            {"$set": {"cur_nook_pos": (cur_pos + 2) % total_len}},
        )

        self.nooks_home.update_home_tab(
            self.slack_app.client,
            {"user": user_id, "view": {"team_id": body["team"]["id"]}},
            token=get_token(team_id),
        )
