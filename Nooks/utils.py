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

        self.temporal_interacted = np.zeros((self.total_members, self.total_members))

        temporal_interacted = self.db.temporal_interacted.find()
        for interacted in temporal_interacted:
            member = interacted["user_id"]
            self.temporal_interacted[self.member_dict[member]] = interacted["counts"]

        self.all_interacted = np.zeros((self.total_members, self.total_members))
        all_interacted = self.db.all_interacted.find()
        for interacted in all_interacted:
            member = interacted["user_id"]
            self.all_interacted[self.member_dict[member]] = interacted["counts"]

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
            logging.info("TGYUV")
            logging.info(self.temporal_interacted)
            logging.info(member)
            logging.info(member_allocs)
            self.temporal_interacted[member] += nooks_allocs[member_allocs[member]]
            self.all_interacted[member] += nooks_allocs[member_allocs[member]]
            self.db.temporal_interacted.update_one(
                {"user_id": self.member_ids[member]},
                {"$set": {"counts": self.temporal_interacted[member].tolist()}},
                upsert=True,
            )
            self.db.all_interacted.update_one(
                {"user_id": self.member_ids[member]},
                {"$set": {"counts": self.all_interacted[member].tolist()}},
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
            logging.info("UUUNIN")
            logging.info(right_swipe_mems)
            # .tolist()
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

    def update(self, suggested_stories):
        self.suggested_stories = suggested_stories
        logging.info("HERERE")
        logging.info(self.suggested_stories)

    def default_message(self, client, event):
        client.views_publish(
            # Use the user ID associated with the event
            user_id=event["user"],
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
                            {
                                "type": "button",
                                "action_id": "ideas",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Get topic inspirations",
                                    "emoji": True,
                                },
                                "value": "join",
                            }
                        ],

                    },
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
                ],
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
                            "text": "*Welcome home, <@" + event["user"] + "> :house:*",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Create your profile to access nooks! ",
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

    def update_home_tab(self, client, event, cur_pos=0):
        user_id = event["user"]
        member = self.db.member_vectors.find({"user_id": user_id})
        if not member:
            self.initial_message(client, event)
            return

        swipes = self.db.user_swipes.find_one({"user_id": user_id})
        to_insert = False
        if not swipes:
            cur_pos = 0
            to_insert = True
        else:
            cur_pos = swipes["cur_pos"]
        found_pos = cur_pos
        while cur_pos < len(self.suggested_stories):
            cur_display_card = self.suggested_stories[cur_pos]

            if user_id not in cur_display_card["banned"]:
                break
            cur_pos += 1
        if cur_pos >= len(self.suggested_stories):
            self.default_message(client, event)
            return
        if to_insert:
            self.db.user_swipes.insert_one({"user_id": user_id, "cur_pos": cur_pos})
        elif not (cur_pos == found_pos):
            self.db.user_swipes.update_one(
                {"user_id": user_id},
                {
                    "$set": {"cur_pos": cur_pos},
                },
                upsert=True,
            )

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
                            {
                                "type": "button",
                                "action_id": "ideas",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Get topic inspirations",
                                    "emoji": True,
                                },
                                "value": "join",
                            }
                        ],

                    },
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
