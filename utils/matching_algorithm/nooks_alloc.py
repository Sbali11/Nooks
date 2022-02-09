from asyncio.log import logger
from audioop import reverse
import collections
import logging
from multiprocessing import context
import numpy as np
import random
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
        weight_factor = np.zeros(len(self.homophily_factors))
        homophily_factors = sorted(self.homophily_factors)
        member_vector = member["member_vector"]
        for interacted_member in top_int_members:
            if interacted_member not in self.member_dict:
                continue
            interacted_member_vector = self.member_vectors[self.member_dict[interacted_member]]
            for i, homophily_factor in enumerate(homophily_factors):
                weight_factor[i] += (member_vector[i] == interacted_member_vector[i])
        self.member_heterophily_priority[self.member_dict[member["user_id"]]] = (weight_factor+EPSILON)/(np.sum(weight_factor)+EPSILON)

    # TODO change to team specific?
    def _create_members(self):
        all_members = list(self.db.member_vectors.find())
        self.member_vectors = np.array(
            [np.array(member["member_vector"]) for member in all_members]
        )

        self.member_dict = {}
        self.member_ids = {}
        self.members_not_together = np.zeros((len(all_members), len(all_members)))
        for i, member_row in enumerate(all_members):
            member = member_row["user_id"]
            self.member_dict[member] = i
            self.member_ids[i] = member
        for blacklist_row in all_members:
            member_pos = self.member_dict[blacklist_row["user_id"]]
            if "blacklisted_from" in blacklist_row:
                for b_from in blacklist_row["blacklisted_from"]:
                    if b_from not in self.member_dict:
                        continue
                    self.members_not_together[member_pos][self.member_dict[b_from]] = 1
                    self.members_not_together[self.member_dict[b_from]][member_pos] = 1
            if "black_list" in blacklist_row:
                for b in blacklist_row["black_list"]:
                    if b not in self.member_dict:
                        continue
                    self.members_not_together[member_pos][self.member_dict[b]] = 1
                    self.members_not_together[self.member_dict[b]][member_pos] = 1

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
            if not (np.sum(nook_swipes[member])) :
                members_no_swipes.add(self.member_ids[member])
                continue
            swipes = nook_swipes[member]
            selected_nook = -1
            for nook in np.random.permutation(num_nooks):
                if not swipes[nook] or self.members_not_together[nooks_allocs[nook]==1].sum(axis=0)[member]:
                    continue
                selected_nook = nook
                break
            if selected_nook==-1:
                continue


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
                interacted_nook = []
                if member not in member_allocs:
                    continue
                og_nook = member_allocs[member]
                if nooks_mem_cnt[og_nook] <= 2:
                    continue
                elif nooks_mem_cnt[og_nook] == 3 and not nooks[og_nook]["allow_two_members"]:
                    continue

                for nook in range(num_nooks):
                    if not nook_swipes[member][nook]:
                        heterophily_nook.append(0)  # this value will be ignored
                        continue
                    same_nook_members = self.member_vectors[nooks_allocs[nook] == 1]
                    member_diff = np.linalg.norm(
                        self.member_vectors[member] - same_nook_members
                    )
                    priority = self.member_heterophily_priority[nooks_allocs[nook] == 1] + (self.member_heterophily_priority[member].reshape(1, -1))
                    heterophily_nook.append(EPSILON + (priority * member_diff ).sum())
                    interacted_nook.append(((nooks_allocs[nook]) * (self.temporal_interacted[member] > 0)).sum())
                interacted_by = np.array(interacted_nook)          
                heterophily = np.array(heterophily_nook)     
                interacted_by = nooks_mem_int_cnt[:, member]
                wts = ((EPSILON + interacted_by) / nooks_mem_cnt) * (
                    1 + (self.alpha * heterophily)
                )

                sel_wts = wts * nook_swipes[member]
                for nook in range(num_nooks):
                    if self.members_not_together[nooks_allocs[nook]==1].sum(axis=0)[member]:
                        sel_wts[nook] = 0

                total_sel_wts = np.sum(sel_wts)
                if total_sel_wts == 0:
                    continue

                selected_nook = np.argmax(sel_wts / total_sel_wts)

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
            if nooks_mem_cnt[nook_id] <= 3 and not nooks[nook_id]["allow_two_members"]:
                continue
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
            interacted_nook = []
            member_pos = self.member_dict[member]
            for nook in range(num_nooks):
                if member in nooks[nook]["banned"]:
                    heterophily_nook.append(0)  # this value will be ignored
                    continue
                same_nook_members = self.member_vectors[nooks_allocs[nook] == 1]
                member_diff = np.linalg.norm(
                    self.member_vectors[member_pos] - same_nook_members
                )
                priority = self.member_heterophily_priority[nooks_allocs[nook] == 1] + (self.member_heterophily_priority[member_pos].reshape(1, -1))
                heterophily_nook.append(EPSILON + (priority * member_diff ).sum())
                interacted_nook.append(((nooks_allocs[nook]) * (self.temporal_interacted[member_pos] > 0)).sum())
            interacted_by = np.array(interacted_nook)          
            heterophily = np.array(heterophily_nook)           
            wts = ((EPSILON + interacted_by) / nooks_mem_cnt) * (
                1 + (self.alpha * heterophily)
            )
            for nook in range(num_nooks):
                if self.members_not_together[nooks_allocs[nook]==1].sum(axis=0)[member_pos]:
                    wts[nook] = 0
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
