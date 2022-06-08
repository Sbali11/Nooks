from asyncio.log import logger
from audioop import reverse
import collections
from gc import collect
import logging
from multiprocessing import context
from re import L
import numpy as np
import random
from utils.constants import *
import datetime
from .k_coloring import Graph, kColoring


class NooksAllocation:
    def __init__(self, db, alpha=2):
        self.db = db
        self.apha = alpha
        self.member_vectors = collections.defaultdict(dict)
        self.partitions = collections.defaultdict(dict)
        self.all_members_ids = collections.defaultdict(set)
        for team_row in list(self.db.tokens_2.find()):
            self._create_members(team_row["team_id"])
            

    def _create_partitions(self, team_id):
        allocated = set([])
        num_members = len(self.member_vectors[team_id]["oldmembers"]) + len(
            self.member_vectors[team_id]["newcomers"]
        )
        num_partitions = num_members // 10 + 1
        self.partitions = {i: {} for i in range(num_partitions)}

        oldmembers_list = list(self.member_vectors[team_id]["oldmembers"])
        random.shuffle(oldmembers_list)

        newmembers_list = list(self.member_vectors[team_id]["newcomers"])
        random.shuffle(newmembers_list)
        all_members = oldmembers_list + newmembers_list
        blacklist_edges = []
        blacklist_nodes = set([])

        for member in all_members:
            if "blacklisted_from" in member:
                for b_from in member["blacklisted_from"]:
                    if b_from not in self.all_members_ids[team_id]:
                        continue
                    blacklist_edges.append((member["user_id"], b_from))
                    blacklist_nodes.add(member["user_id"])
                    blacklist_nodes.add(b_from)

            if "black_list" in member:
                for b in member["black_list"]:
                    if b not in self.all_members_ids[team_id]:
                        continue
                    blacklist_edges.append((member["user_id"], b))
                    blacklist_nodes.add(member["user_id"])
                    blacklist_nodes.add(b)

        bnodes = list(blacklist_nodes)
        random.shuffle(bnodes)
        newmembers = newmembers_list
        random.shuffle(newmembers)
        kcoloring_res = []
        partitions_alloc = {}
        if bnodes:
            g = Graph(blacklist_edges, bnodes, len(bnodes))
            while not kcoloring_res:
                
                kcoloring_res = kColoring(
                    g, [0] * len(bnodes), num_partitions, 0, len(bnodes)
                )
                if kcoloring_res:
                    break
                num_partitions += 1
        partitions = [set([]) for i in range(num_partitions)]
        for member_idx in range(len(kcoloring_res)):
            partitions[kcoloring_res[member_idx]].add(bnodes[member_idx]["user_id"])
            partitions_alloc[bnodes[member_idx]["user_id"]] = kcoloring_res[member_idx]

        current_part = 0
        for member in oldmembers_list:
            if member["user_id"] in partitions_alloc:
                pass
            partitions_alloc[member["user_id"]] = current_part
            partitions[current_part].add(member["user_id"])
            current_part += 1
            current_part %= num_partitions
        current_part = 0
        for member in newmembers_list:
            if member["user_id"] in partitions_alloc:
                pass
            partitions_alloc[member["user_id"]] = current_part
            partitions[current_part].add(member["user_id"])
            current_part += 1
            current_part %= num_partitions

        return partitions, partitions_alloc

    def get_partitions(self, team_id):
        my_date = datetime.date.today()  # if date is 01/01/2018
        year, week_num, day_of_week = my_date.isocalendar()
        res = self.db.temporal_partitions.find_one(
            {"team_id": team_id, "week_num": week_num, "year": year}
        )
        print(res)
        if res:
            partitions, partitions_alloc = (
                res["partitions"],
                res["partitions_alloc"],
            )
        else:
            partitions, partitions_alloc = self._create_partitions(team_id)
            print(partitions)
            print(partitions_alloc)
            self.db.temporal_partitions.insert_one(
                {
                    "team_id": team_id,
                    "week_num": week_num,
                    "year": year,
                    "partitions_alloc": partitions_alloc,
                    "partitions": [list(p) for p in partitions],
                }
            )
        return partitions, partitions_alloc

    # TODO change to team specific?
    def _create_members(self, team_id):
        # np.zeros((len(all_members), len(all_members)))
        
        all_members = list(self.db.member_vectors.find({"team_id": team_id}))
        self.member_vectors[team_id]["newcomers"] = []
        self.member_vectors[team_id]["oldmembers"] = []
        self.all_members_ids[team_id] = set([])
        for member in all_members:
            self.all_members_ids[team_id].add(member["user_id"])
            if member["Role"] == "REU":
                self.member_vectors[team_id]["newcomers"].append(member)
            else:
                self.member_vectors[team_id]["oldmembers"].append(member)

    def create_nook_allocs(self, nooks, team_id):
        nooks_allocs = {}
        self._create_members(team_id)
        partitions, partitions_alloc = self.get_partitions(team_id)
        all_mems_right_swipes = set([])
        suggestions = set([])
        for nook in nooks:
            # member created nooks
            right_swiped_set = set(nook["swiped_right"])
            all_mems_right_swipes = all_mems_right_swipes.union(right_swiped_set)
            right_swiped = list(right_swiped_set)
            if nook["creator"] in self.all_members_ids[team_id]:
                right_swiped.append(nook["creator"])
                right_swiped_set = set(right_swiped)
                
                if len(right_swiped_set) < 2 :
                    mems = []
                elif len(right_swiped_set) < 3 and not(nook["allow_two_members"]):
                    mems = []
                else :
                    mems = right_swiped_set
                
                nooks_allocs[nook["_id"]] = ",".join(list(set(mems)))

            else:
                nook_part_id = {}

                partitioned_nooks_members = [set([]) for i in range(len(partitions))]
                for p in range(len(partitions)):
                    for member in partitions[p]:
                        if member in right_swiped_set:
                            partitioned_nooks_members[p].add(member)
                partitioned_nooks_members.sort(key=len)
                last_merge_index = -1
                start_merge_index = 0

                for i in range(len(partitioned_nooks_members)):
                    if len(partitioned_nooks_members[i]) == 0:
                        start_merge_index = i + 1
                    if len(partitioned_nooks_members[i]) >= MIN_NUM_MEMS:
                        last_merge_index = i - 1
                i = start_merge_index
                j = last_merge_index
                merged = {i: i for i in range(len(partitions))}
                merge_idx = len(partitions)
                while i < j:
                    ci = i
                    cj = j
                    total_num = 0
                    while ci < cj:
                        total_num += len(partitioned_nooks_members[ci]) + len(
                            partitioned_nooks_members[cj]
                        )
                        if total_num >= MIN_NUM_MEMS:
                            for ii in range(i, ci + 1):
                                merged[ii] = merge_idx
                            for jj in range(cj, cj + 1):
                                merged[jj] = merge_idx
                        merge_idx += 1
                        ci += 1
                        cj -= 1
                    i = ci
                    j = cj

                if i == j and total_num < MIN_NUM_MEMS and i < len(partitions) - 1:
                    merged[i] = merge_idx
                    merged[i + 1] = merge_idx
                    merge_idx += 1

                nook_mems = [set([]) for _ in range(merge_idx)]

                for part_idx in merged:
                    nook_mems[merged[part_idx]] = nook_mems[merged[part_idx]].union(
                        partitioned_nooks_members[part_idx]
                    )

                for merged_part_idx in range(len(nook_mems)):

                    if nook_mems[merged_part_idx]:
                        nook_info = {key: nook[key] for key in nook if not(key=="_id")}
                        nook_info["members"] = ",".join(
                            list(nook_mems[merged_part_idx])
                        )
                        nook_part_i = self.db.nooks.insert_one(nook_info)
                        nooks_allocs[nook_part_i.inserted_id] = nook_info["members"]
                        nook_part_id[merged_part_idx] = nook_part_i.inserted_id

                self.db.nooks.update_one(
                    {"_id": nook["_id"]}, {"$set": {"status": "duplicated"}}
                )

                suggestions = self._create_alloc_suggestions(
                    merged,
                    partitions,
                    partitions_alloc,
                    self.all_members_ids[team_id].difference(all_mems_right_swipes),
                    nook_part_id,
                )
        print(nooks_allocs, suggestions)
        return nooks_allocs, suggestions 

    def _create_alloc_suggestions(
        self,
        merged_partitions,
        partitions,
        partitions_alloc,
        no_right_swiped,
        nook_part_id,
    ):
        suggested_allocs_list = collections.defaultdict(list)
        suggested_allocs = {}
        print(merged_partitions, partitions_alloc)
        for member in no_right_swiped:
            if merged_partitions[partitions_alloc[member]] in nook_part_id:

                suggested_allocs_list[
                nook_part_id[merged_partitions[partitions_alloc[member]]]
                ].append(member)

        for nook_id in suggested_allocs_list:
            suggested_allocs[nook_id] = ",".join(suggested_allocs_list[nook_id])
            self.db.nooks.update_one(
                {"_id": nook_id},
                {"$set": {"suggested_to": suggested_allocs[nook_id]}},
            )
        return suggested_allocs_list
