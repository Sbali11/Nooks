import logging
import numpy as np
import random

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
            member_1 = interaction_row["user_id"]
            if member_1 not in self.member_dict:
                continue
            for member_2 in interaction_row["counts"]:
                if member_2 not in self.member_dict:
                    continue
                interaction_np[self.member_dict[member_1]][
                    self.member_dict[member_2]
                ] = interaction_row["counts"][member_2]
        return interaction_np

    def _create_member_interactions_dict(self, interactions_np):

        interactions_dict = {}
        for member in range(self.total_members):
            if member not in self.member_ids:
                continue
            interactions_dict[self.member_ids[member]] = interactions_np[member]
        return interactions_dict

    def __init__(self, db, alpha=2):
        self.db = db
        self.member_vectors = {
            member["user_id"]: np.array(member["member_vector"])
            for member in self.db.member_vectors.find()
        }
        self.member_dict = {}
        self.member_ids = {}
        for i, member in enumerate(self.member_vectors):
            self.member_dict[member] = i
            self.member_ids[i] = member

        self.total_members = len(self.member_vectors)
        self.temporal_interacted = self._create_interactions_np(
            self.db.temporal_interacted.find()
        )
        self.all_interacted = self._create_interactions_np(
            self.db.all_interacted.find()
        )
        self.num_iters = 20
        self.alpha = alpha

    """
        resets the interactions (for eg at the end of every week)
    """

    def reset(self):
        self.db.interacted.remove()
        self.db.create_collection("interacted")

    """
        called to update the interactions, also updates the total interactions during the experiment
    
    """

    def _update_interacted(self, member_allocs, nooks_allocs):
        for member in range(self.total_members):
            if not member in member_allocs:
                continue
            self.temporal_interacted[member] += nooks_allocs[member_allocs[member]]
            self.all_interacted[member] += nooks_allocs[member_allocs[member]]
            self.db.temporal_interacted.update_one(
                {"user_id": self.member_ids[member]},
                {
                    "$set": {
                        "counts": self._create_member_interactions_dict(
                            self.temporal_interacted[member]
                        )
                    }
                },
                upsert=True,
            )
            self.db.all_interacted.update_one(
                {"user_id": self.member_ids[member]},
                {
                    "$set": {
                        "counts": self._create_member_interactions_dict(
                            self.all_interacted[member]
                        )
                    }
                },
                upsert=True,
            )

    # TODO see if running median is needed; space & time
    def create_nook_allocs(self, nooks):
        num_nooks = len(nooks)
        nooks_allocs = np.zeros((num_nooks, self.total_members))
        member_allocs = {}
        creators = set([])
        nooks_mem_cnt = np.ones((num_nooks))
        nooks_mem_int_cnt = np.zeros((num_nooks, self.total_members))
        nook_swipes = np.zeros((self.total_members, num_nooks))
        # allocates the creator to their respective nooks
        for i, nook in enumerate(nooks):
            if nook["creator"] not in self.member_dict:
                continue
            creator_key = self.member_dict[nook["creator"]]
            nooks_allocs[i][creator_key] = 1
            member_allocs[creator_key] = i
            if "swiped_right" not in nook:
                continue
            for member in nook["swiped_right"]:
                nook_swipes[self.member_dict[member]][i] = 1
            creators.add(creator_key)

        # iteratively add members to nooks
        for member in range(self.total_members):
            if member in member_allocs or not (np.sum(nook_swipes[member])):
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
                if member in creators or not (np.sum(nook_swipes[member])):
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
                interacted_by = 1
                # nooks_mem_int_cnt[:, member]
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
            right_swipe_mems = nooks_allocs[nook_id].nonzero()[0].tolist()
            right_swipe_mems_ids = [
                self.member_ids[member] for member in right_swipe_mems
            ]
            allocations[nooks[nook_id]["_id"]] = ",".join(right_swipe_mems_ids)
            self.db.stories.update_one(
                {"_id": nooks[nook_id]["_id"]},
                {"$set": {"members": right_swipe_mems_ids}},
            )
        self._update_interacted(member_allocs, nooks_allocs)
        return allocations


class NooksHome:
    def __init__(self, db):
        self.db = db
        self.suggested_stories = []
        self.sample_nooks = db.sample_nooks.distinct("title")
        

    def update_sample_nooks(self):
        self.sample_nooks = self.db.sample_nooks.distinct("title")
        random.shuffle(self.sample_nooks)

    def update(self, suggested_stories):
        self.suggested_stories = suggested_stories
        logging.info("HERERE")
        logging.info(self.suggested_stories)

    def get_interaction_blocks(self, client, user_id):
        all_connections = self.db.all_interacted.find_one({"user_id": user_id})

        interacted_with = []
        interaction_block_items = []

        if all_connections:
            num_interactions = all_connections["counts"]
            interacted_with = [
                (num_interactions[member], member)
                for member in num_interactions
                if num_interactions[member] > 0
            ]
            interacted_with.sort(reverse=True)
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
                            "text": "Don't let these connections go!",
                        },
                    },
                ] + [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "@"
                            + client.users_profile_get(user=member)["profile"][
                                "real_name"
                            ],
                        },
                        "accessory": {
                            "type": "button",
                            "action_id": "contact_person",
                            "text": {
                                "type": "plain_text",
                                "text": "Connect",
                                "emoji": True,
                            },
                            "style": "primary",
                            "value": member,
                        },
                    }
                    for _, member in interacted_with
                ]
        return interaction_block_items

    def default_message(self, client, event):
        user_id = event["user"]
        interaction_block_items = self.get_interaction_blocks(client, user_id)
        sample_nook_pos = self.db.sample_nook_pos.find_one({"user_id": user_id})
        if not sample_nook_pos:
            cur_nook_pos = 0
            self.db.sample_nook_pos.insert_one({"user_id": user_id, "cur_nook_pos": cur_nook_pos})
        else:
            cur_nook_pos = sample_nook_pos["cur_nook_pos"] 
        current_sample = self.sample_nooks[cur_nook_pos]    
        client.views_publish(
            # Use the user ID associated with the event
            user_id=user_id,
            # Home tabs must be enabled in your app configuration
            view={
                "type": "home",
                "blocks": (
                    [
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "action_id": "create_story",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Create a nook!",
                                        "emoji": True,
                                    },
                                    "style": "primary",
                                    "value": "join",
                                },
                            ],
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Not sure about the topic? Here's a sample nook to inspire you!*",
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": ">"+current_sample,
                            },
                            "accessory": {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Get new!",
                                    "emoji": True,
                                },
                                "value": str(cur_nook_pos) + "/" + str(len(self.sample_nooks)),
                                "action_id": "new_sample_nook",
                            },
                        },
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
                    ]
                    + interaction_block_items
                ),
            },
        )

    def initial_message(self, client, event):
        client.views_publish(
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
                            "text": "*Welcome to Nooks, <@"
                            + event["user"]
                            + "> :house:*",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Create your profile to now to start! ",
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
            },
        )

    def update_home_tab(self, client, event, cur_pos=0, cur_nooks_pos=0):
        user_id = event["user"]
        member = self.db.member_vectors.find_one({"user_id": user_id})
        interaction_block_items = self.get_interaction_blocks(client, user_id)

        if not member:
            self.initial_message(client, event)
            return

        swipes = self.db.user_swipes.find_one({"user_id": user_id})
        
        swipes_to_insert = False
        sample_nook_to_insert = False
        if not swipes:
            cur_pos = 0
            swipes_to_insert = True
        else:
            cur_pos = swipes["cur_pos"]
        sample_nook_pos = self.db.sample_nook_pos.find_one({"user_id": user_id})
        
        if not sample_nook_pos:
            cur_nook_pos = 0
            self.db.sample_nook_pos.insert_one({"user_id": user_id, "cur_nook_pos": cur_nook_pos})
        else:
            cur_nook_pos = sample_nook_pos["cur_nook_pos"] 
        cur_sample = self.sample_nooks[cur_nook_pos]
        found_pos = cur_pos
        while cur_pos < len(self.suggested_stories):
            cur_display_card = self.suggested_stories[cur_pos]
            if user_id not in cur_display_card["banned"]:
                break
            cur_pos += 1
        if cur_pos >= len(self.suggested_stories):
            self.default_message(client, event)
            return
        if swipes_to_insert:
            self.db.user_swipes.insert_one({"user_id": user_id, "cur_pos": cur_pos})
        '''
        elif not (cur_pos == found_pos):
            self.db.user_swipes.update_one(
                {"user_id": user_id},
                {
                    "$set": {"cur_pos": cur_pos},
                },
                upsert=True,
            )
        '''

        if not self.suggested_stories or cur_pos >= len(self.suggested_stories):
            self.default_message(client, event)
            return

        client.views_publish(
            # Use the user ID associated with the event
            user_id=user_id,
            # Home tabs must be enabled in your app configuration
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "action_id": "create_story",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Create a nook!",
                                    "emoji": True,
                                },
                                "style": "primary",
                                "value": "join",
                            },
                        ],
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Not sure about the topic? Here's a sample nook to inspire you!*",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ">"+cur_sample,
                        },
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Get new!",
                                "emoji": True,
                            },
                            "value": str(cur_nook_pos) + "/" + str(len(self.sample_nooks)),
                            "action_id": "new_sample_nook",
                        },
                    },
                    {"type": "divider"},
                    {"type": "divider"},
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
                                    "text": "Pass :x:",
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
                ],
            },
        )
        
