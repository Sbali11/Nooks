from audioop import reverse
import collections
import logging
from multiprocessing import context
import numpy as np
import random
from constants import *
from utils.constants import *


class NooksAllocation:
    def _create_interactions_np(self, interactions):
        interaction_np = np.zeros((self.total_members, self.total_members))
        for interaction_row in interactions:
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
        
        self.num_iters = 20
        self.alpha = alpha
        self.homophily_factors = sorted(HOMOPHILY_FACTORS)
        self.homophily_factors_index = {
            self.homophily_factors[i]: i
            for i in range(len(self.homophily_factors))
        }
        self._create_members()

    def _set_homophily_priority(self, member):
        top_int_members = member["top_members"]
        weight_factor = {factor: 0 for factor in self.homophily_factors}
        homophily_factors = self.homophily_factors

        member_vector = member["member_vector"]
        for interacted_member in top_int_members:
            if interacted_member not in self.member_dict:
                continue
            interacted_member_vector = self.member_vectors[interacted_member]
            for i, homophily_factor in enumerate(homophily_factors):
                if homophily_factor in SAME_HOMOPHILY_FACTORS:
                    weight_factor[homophily_factor] += not (
                        member_vector[i] == interacted_member_vector[i]
                    )
                else:
                    weight_factor[homophily_factor] += abs(
                        member_vector[i] - interacted_member_vector[i]
                    )
        weight_factor_tuples = [
            (weight_factor[homophily_factor], homophily_factor)
            for homophily_factor in homophily_factors
        ]
        weight_factor_tuples.sort(reverse=True)
        member_heterophily_priority = [0] * len(self.homophily_factors)
        for i, weight_tuple in enumerate(weight_factor_tuples):
            _, homophily_factor = weight_tuple
            member_heterophily_priority[self.homophily_factors_index[homophily_factor]] = FIBONACCI[i]
        self.member_heterophily_priority[self.member_dict[member["user_id"]]]= np.array(member_heterophily_priority)

    # TODO change to team specific?
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
        self.member_heterophily_priority = np.zeros((self.total_members, len(self.homophily_factors)))
        for member_row in all_members:
            self._set_homophily_priority(member_row)

        
        self.temporal_interacted = self._create_interactions_np(
            self.db.temporal_interacted.find()
        )
        self.all_interacted = self._create_interactions_np(
            self.db.all_interacted.find()
        )
        self.weight_factors = {}

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
                heterophily_nook = []
                for nook in range(num_nooks):
                    if not nook_swipes[member][nook]:
                        heterophily_nook.append(1)  # this value will be ignored
                        continue
                    same_nook_members = self.member_vectors[nooks_allocs[nook] == 1]
                    member_diff = np.linalg.norm(
                        self.member_vectors[member] - same_nook_members
                    )
                    priority = self.member_heterophily_priority[same_nook_members] + self.member_heterophily_priority[member]
                    heterophily_nook.append(EPSILON + (priority * member_diff ).sum(dim=1))

                heterophily = np.array(heterophily_nook)
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
            heterophily_nook = []
            for nook in range(num_nooks):
                if member in nooks[nook]["banned"]:
                    heterophily_nook.append(0)  # this value will be ignored
                    continue
                same_nook_members = self.member_vectors[nooks_allocs[nook] == 1]
                member_diff = np.linalg.norm(
                    self.member_vectors[member] - same_nook_members
                )
                priority = self.member_heterophily_priority[same_nook_members] + self.member_heterophily_priority[member]
                heterophily_nook.append(EPSILON + (priority * member_diff ).sum(dim=1))
            heterophily = np.array(heterophily_nook)
            interacted_by = (nooks_allocs[nook]) * (
                    self.temporal_interacted[self.member_dict[member]] > 0
                )            
            wts = ((EPSILON + interacted_by) / nooks_mem_cnt) * (
                1 + (self.alpha * heterophily)
            )
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
