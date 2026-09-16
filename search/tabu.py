"""
Il second motore: ricerca local diretta sulle words.

PERCHÉ SERVE UN SECONDO MOTORE
------------------------------
Il first motore (`search_core.py`) search_for codici **invarianti below un group**. È
elegante e veloce, ma ha un limit di principio che si è visto subito: per
A(21,10,9) le orbits below Z21 hanno size 7 o 21, e nessuna total_sum di 7 e 21 fa
27, che è il limit pubblicato. Nessuna quantità di ricerca può arrivarci per
quella strada: **il record non è invariante below quel group.**

Questo motore non assume niente. Fissa un goal m (how_many words vogliamo),
parte da m words qualunque, e minimizza il number di pairs che violano la
distance scambiando one word alla volta. Se arriva a zero violations, abbiamo un
code di m words. È la tabu search «a level di scambi» con cui sono stati
ottenuti i miglioramenti recenti nelle tables di Brouwer.

STRATEGIA
---------
Si parte da m = limit pubblicato e si tenta. Se riesce, si trial m+1: è lì che un
record cadrebbe. Se non riesce, si scende. Il cost della funzione goal è
tenuto low ricalcolando only la line della word che cambia.
"""
from __future__ import annotations

import random
from itertools import combinations

import numpy as np


def _all_words(n: int, w: int) -> np.ndarray:
    from math import comb
    return np.fromiter((sum(1 << i for i in c) for c in combinations(range(n), w)),
                       dtype=np.uint64, count=comb(n, w))


def _conflicts(words: np.ndarray, choices: np.ndarray, d: int) -> np.ndarray:
    """Per ogni word scelta, how_many delle other_items choices sono troppo neighbours."""
    x = words[choices]
    dist = np.bitwise_count(np.bitwise_xor(x[:, None], x[None, :]))
    bad_list = (dist < d)
    np.fill_diagonal(bad_list, False)
    return bad_list.sum(axis=1)


def size_trial(n: int, d: int, w: int, m: int, *, iterations: int = 60_000,
                     seed: int = 0, words: np.ndarray | None = None,
                     start: list[int] | None = None) -> tuple[list[int], int]:
    """Cerca un code di esattamente m words. Restituisce (words, violations)."""
    rng = np.random.default_rng(seed)
    all_items = _all_words(n, w) if words is None else words
    N = len(all_items)
    if m > N:
        return [], m * m
    choices = (np.array(start, dtype=np.int64) if start is not None
              else rng.choice(N, size=m, replace=False))
    if len(choices) != m:
        choices = rng.choice(N, size=m, replace=False)

    conf = _conflicts(all_items, choices, d)
    total = int(conf.sum()) // 2
    best = total
    tabu: dict[int, int] = {}
    for step in range(iterations):
        if total == 0:
            break
        # Si sostituisce one delle words piu' in conflitto -- ma non sempre: con
        # probabilita' fix si prende one word in conflitto QUALUNQUE. Senza
        # questa walk casuale la ricerca cicla fra le stesse two
        # configurazioni, ed e' la ragione misurata per cui sulle cells con divario
        # aperto i residui restavano grandi e costanti (69-441 violations).
        if rng.random() < 0.25:
            in_conflict = np.flatnonzero(conf > 0)
            slot = int(rng.choice(in_conflict)) if len(in_conflict) else 0
        else:
            worst_list = np.flatnonzero(conf == conf.max())
            slot = int(rng.choice(worst_list))
        previous = int(choices[slot])
        other_items = np.delete(choices, slot)
        x = all_items[other_items]
        # how_many violations porterebbe ogni possibile sostituta
        cost = np.zeros(N, dtype=np.int32)
        block = 4096
        for i in range(0, N, block):
            slice = all_items[i:i + block]
            dist = np.bitwise_count(np.bitwise_xor(slice[:, None], x[None, :]))
            cost[i:i + block] = (dist < d).sum(axis=1)
        cost[other_items] = 10_000                      # gia' nel code
        for word, fino in list(tabu.items()):
            if fino > step:
                cost[word] += 50
            else:
                del tabu[word]
        minimum = cost.min()
        candidates = np.flatnonzero(cost == minimum)
        new = int(rng.choice(candidates))
        choices[slot] = new
        tabu[previous] = step + max(5, m // 4)
        conf = _conflicts(all_items, choices, d)
        total = int(conf.sum()) // 2
        best = min(best, total)
    return [int(all_items[i]) for i in choices], total


def spingi(n: int, d: int, w: int, start_point: int, *, cap: int = 6,
           iterations: int = 40_000, seed: int = 0) -> dict:
    """Parte da `start_point` words e sale finche' riesce."""
    words = _all_words(n, w)
    succeeded: list[int] = []
    m = start_point
    results = {}
    while m <= start_point + cap:
        found, violations = size_trial(n, d, w, m, iterations=iterations,
                                               seed=seed, words=words)
        results[m] = violations
        if violations == 0:
            succeeded = found
            m += 1
        else:
            break
    return {"size": len(succeeded), "words": sorted(succeeded),
            "attempts": results}
