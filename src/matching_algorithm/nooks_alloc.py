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
            print(team_id, bnodes)
            g = Graph(blacklist_edges, bnodes, len(bnodes))
            while not kcoloring_res:
                print(num_partitions, kcoloring_res)

                kcoloring_res = kColoring(
                    g, [0] * len(bnodes), num_partitions, 0, len(bnodes)
                )
                if kcoloring_res:
                    break
                num_partitions += 1
        print(kcoloring_res)
        partitions = [set([]) for i in range(num_partitions)]
        for member_idx in range(len(kcoloring_res)):
            partitions[kcoloring_res[member_idx] - 1].add(bnodes[member_idx])
            partitions_alloc[bnodes[member_idx]] = kcoloring_res[member_idx] - 1

        current_part = 0
        for member in oldmembers_list:
            if member["user_id"] in partitions_alloc:
                continue
            partitions_alloc[member["user_id"]] = current_part
            partitions[current_part].add(member["user_id"])
            current_part += 1
            current_part %= num_partitions
        current_part = 0
        for member in newmembers_list:
            if member["user_id"] in partitions_alloc:
                continue
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
            if member["Role"] not in [
                "Old Company Employee(More than 6 months)",
                "Professor",
                "PhD Student",
            ]:
                print(member["Role"])
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

                if len(right_swiped_set) < 2:
                    mems = []
                elif len(right_swiped_set) < 3 and not (nook["allow_two_members"]):
                    mems = []
                else:
                    mems = right_swiped_set

                nooks_allocs[nook["_id"]] = ",".join(list(set(mems)))

            else:
                try:
                    nook_part_id = {}
                    partitioned_nooks_members = [set([]) for i in range(len(partitions))]
                    random.shuffle(right_swiped)
                    right_swiped_set = set(right_swiped)
                    i = 0
                    partitions_has_changed = False
                    for member in set(right_swiped_set):
                        if member not in partitions_alloc:
                            partitions_has_changed = True
                            partitions[i].append(member)
                            partitions_alloc[member] = i
                            i = (i + 1) % len(partitions)
                    if partitions_has_changed:
                        my_date = datetime.date.today()  # if date is 01/01/2018
                        year, week_num, day_of_week = my_date.isocalendar()
                        self.db.temporal_partitions.update_one(
                        {"team_id": team_id, "week_num": week_num, "year": year},
                        {"$set": {
                            "team_id": team_id,
                            "week_num": week_num,
                            "year": year,
                            "partitions_alloc": partitions_alloc,
                            "partitions": [list(p) for p in partitions],
                            }}
                        )

                    for p in range(len(partitions)):
                        for member in partitions[p]:
                            if member in right_swiped_set:
                                partitioned_nooks_members[p].add(member)
                    partitioned_nooks_members.sort(key=len)

                    start_merge_index = 0
                    last_merge_index = len(partitioned_nooks_members) - 1
                    print(partitioned_nooks_members)

                    for i in range(len(partitioned_nooks_members)):
                        if len(partitioned_nooks_members[i]) == 0:
                            start_merge_index = i + 1
                        if len(partitioned_nooks_members[i]) >= MIN_NUM_MEMS:
                            last_merge_index = i - 1
                    i = start_merge_index
                    j = len(partitioned_nooks_members) - 1
                    merged = {i: i for i in range(len(partitions))}
                    merge_idx = len(partitions)
                    while i <= last_merge_index:
                        total_num = len(partitioned_nooks_members[i])
                        merged[i] = merge_idx
                        i += 1
                        while total_num < MIN_NUM_MEMS and i < len(
                        partitioned_nooks_members):
                            total_num += len(partitioned_nooks_members[i])
                            merged[i] = merge_idx
                            i += 1
                        merge_idx += 1

                    nook_mems = [set([]) for _ in range(merge_idx)]
                    for i in range(len(partitions)):
                        nook_mems[merged[i]] = nook_mems[merged[i]].union(
                            partitioned_nooks_members[i]
                        )
                    nook_mems.sort(key=len)
                    n_nook_mems = []
                    for n in nook_mems:
                        if n:
                            n_nook_mems.append(n)
                    
                    if len(n_nook_mems) > 1 and len(n_nook_mems[0])< MIN_NUM_MEMS:
                        n_nook_mems[1] = n_nook_mems[1].union({k for k in n_nook_mems[0]})
                        n_nook_mems[0] = set([])

                    for merged_part_idx in range(len(n_nook_mems)):

                        if n_nook_mems[merged_part_idx]:
                            nook_info = {
                            key: nook[key] for key in nook if not (key == "_id")
                            }
                            nook_info["members"] = ",".join(
                                list(n_nook_mems[merged_part_idx])
                            )
                            nook_part_i = self.db.nooks.insert_one(nook_info)
                            nooks_allocs[nook_part_i.inserted_id] = nook_info["members"]
                            nook_part_id[merged_part_idx] = nook_part_i.inserted_id

                    nooks_allocs[nook["_id"]] = ""

                    self.db.nooks.update_one(
                    {"_id": nook["_id"]}, {"$set": {"status": "duplicated"}}
                    )
                except Exception as e:
                    print(e)

        return nooks_allocs, {}

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
