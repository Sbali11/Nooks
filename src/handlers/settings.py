from utils.constants import *
from installation import *
from utils.ack_methods import *
import logging
import time


class Settings:
    def __init__(self, slack_app, db, nooks_home, nooks_alloc):
        self.slack_app = slack_app
        self.db = db
        self.nooks_home = nooks_home
        self.nooks_alloc = nooks_alloc

    def handle_update_timezone(self,ack, body, client, view, logger):
        input_data = view["state"]["values"]
        team_id = body["team"]["id"]
        time_zone = input_data["timezone_id"]["select_input-action"]["selected_option"][
            "value"
        ]
        success_modal_ack(
            ack,
            body,
            view,
            logger,
            message="Time Zone for the workspace updated to " + time_zone,
            title="Set Time-Zone",
        )
        # TODO create a new name if taken?

        self.db.tokens_2.update(
            {
                "team_id": team_id,
            },
            {
                "$set": {
                    "time_zone": time_zone,
                }
            },
        )
        self.update_home_tab_all(token=get_token(team_id), installed_team=body["team"])

    def handle_update_timezone(self, ack, body, client, view, logger):
        input_data = view["state"]["values"]
        user_id = body["user"]["id"]
        team_id = body["team"]["id"]
        if "past_locations" in input_data:
            past_locations = [
                options["text"]["text"]
                for options in input_data["past_locations"]["location_checkboxes"][
                    "selected_options"
                ]
            ]
        else:
            past_locations = []
        if "new_location" in input_data:
            if input_data["new_location"]["plain_text_input-action"]["value"]:
                new_locations = input_data["new_location"]["plain_text_input-action"][
                    "value"
                ].split(",")
            else:
                new_locations = []
        else:
            new_locations = []
        success_modal_ack(
            ack,
            body,
            view,
            logger,
            message="Location options updated! ",
            title="Edit Location Options",
        )
        # TODO create a new name if taken?

        self.db.tokens_2.update(
            {
                "team_id": team_id,
            },
            {
                "$set": {
                    "locations": past_locations + new_locations,
                }
            },
        )

        self.update_home_tab_all(token=get_token(team_id), installed_team=body["team"])

    def set_timezone_modal(self, ack, body, logger):
        ack()
        common_timezones = set([])

        timezone_options = [
            {
                "value": timezone,
                "text": {"type": "plain_text", "text": timezone},
            }
            for timezone in ALL_TIMEZONES
        ]

        self.slack_app.client.views_open(
            token=get_token(body["team"]["id"]),
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "update_timezone",
                "title": {"type": "plain_text", "text": "Set Time-Zone"},
                "submit": {"type": "plain_text", "text": "Set Time-Zone"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "block_id": "timezone_id",
                        "type": "input",
                        "label": {
                            "type": "plain_text",
                            "text": "Select a timezone for the workspace",
                        },
                        "element": {
                            "type": "static_select",
                            "action_id": "select_input-action",
                            "options": timezone_options,
                        },
                    },
                ],
            },
        )

    def set_locations_modal(self, ack, body, logger):
        ack()
        common_timezones = set([])
        team_row = self.db.tokens_2.find_one({"team_id": body["team"]["id"]})
        current_time_zone = team_row["time_zone"]
        if "locations" not in team_row:
            current_location_options = []

        else:
            current_location_options = [
                {
                    "value": str(i),
                    "text": {"type": "plain_text", "text": location},
                }
                for i, location in enumerate(team_row["locations"])
            ]
        if current_location_options:
            current_location_block = [
                {
                    "type": "input",
                    "block_id": "past_locations",
                    "label": {
                        "type": "plain_text",
                        "text": "Unselect any location you want to delete",
                    },
                    "optional": True,
                    "element": {
                        "type": "checkboxes",
                        "action_id": "location_checkboxes",
                        "initial_options": current_location_options,
                        "options": current_location_options,
                    },
                }
            ]
        else:
            current_location_block = []

        self.slack_app.client.views_open(
            token=get_token(body["team"]["id"]),
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "update_locations",
                "title": {"type": "plain_text", "text": "Edit Location Options"},
                "submit": {"type": "plain_text", "text": "Submit Changes"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": current_location_block
                + [
                    {
                        "block_id": "new_location",
                        "type": "input",
                        "label": {
                            "type": "plain_text",
                            "text": "Add location options for the workspace(to add in multiple locations separate them by commas)",
                        },
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "plain_text_input-action",
                        },
                    },
                ],
            },
        )

    def edit_team_settings(self, ack, body, logger):
        ack()

        self.slack_app.client.views_open(
            token=get_token(body["team"]["id"]),
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "update_timezone",
                "title": {"type": "plain_text", "text": "Edit Team Settings"},
                "submit": {"type": "plain_text", "text": "Set Time-Zone"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "action_id": "set_timezone",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Change Team Timezone",
                                    "emoji": True,
                                },
                                "style": "primary",
                            },
                            {
                                "type": "button",
                                "action_id": "location_choices",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Add a Location Choices",
                                    "emoji": True,
                                },
                                "style": "primary",
                            },
                        ],
                    },
                ],
            },
        )

    def update_channel_first(self, token, installed_team):
        channel_id = (
            self.db.tokens_2.find_one({"team_id": installed_team.get("id")})["installation"]
        )["incoming_webhook_channel_id"]
        for member in self.slack_app.client.conversations_members(
            token=token, channel=channel_id
        )["members"]:

            self.nooks_home.update_home_tab(
                client=self.slack_app.client,
                event={
                    "user": member,
                    "view": {"team_id": installed_team.get("id")},
                },
                token=get_token(installed_team.get("id")),
            )

    def update_home_tab_all(self, token, installed_team):

        self.nooks_alloc._create_members(team_id=installed_team.get("id"))
        try:
            self.update_channel_first(token, installed_team)
        except Exception as e:
            logging.error(e)

        all_members = self.slack_app.client.users_list(token=token)["members"]

        for i in range(len(all_members) // 50 + 1):

            for j in range(i * 50, (i + 1) * 50):
                if j >= len(all_members):
                    continue
                member = all_members[j]
                try:
                    self.nooks_home.update_home_tab(
                        client=self.slack_app.client,
                        event={
                            "user": member["id"],
                            "view": {"team_id": installed_team.get("id")},
                        },
                        token=get_token(installed_team.get("id")),
                    )

                except Exception as e:
                    logging.error(e)
            time.sleep(60)
