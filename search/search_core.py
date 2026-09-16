"""
The search: a code invariant under a group, of maximum size.

THE PROBLEM, REDUCED
--------------------
With n, d, w and a group G of permutations of the n positions fixed:

  1. the words of weight w split into orbits under G;
  2. an orbit is **usable** if its words are pairwise at distance >= d (otherwise the
     code cannot contain all of it);
  3. two usable orbits are **compatible** if every word of one is at distance >= d
     from every word of the other;
  4. the largest G-invariant code is the set of pairwise compatible orbits of maximum
     total weight.

Step 4 is NP-hard in general, but here the graphs are small because the group has
already done the work. A greedy with random restarts plus a local search (strip k
orbits, refill with the best permitted ones) is used: the same kind of heuristic with
which the records in the tables were found, and on a Mac it suffices.
"""
from __future__ import annotations

import random
from itertools import combinations

from math import comb

from codes import fast_check


# ---------------------------------------------------------------------------
# TWO EXACT SIMPLIFICATIONS, not heuristics, that make the computation possible
#
# 1. An orbit is usable if and only if **one of its representatives** is at distance
#    >= d from all the other words of the orbit. There is no need to check every
#    are the same as those involving a: if a' = g(a) then dist(g(a), b) =
#    pair: the group acts transitively on the orbit, so the pairs involving a'
#    coinvolgono a, riordinate.
#
# 2. For the same reason, two orbits are compatible if and only if **one
#    representative of the first** is at distance >= d from every word of the second.
#
# Together they save a factor equal to the orbit size -- from tens to hundreds. The
# rest is numpy: a single XOR between the representative and the whole vector of
# words, and `bitwise_count` for the weights.


def _orbit_table(n: int, w: int, group):
    """Every word of weight w, the orbit of each, and a representative."""
    import numpy as np
    words = np.fromiter((sum(1 << i for i in c)
                          for c in combinations(range(n), w)),
                         dtype=np.uint64, count=comb(n, w))
    order = {int(p): k for k, p in enumerate(words)}
    orbit_of = np.full(len(words), -1, dtype=np.int64)
    representatives: list[int] = []
    members: list[list[int]] = []
    for k, p in enumerate(words):
        if orbit_of[k] >= 0:
            continue
        o = len(representatives)
        support = [i for i in range(n) if int(p) >> i & 1]
        orbit_group = set()
        for perm in group:
            f = 0
            for i in support:
                f |= 1 << perm[i]
            orbit_group.add(f)
        indices = [order[x] for x in orbit_group]
        orbit_of[indices] = o
        representatives.append(int(p))
        members.append(sorted(indices))
    return words, orbit_of, representatives, members


def orbits_and_compatibility(n: int, d: int, w: int, group):
    """The usable orbits, their weights and the compatibility graph."""
    import numpy as np
    words, orbit_of, rapp, members = _orbit_table(n, w, group)
    # 1. usability: the representative against its orbit-mates
    good_list = []
    for o, r in enumerate(rapp):
        idx = np.array(members[o], dtype=np.int64)
        dist = np.bitwise_count(np.bitwise_xor(words[idx], np.uint64(r)))
        if bool(np.all((dist == 0) | (dist >= d))):
            good_list.append(o)
    if not good_list:
        return [], [], []
    nuovo_id = {o: i for i, o in enumerate(good_list)}
    orbits = [tuple(sorted(int(words[i]) for i in members[o])) for o in good_list]
    weights = [len(o) for o in orbits]

    # 2. compatibility: the representative against every word, in one go
    neighbours = [set(range(len(good_list))) - {i} for i in range(len(good_list))]
    for i, o in enumerate(good_list):
        dist = np.bitwise_count(np.bitwise_xor(words, np.uint64(rapp[o])))
        culprits = orbit_of[(dist > 0) & (dist < d)]
        for c in set(int(x) for x in culprits):
            j = nuovo_id.get(c)
            if j is not None and j != i:
                neighbours[i].discard(j)
                neighbours[j].discard(i)
    return orbits, weights, neighbours


def orbite_utilizzabili(n: int, d: int, w: int, group) -> list[tuple[int, ...]]:
    """The orbits of weight w that respect distance d internally."""
    t = w - d // 2
    seen = set()
    outside = []
    for support in combinations(range(n), w):
        word = sum(1 << i for i in support)
        if word in seen:
            continue
        orbit = set()
        for p in group:
            f = 0
            for i in support:
                f |= 1 << p[i]
            orbit.add(f)
        seen |= orbit
        orbit = tuple(sorted(orbit))
        good = all((a ^ b).bit_count() >= d for a, b in combinations(orbit, 2))
        if good:
            outside.append(orbit)
    return outside


def compatibilita(orbits: list[tuple[int, ...]], d: int) -> list[set[int]]:
    """For each orbit, the set of orbits it can coexist with."""
    m = len(orbits)
    neighbours: list[set[int]] = [set() for _ in range(m)]
    for i in range(m):
        for j in range(i + 1, m):
            if all((a ^ b).bit_count() >= d for a in orbits[i] for b in orbits[j]):
                neighbours[i].add(j)
                neighbours[j].add(i)
    return neighbours


def weighted_clique(weights: list[int], neighbours: list[set[int]], *,
                  restarts: int = 200, seed: int = 0,
                  local_steps: int = 60) -> list[int]:
    """Greedy with random restarts and a local search. Returns the chosen indices."""
    rng = random.Random(seed)
    m = len(weights)
    best: list[int] = []
    best_value = 0

    def complete(chosen: list[int], permitted: set[int]) -> tuple[list[int], int]:
        chosen = list(chosen)
        permitted = set(permitted)
        while permitted:
            # prefer the high weight, and on a tie whoever leaves more options
            candidates = sorted(permitted, key=lambda i: (-weights[i], -len(neighbours[i] & permitted)))
            head = candidates[:3]
            pick = rng.choice(head) if len(head) > 1 and rng.random() < 0.3 else candidates[0]
            chosen.append(pick)
            permitted &= neighbours[pick]
        return chosen, sum(weights[i] for i in chosen)

    for _ in range(restarts):
        chosen, value = complete([], set(range(m)))
        for _ in range(local_steps):
            if len(chosen) <= 1:
                break
            k = min(len(chosen), rng.randint(1, 3))
            kept = rng.sample(chosen, len(chosen) - k)
            permitted = set(range(m))
            for i in kept:
                permitted &= neighbours[i]
            permitted -= set(kept)
            new_items, new_value = complete(kept, permitted)
            if new_value >= value:
                chosen, value = new_items, new_value
        if value > best_value:
            best, best_value = chosen, value
    return best


def search_for(n: int, d: int, w: int, groups: dict, *, restarts: int = 200,
          seed: int = 0, max_orbits: int = 8_000) -> dict:
    """Try every group and return the best code found.

    Groups that are too small are discarded: with a small |G| there are as many
    orbits as words, the compatibility graph becomes enormous and the method loses
    its advantage. The case that taught this: `blocks7x3` on n=21 has order 3, hence
    98 thousand orbits and 29 billion comparisons.
    """
    from math import comb
    results = {}
    best = {"words": [], "size": 0, "group": None}
    for name, G in groups.items():
        if comb(n, w) / len(G) > max_orbits:
            results[name] = {"saltato": f"circa {comb(n, w) // len(G)} orbits"}
            continue
        orb, weights, neigh = orbits_and_compatibility(n, d, w, G)
        if not orb:
            results[name] = {"orbits": 0, "size": 0}
            continue
        chosen = weighted_clique(weights, neigh, restarts=restarts, seed=seed)
        words = [x for i in chosen for x in orb[i]]
        v = fast_check(words, n, d, w)
        assert v.ok, f"the search produced an invalid code: {v.findings[:2]}"
        results[name] = {"orbits": len(orb), "order": len(G),
                       "size": len(words)}
        if len(words) > best["size"]:
            best = {"words": sorted(words), "size": len(words),
                        "group": name}
    return {"best": best, "per_gruppo": results}
