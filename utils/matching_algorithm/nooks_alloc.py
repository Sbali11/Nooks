from asyncio.log import logger
from audioop import reverse
import collections
from gc import collect
import logging
from multiprocessing import context
import numpy as np
import random
from utils.constants import *


class NooksAllocation:
    def _create_interactions_np(self, team_id, interactions):
        if team_id not in self.total_members:
            self.total_members[team_id] = 0
        interaction_np = np.zeros((self.total_members[team_id], self.total_members[team_id]))
        for interaction_row in interactions:
            member_1 = interaction_row["user1_id"]
            member_2 = interaction_row["user2_id"]
            if member_1 not in self.member_dict or member_2 not in self.member_dict:
                continue

            interaction_np[self.member_dict[member_1]][
                self.member_dict[member_2]
            ] = interaction_row["count"]
        return interaction_np
    
    def get_member_vector(self, member_info):
        member_vector = [0] * (len(self.homophily_factors))
        for i, homophily_factor in enumerate(self.homophily_factors):
            
            if homophily_factor == "Location":
                if ("Location" not in member_info) or (member_info[homophily_factor] not in self.locations[member_info["team_id"]]):
                    member_vector[i] = len(self.locations[member_info["team_id"]])-1
                else:
                    
                    member_vector[i] = self.locations[member_info["team_id"]][member_info[homophily_factor]]
            else:
                member_vector[i] = HOMOPHILY_FACTORS[homophily_factor][
                    member_info[homophily_factor]
                ]

        return member_vector
    
    def __init__(self, db, alpha=2):
        self.db = db
        
        self.num_iters = 20
        self.alpha = alpha
        sorted_homophily_factors =  sorted(list(HOMOPHILY_FACTORS.keys()) + ["Location"])
        self.homophily_factors = HOMOPHILY_FACTORS.copy()
        self.homophily_factors["Location"] = None # this depends on different teams
        self.homophily_factors_index = {
            sorted_homophily_factors[i]: i
            for i in range(len(sorted_homophily_factors))
        }
        print(self.homophily_factors_index)
        self.member_vectors = {}
        self.member_dict = {}
        self.member_ids = {}
        self.members_not_together = {}
        self.total_members = {}
        self.member_heterophily_priority = {}
        self.temporal_interacted = {}
        self.all_interacted = {}
        self.locations = collections.defaultdict(dict)
        for team_row in list(self.db.tokens_2.find()):
            if "locations" in team_row:
                team_locations = team_row["locations"]
            else:
                team_locations = []
            team_locations.append("Other")
            
            for i, location in enumerate(team_locations):
                self.locations[team_row["team_id"]][location] = i
            
            self._create_members(team_row["team_id"])
        #print(self.locations)
    def _set_homophily_priority(self, team_id, member):
        top_int_members = member["top_members"]
        weight_factor = np.zeros(len(self.homophily_factors))
        homophily_factors = sorted(self.homophily_factors)
        member_vector = self.get_member_vector(member)
        for interacted_member in top_int_members:
            if interacted_member not in self.member_dict:
                continue
            interacted_member_vector = self.member_vectors[self.member_dict[team_id][interacted_member]]
            for i, homophily_factor in enumerate(homophily_factors):
                weight_factor[i] += (member_vector[i] == interacted_member_vector[i])
        self.member_heterophily_priority[team_id][self.member_dict[team_id][member["user_id"]]] = (weight_factor+EPSILON)/(np.sum(weight_factor+EPSILON))
        #print(self.member_heterophily_priority)
    # TODO change to team specific?
    def _create_members(self, team_id):


        #np.zeros((len(all_members), len(all_members)))
        all_members = list(self.db.member_vectors.find({"team_id": team_id}))
    
        self.member_vectors[team_id] = np.array(
            [
                np.array(self.get_member_vector(member)) for member in all_members]
            )

        self.members_not_together[team_id] = np.zeros((len(all_members), len(all_members)))

        self.member_dict[team_id] = {}
        self.member_ids[team_id] = {}
        
        for i, member_row in enumerate(all_members):
            member = member_row["user_id"]
            self.member_dict[team_id][member] = i
            self.member_ids[team_id][i] = member

        for blacklist_row in all_members:
            member_pos = self.member_dict[team_id][blacklist_row["user_id"]]
            if "blacklisted_from" in blacklist_row:
                for b_from in blacklist_row["blacklisted_from"]:
                    if b_from not in self.member_dict[team_id]:
                        continue
                    self.members_not_together[team_id][member_pos][self.member_dict[b_from]] = 1
                    self.members_not_together[team_id][self.member_dict[b_from]][member_pos] = 1
            if "black_list" in blacklist_row:
                for b in blacklist_row["black_list"]:
                    if b not in self.member_dict[team_id]:
                        continue
                    self.members_not_together[team_id][member_pos][self.member_dict[team_id][b]] = 1
                    self.members_not_together[team_id][self.member_dict[team_id][b]][member_pos] = 1

        self.total_members[team_id] = len(self.member_vectors[team_id])
        self.member_heterophily_priority[team_id] = np.zeros((self.total_members[team_id], len(self.homophily_factors)))
        for member_row in all_members:
            self._set_homophily_priority(team_id, member_row)
        
        self.temporal_interacted[team_id]= self._create_interactions_np(team_id, 
            self.db.temporal_interacted.find({"team_id": team_id})
        )
        self.all_interacted[team_id] = self._create_interactions_np(team_id, 
            self.db.all_interacted.find({"team_id": team_id})
        )

    def update_interactions(self):
        for team_row in list(self.db.tokens_2.find()):
            team_id = team_row["team_id"]
            self.temporal_interacted[team_id] = self._create_interactions_np(
                team_id,
            self.db.temporal_interacted.find()
            )
            self.all_interacted[team_id] = self._create_interactions_np(
                team_id,
                self.db.all_interacted.find()
            )

    """
        resets the interactions (for eg at the end of every week)
    """

    def reset(self):
        self.db.temporal_interacted.remove()
        #self.db.create_collection("temporal_interacted")

    def create_nook_allocs(self, nooks, team_id):
        self._create_members(team_id)
        team_wise_nooks = collections.defaultdict(list)
        member_allocs = {}
        nooks_creators = {}
        creators = {}
        members_no_swipes = {}
        nooks_mem_cnt = {}
        nooks_mem_int_cnt = {}
        nook_swipes = {}
        allocations = {}
        suggested_allocs = {}
        nooks_allocs = {}
        for nook in nooks:
            team_wise_nooks[nook["team_id"]].append(nook)

        num_nooks = len(nooks)
        nooks_allocs[team_id] = np.zeros((num_nooks, self.total_members[team_id]))
        member_allocs[team_id] = {}
        nooks_creators[team_id] = {}
        creators[team_id] = set([])
        members_no_swipes[team_id] = set([])
        nooks_mem_cnt[team_id] = np.ones((num_nooks))
        nooks_mem_int_cnt[team_id] = np.zeros((num_nooks, self.total_members[team_id]))
        nook_swipes[team_id] = np.zeros((self.total_members[team_id], num_nooks))
        # allocates the creator to their respective nooks
        for i, nook in enumerate(team_wise_nooks[team_id]):
            creator_key = self.member_dict[team_id][nook["creator"]]
            nooks_allocs[team_id][i][creator_key] = 1
            member_allocs[team_id][creator_key] = i
            nooks_creators[team_id][i] = creator_key
            if "swiped_right" not in nook:
                continue
            for member in nook["swiped_right"]:
                nook_swipes[team_id][self.member_dict[team_id][member]][i] = 1
            creators[team_id].add(creator_key)
            nook_swipes[team_id][creator_key][i] = 1
        nook_swipe_nums = nook_swipes[team_id].sum(axis=0)
        right_swiped_nums = [(nook_swipe_nums[i], i) for i in range(len(nook_swipe_nums))]
        right_swiped_nums.sort(reverse=True)
        # iteratively add members to nooks
        for member in range(self.total_members[team_id]):
            if not (np.sum(nook_swipes[team_id][member])) :
                members_no_swipes[team_id].add(self.member_ids[team_id][member])
                continue
            swipes = nook_swipes[team_id][member]
            selected_nook = -1
            for _, nook in right_swiped_nums:
                if not swipes[nook] or (self.members_not_together[team_id][nooks_allocs[team_id][nook]==1]).sum(axis=0)[member]:
                    continue
                selected_nook = nook
                break
            
            if selected_nook==-1:
                continue
            nooks_allocs[team_id][selected_nook][member] = 1
            member_allocs[team_id][member] = selected_nook
            nooks_mem_cnt[team_id][selected_nook] += 1
            nooks_mem_int_cnt[team_id] += self.temporal_interacted[team_id][member] >= 1
        for i in range(self.num_iters):
            all_members_permute = np.random.permutation(self.total_members[team_id])
            for member in all_members_permute:
                if not (np.sum(nook_swipes[team_id][member])):
                    continue
                swipes = nook_swipes[team_id][member]
                heterophily_nook = []
                interacted_nook = []
                if member not in member_allocs[team_id]:
                    continue
                og_nook = member_allocs[team_id][member]
                if nooks_mem_cnt[team_id][og_nook] <= 2:
                    continue
                elif nooks_mem_cnt[team_id][og_nook] == 3 and not team_wise_nooks[team_id][og_nook]["allow_two_members"]:
                    continue
                for nook in range(num_nooks):
                    if not nook_swipes[team_id][member][nook]:
                        heterophily_nook.append(0)  # this value will be ignored
                        continue
                    same_nook_members = self.member_vectors[team_id][nooks_allocs[team_id][nook] == 1]
                    member_diff = (np.abs(self.member_vectors[team_id][member] - same_nook_members) > 0)
                    priority = self.member_heterophily_priority[team_id][nooks_allocs[team_id][nook] == 1] + (self.member_heterophily_priority[team_id][member].reshape(1, -1))
                    heterophily_nook.append(EPSILON + (priority * member_diff ).sum())
                    interacted_nook.append(((nooks_allocs[team_id][nook]) * (self.temporal_interacted[team_id][member] > 0)).sum())
                interacted_by = np.array(interacted_nook)          
                heterophily = np.array(heterophily_nook)     
                interacted_by = nooks_mem_int_cnt[team_id][:, member]
                wts = ((EPSILON + interacted_by) / nooks_mem_cnt[team_id]) * (
                    1 + (self.alpha * heterophily)
                )

                sel_wts = wts * nook_swipes[team_id][member]
                for nook in range(num_nooks):
                    if self.members_not_together[team_id][nooks_allocs[team_id][nook]==1].sum(axis=0)[member]:
                        sel_wts[nook] = 0
                total_sel_wts = np.sum(sel_wts)
                if total_sel_wts == 0:
                    continue
                selected_nook = np.argmax(sel_wts / total_sel_wts)
                if selected_nook == og_nook:
                    continue
                nooks_allocs[team_id][selected_nook][member] = 1
                nooks_allocs[team_id][og_nook][member] = 0
                if not nooks_creators[team_id][selected_nook] == member:
                    nooks_mem_cnt[team_id][selected_nook] += 1
                if not nooks_creators[team_id][og_nook] == member:
                    nooks_mem_cnt[team_id][og_nook] -= 1
                member_allocs[team_id][member] = selected_nook
                nooks_mem_int_cnt[team_id][selected_nook] += (
                    self.temporal_interacted[team_id][member] >= 1
                )
                nooks_mem_int_cnt[team_id][og_nook] -= self.temporal_interacted[team_id][member] >= 1

        for nook_id in range(len(nooks_allocs[team_id])):
            allocated_mems = nooks_allocs[team_id][nook_id].nonzero()[0].tolist()
            allocated_mems = list(
                set(
                [self.member_ids[team_id][member] for member in allocated_mems]
                + [self.member_ids[team_id][nooks_creators[team_id][nook_id]]]
                )
            )        
            if len(allocated_mems) < 3 and not nooks[nook_id]["allow_two_members"]:
                allocations[team_wise_nooks[team_id][nook_id]["_id"]] = ""
                continue
            allocations[team_wise_nooks[team_id][nook_id]["_id"]] = ",".join(allocated_mems)
            self.db.nooks.update_one(
                {"_id": team_wise_nooks[team_id][nook_id]["_id"]},
                {"$set": {"members": allocated_mems}},
            )
            # self._update_interacted(member_allocs, nooks_allocs)
            suggested_allocs.update(self._create_alloc_suggestions(
            team_id, team_wise_nooks[team_id], members_no_swipes[team_id], nooks_allocs[team_id], nooks_mem_cnt[team_id]
            ))
        return allocations, suggested_allocs

    def _create_alloc_suggestions(
        self, team_id, nooks, members_no_swipes, nooks_allocs, nooks_mem_cnt
    ):
        num_nooks = len(nooks)

        suggested_allocs_list = collections.defaultdict(list)
        suggested_allocs = {}
        for member in members_no_swipes:
            heterophily_nook = []
            interacted_nook = []
            member_pos = self.member_dict[team_id][member]
            for nook in range(num_nooks):
                if member in nooks[nook]["banned"]:
                    heterophily_nook.append(0)  # this value will be ignored
                    continue
                same_nook_members = self.member_vectors[team_id][nooks_allocs[nook] == 1]
                member_diff = (np.abs(self.member_vectors[team_id][member] - same_nook_members) > 0)
                priority = self.member_heterophily_priority[team_id][nooks_allocs[nook] == 1] + (self.member_heterophily_priority[team_id][member_pos].reshape(1, -1))
                heterophily_nook.append(EPSILON + (priority * member_diff ).sum())
                interacted_nook.append(((nooks_allocs[nook]) * (self.temporal_interacted[team_id][member_pos] > 0)).sum())
            interacted_by = np.array(interacted_nook)          
            heterophily = np.array(heterophily_nook)           
            wts = ((EPSILON + interacted_by) / nooks_mem_cnt) * (
                1 + (self.alpha * heterophily)
            )
            for nook in range(num_nooks):
                if self.members_not_together[team_id][nooks_allocs[nook]==1].sum(axis=0)[member_pos]:
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
