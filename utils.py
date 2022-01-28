import collections
import logging
import numpy as np
import random
from constants import *

EPSILON = 0.001

MEMBER_FEATURES = 2


def get_member_vector(member_info):
    return np.zeros((MEMBER_FEATURES)).tolist()


def random_priority(creator, user, title, desc, to):
    p = random.randint(0, 2)
    return p


class NooksAllocation:
    def _create_interactions_np(self, interactions):

        interaction_np = np.zeros((self.total_members, self.total_members))

        for interaction_row in interactions:
            logging.info(interaction_row)
            member_1 = interaction_row["user1_id"]
            member_2 = interaction_row["user2_id"]
            if member_1 not in self.member_dict or member_2 not in self.member_dict:
                continue

            interaction_np[self.member_dict[member_1]][
                self.member_dict[member_2]
            ] = interaction_row["count"]
        return interaction_np

    def __init__(self, db, alpha=2):
        self.db = db
        self._create_members()
        self.num_iters = 20
        self.alpha = alpha

    def _create_members(self):
        all_members = list(self.db.member_vectors.find())
        self.member_vectors = np.array(
            [np.array(member["member_vector"]) for member in all_members]
        )

        self.member_dict = {}
        self.member_ids = {}
        for i, member_row in enumerate(all_members):
            member = member_row["user_id"]
            self.member_dict[member] = i
            self.member_ids[i] = member

        self.total_members = len(self.member_vectors)
        self.temporal_interacted = self._create_interactions_np(
            self.db.temporal_interacted.find()
        )
        self.all_interacted = self._create_interactions_np(
            self.db.all_interacted.find()
        )

    def update_interactions(self):
        self.temporal_interacted = self._create_interactions_np(
            self.db.temporal_interacted.find()
        )
        self.all_interacted = self._create_interactions_np(
            self.db.all_interacted.find()
        )

    """
        resets the interactions (for eg at the end of every week)
    """

    def reset(self):
        self.db.temporal_interacted.remove()
        self.db.create_collection("temporal_interacted")

    # TODO see if running median is needed; space & time
    def create_nook_allocs(self, nooks):
        self._create_members()
        num_nooks = len(nooks)
        nooks_allocs = np.zeros((num_nooks, self.total_members))
        member_allocs = {}
        nooks_creators = {}
        creators = set([])
        members_no_swipes = set([])
        nooks_mem_cnt = np.ones((num_nooks))
        nooks_mem_int_cnt = np.zeros((num_nooks, self.total_members))
        nook_swipes = np.zeros((self.total_members, num_nooks))
        # allocates the creator to their respective nooks
        for i, nook in enumerate(nooks):

            creator_key = self.member_dict[nook["creator"]]
            nooks_allocs[i][creator_key] = 1
            member_allocs[creator_key] = i
            nooks_creators[i] = creator_key
            if "swiped_right" not in nook:
                continue
            for member in nook["swiped_right"]:
                nook_swipes[self.member_dict[member]][i] = 1
            creators.add(creator_key)

        # iteratively add members to nooks
        for member in range(self.total_members):
            if member in member_allocs:
                continue
            if not (np.sum(nook_swipes[member])):
                members_no_swipes.add(self.member_ids[member])
                continue
            swipes = nook_swipes[member]
            median_reps = []
            selected_nook = np.random.choice(num_nooks, p=swipes / np.sum(swipes))
            nooks_allocs[selected_nook][member] = 1
            member_allocs[member] = selected_nook
            nooks_mem_cnt[selected_nook] += 1
            nooks_mem_int_cnt += self.temporal_interacted[member] >= 1

        for i in range(self.num_iters):
            all_members_permute = np.random.permutation(self.total_members)

            for member in all_members_permute:
                if not (np.sum(nook_swipes[member])):
                    continue
                swipes = nook_swipes[member]
                median_reps = []
                for nook in range(num_nooks):
                    if not nook_swipes[member][nook]:
                        median_reps.append(1)  # this value will be ignored
                        continue
                    same_nook_members = self.member_vectors[nooks_allocs[nook] == 1]
                    count = np.linalg.norm(
                        self.member_vectors[member] - same_nook_members
                    )
                    median_reps.append(EPSILON + len(count[count > 5]))
                    # median_reps.append(np.linalg.norm(self.member_vectors[member]-median_rep))

                heterophily = np.array(median_reps)
                interacted_by = nooks_mem_int_cnt[:, member]
                wts = ((EPSILON + interacted_by) / nooks_mem_cnt) * (
                    1 + (self.alpha * heterophily)
                )

                sel_wts = wts * nook_swipes[member]

                total_sel_wts = np.sum(sel_wts)
                selected_nook = np.argmax(sel_wts / total_sel_wts)
                og_nook = member_allocs[member]
                if selected_nook == og_nook:
                    continue

                nooks_allocs[selected_nook][member] = 1
                nooks_allocs[og_nook][member] = 0

                nooks_mem_cnt[selected_nook] += 1
                nooks_mem_cnt[og_nook] -= 1

                member_allocs[member] = selected_nook
                nooks_mem_int_cnt[selected_nook] += (
                    self.temporal_interacted[member] >= 1
                )
                nooks_mem_int_cnt[og_nook] -= self.temporal_interacted[member] >= 1
        allocations = {}
        for nook_id in range(len(nooks_allocs)):
            allocated_mems = nooks_allocs[nook_id].nonzero()[0].tolist()
            allocated_mems = list(
                set(
                    [self.member_ids[member] for member in allocated_mems]
                    + [self.member_ids[nooks_creators[nook_id]]]
                )
            )
            allocations[nooks[nook_id]["_id"]] = ",".join(allocated_mems)
            self.db.nooks.update_one(
                {"_id": nooks[nook_id]["_id"]},
                {"$set": {"members": allocated_mems}},
            )
        # self._update_interacted(member_allocs, nooks_allocs)
        suggested_allocs = self._create_alloc_suggestions(
            nooks, members_no_swipes, nooks_allocs, nooks_mem_cnt
        )
        return allocations, suggested_allocs

    def _create_alloc_suggestions(
        self, nooks, members_no_swipes, nooks_allocs, nooks_mem_cnt
    ):
        num_nooks = len(nooks)

        suggested_allocs_list = collections.defaultdict(list)
        suggested_allocs = {}
        for member in members_no_swipes:
            wts = []
            for nook in range(num_nooks):
                if member in nooks[nook]["banned"]:
                    wts.append(0)
                    continue
                same_nook_members = self.member_vectors[nooks_allocs[nook] == 1]
                diff = np.linalg.norm(
                    self.member_vectors[self.member_dict[member]] - same_nook_members
                )
                # TODO confirm this
                heterophily = EPSILON + len(diff[diff > 5])
                interacted_by = (nooks_allocs[nook]) * (
                    self.temporal_interacted[self.member_dict[member]] > 0
                )
                wts.append(
                    ((EPSILON + np.sum(interacted_by)) / len(same_nook_members))
                    * (1 + (self.alpha * heterophily))
                )
            # total_wts = np.sum(wts)
            wts = np.array(wts)
            # banned from all nooks
            if not np.sum(wts):
                continue
            selected_nook = np.argmax(
                np.array(wts)
            )  # should this be random with probability related to the value instead of argmax?
            # allocations
            suggested_allocs_list[nooks[selected_nook]["_id"]].append(member)
        for nook_id in suggested_allocs_list:
            suggested_allocs[nook_id] = ",".join(suggested_allocs_list[nook_id])
            # self.member_vectors[member]] = selected_nook
        return suggested_allocs_list


class NooksHome:
    def __init__(self, db):
        self.db = db
        self.suggested_stories = collections.defaultdict(dict)
        self.sample_nooks = db.sample_nooks.distinct("title")
        self.all_members = list(self.db.member_vectors.find())

    def update_sample_nooks(self):
        self.sample_nooks = self.db.sample_nooks.distinct("title")
        random.shuffle(self.sample_nooks)

    def update(self, suggested_stories):
        self.suggested_stories = suggested_stories

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
                    )["user"]["name"]
                    if not (member == NOOKS_BOT_NAME):
                        interacted_with.append(
                            (
                                interaction_row["count"],
                                member,
                                interaction_row["user2_id"],
                            )
                        )
            interacted_with.sort(reverse=True)
            interacted_with = interacted_with[:MAX_NUM_CONNECTIONS]
            if interacted_with:
                interaction_block_items = [
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
                ] + [
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
                            "style": "primary",
                            "value": member_user_id,
                        },
                    }
                    for _, member, member_user_id in interacted_with
                ]
        return interaction_block_items

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
        current_sample = self.sample_nooks[cur_nook_pos]
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Hey there"
                    + "<@"
                    + event["user"]
                    + "> :wave: I'm *NooksBot*. \n\n Nooks allow you to 'bump' into other workplace members over shared interests!",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text":  "> Have something you want to talk about with your co-workers? Give me a topic and I'll do the rest :) P.S all nooks are created anonymously, so you don't need to worry about starting conversations",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Create a nook",
                        "emoji": True,
                    },
                    "style": "primary",
                    "value": "join",
                    "action_id": "create_story",
                },
            },
            {"type": "divider"},
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "* Here are some samples to get your started!*",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ">" + current_sample,
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Suggest Another Topic!",
                        "emoji": True,
                    },
                    "value": str(cur_nook_pos) + "/" + str(len(self.sample_nooks)),
                    "action_id": "new_sample_nook",
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
                                "type": "plain_text",
                                "text": "You've exhausted your list for the day. I'll be back tomorrow :)  ",
                                "emoji": True,
                            },
                        },
                        {"type": "divider"},
                        {"type": "divider"},
                    ]
                    + interaction_block_items
                ),
            },
        )

    def initial_message(self, client, event, token):
        client.views_publish(
            token=token,
            # Use the user ID associated with the event
            user_id=event["user"],
            # Home tabs must be enabled in your app configuration
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Hey there"
                            + "<@"
                            + event["user"]
                            + "> :wave: I'm *NooksBot*.\n_Remember the good old days where you could bump into people and start conversations?_\n Nooks allow you to do exactly that but over slack! Your workplace admin invited me here and I'm ready to help you interact with your coworkers in a exciting new ways:partying_face:\n",
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
                            {
                                "type": "button",
                                "action_id": "learn_more",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Learn More",
                                    "emoji": True,
                                },
                            },
                        ],
                    },
                ],
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

        suggested_stories_current = self.suggested_stories[team_id]
        while cur_pos < len(suggested_stories_current):
            cur_display_card = suggested_stories_current[cur_pos]
            if user_id not in cur_display_card["banned"]:
                break
            cur_pos += 1
        if cur_pos >= len(suggested_stories_current):
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

        if not suggested_stories_current or cur_pos >= len(suggested_stories_current):
            self.default_message(client, event, token=token)
            return

        interaction_block_items = self.get_interaction_blocks(
            client, user_id, team_id=event["view"]["team_id"], token=token
        )
        before_cards_block_items = self.get_blocks_before_cards(
            client, event, token=token
        )
        client.views_publish(
            token=token,
            # Use the user ID associated with the event
            user_id=user_id,
            # Home tabs must be enabled in your app configuration
            view={
                "type": "home",
                "blocks": before_cards_block_items
                + [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":calendar: |   *TODAY'S NOOK CARDS*  | :calendar: ",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*"
                            + cur_display_card["title"]
                            + "*"
                            + "\n"
                            + cur_display_card["description"],
                        },
                        "accessory": {
                            "type": "image",
                            "image_url": "https://api.slack.com/img/blocks/bkb_template_images/approvalsNewDevice.png",
                            "alt_text": "computer thumbnail",
                        },
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Not for me :x:",
                                    "emoji": True,
                                },
                                "action_id": "story_not_interested",
                                "value": str(cur_pos),
                            },
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Interested :heavy_check_mark:",
                                    "emoji": True,
                                },
                                "action_id": "story_interested",
                                "value": str(cur_pos),
                            },
                        ],
                    },
                    {"type": "divider"},
                    {"type": "divider"},
                ]
                + interaction_block_items,
            },
        )
