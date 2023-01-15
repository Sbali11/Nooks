from utils.constants import *
from installation import *
from utils.ack_methods import *
import logging

class Onboarding:
    def __init__(self, slack_app, db, nooks_home, nooks_alloc):
        self.slack_app = slack_app
        self.db = db
        self.nooks_home = nooks_home 
        self.nooks_alloc = nooks_alloc

    def show_nooks_info(self, ack, body, logger):
        ack()
        user_id = body["user"]["id"]
        self.slack_app.client.chat_postMessage(
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

    def handle_team_joined(self, client, event, logger):
        if "user" in event:
            self.nooks_home.update_home_tab(
                client,
                {
                    "user": event["user"]["id"],
                    "view": {"team_id": event["user"]["team_id"]},
                },
            )

    def handle_onboard_members(self, ack, body, client, view, logger):
        input_data = view["state"]["values"]
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
                for row in list(self.db.member_vectors.find({"team_id": body["team"]["id"]}))
            }
            for conversation in conversations_ids:

                for member in self.slack_app.client.conversations_members(
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
        print(len(all_members))
        l = len(all_members)

        for member in all_members:

            try:
                self.nooks_home.update_home_tab(
                    client=self.slack_app.client,
                    event={
                        "user": member,
                        "view": {"team_id": body["team"]["id"]},
                    },
                    token=get_token(body["team"]["id"]),
                )
                self.slack_app.client.chat_postMessage(
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
            except Exception as e:
                logging.info(e)


    def handle_unselect_members(self, ack, body, view, logger):
        input_data = view["state"]["values"]

        conversations_all = input_data["members"]["channel_selected"]["selected_options"]
        conversations_ids = [conv["value"] for conv in conversations_all]
        token = get_token(body["team"]["id"])
        all_members = set([])

        for conversation in conversations_ids:
            for member in self.slack_app.client.conversations_members(
                token=token, channel=conversation
            )["members"]:
                user_info = self.slack_app.client.users_info(user=member, token=token)["user"]
                if not user_info["is_bot"]:
                    all_members.add((member, user_info["name"]))

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


    def get_onboard_members_blocks(self, token):

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

    def handle_onboard_request(self, ack, body, logger):
        ack()
        token = get_token(body["team"]["id"])

        self.slack_app.client.views_open(
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


    def get_onboard_channels_blocks(self, token):

        channel_options = [
            {
                "text": {
                    "type": "plain_text",
                    "text": channel["name"],
                },
                "value": channel["id"],
            }
            for channel in self.slack_app.client.users_conversations(
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


    def handle_onboarding(self, ack, body, view, logger):
        input_data = view["state"]["values"]
        onboard_type = input_data["onboard_selected"]["radio_buttons-action"][
            "selected_option"
        ]["value"]
        token = get_token(body["team"]["id"])
        if onboard_type == "onboard_channels":
            blocks = self.get_onboard_channels_blocks(token)
        else:
            blocks = self.get_onboard_members_blocks(token)
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
