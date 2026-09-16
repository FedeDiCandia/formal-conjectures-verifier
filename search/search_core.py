"""
La ricerca: un code invariante below un group, di size massima.

IL PROBLEM, RIDOTTO
--------------------
Fissati n, d, w e un group G di permutazioni delle n positions:

  1. le words di weight w si spezzano in orbits below G;
  2. un'orbit è **utilizzabile** se le sue words sono a two a two a distance
     ≥ d (altrimenti il code non può contenerla tutta);
  3. two orbits utilizzabili sono **compatibili** se ogni word dell'one dista
     ≥ d da ogni word dell'altra;
  4. il più grande code G-invariante è l'insieme di orbits a two a two
     compatibili di weight total maximum: one **clique massima pesata**.

Il step 4 è NP-difficile in generale, ma qui i grafi sono piccoli perché il
group ha già fatto il job. Si usa un greedy con restarts casuali più one
ricerca local (strip k orbits, riempi con le best_list permitted): è lo stesso kind
di euristica con cui sono stati found i record in tabella, e su un Mac basta.
"""
from __future__ import annotations

import random
from itertools import combinations

from math import comb

from codes import fast_check


# ---------------------------------------------------------------------------
# DUE SEMPLIFICAZIONI ESATTE, non euristiche, che rendono il computation possibile
#
# 1. Un'orbit e' utilizzabile se e only se **un suo rappresentante** dista >= d
#    da all_items le other_items words dell'orbit. Non serve controllare all_items le pairs:
#    se a' = g(a), allora dist(g(a), b) = dist(a, g^-1(b)) e g^-1(b) sta ancora
#    nell'orbit, quindi le pairs che coinvolgono a' sono le stesse che
#    coinvolgono a, riordinate.
#
# 2. Per lo stesso reason, two orbits sono compatibili se e only se **un
#    rappresentante della before** dista >= d da all_items le words della seconda.
#
# Insieme fanno risparmiare un factor even alla size dell'orbit -- da decine a
# centinaia. Il resto lo fa numpy: un only XOR fra il rappresentante e l'intero
# vettore delle words, e `bitwise_count` per i weights.


def _orbit_table(n: int, w: int, group):
    """Tutte le words di weight w, l'orbit di ognuna, e un rappresentante."""
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
    """Le orbits utilizzabili, i loro weights e il grafo di compatibilita."""
    import numpy as np
    words, orbit_of, rapp, members = _orbit_table(n, w, group)
    # 1. utilizzabilita: il rappresentante against i suoi compagni di orbit
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

    # 2. compatibilita: il rappresentante against all_items le words, in un colpo
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
    """Le orbits di weight w che al loro interno rispettano la distance d."""
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
    """Per ogni orbit, l'insieme delle orbits con cui può convivere."""
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
    """Greedy con restarts casuali e ricerca local. Restituisce gli indices chosen."""
    rng = random.Random(seed)
    m = len(weights)
    best: list[int] = []
    best_value = 0

    def complete(chosen: list[int], permitted: set[int]) -> tuple[list[int], int]:
        chosen = list(chosen)
        permitted = set(permitted)
        while permitted:
            # preferisci il weight high, a parità chi lascia più opzioni
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
    """Prova ogni group e restituisce il best code found.

    I groups troppo piccoli si scartano: con |G| piccolo le orbits sono tante
    how_many le words, il grafo di compatibilita' diventa enorme e il method perde
    il suo vantaggio. Il caso che ha fatto sbattere il naso: `blocchi7x3` su n=21
    ha order 3, quindi 98 mila orbits e 29 miliardi di confronti.
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
        assert v.ok, f"la ricerca ha prodotto un code non valid: {v.findings[:2]}"
        results[name] = {"orbits": len(orb), "order": len(G),
                       "size": len(words)}
        if len(words) > best["size"]:
            best = {"words": sorted(words), "size": len(words),
                        "group": name}
    return {"best": best, "per_gruppo": results}
