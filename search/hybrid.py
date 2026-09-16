"""
The hybrid engine: **start from the group, repair by hand.**

WHY
---
On the 34 cells with an open gap, the two engines taken separately fail in different
ways:

  * the **local search from random words** matched 1 cell of 34, with residuals of
    69-441 violations: it is not close, it is in the wrong region. The space is too
    large to start from nothing;
  * the **orbit engine** matches at once where the record is invariant (A(19,6,5) in
    0.8 s, A(22,6,5) in 48 s) but stalls below where it is not: A(17,6,6) reaches 85
    against 113, because no sum of orbit sizes makes 113.

The real records sit in between, and that is exactly how they were built: **a group
gives the structure, and a few local moves adjust it.** A code of 5558 words is a
group of order 504 plus 19 seeds *chosen by hand*.

HOW
---
  1. the orbit engine gives the best invariant code under a group;
  2. it is **extended** greedily with every compatible word (often few or none: the
     invariant code is usually already maximal in its class);
  3. words are added in steps up to the target;
  4. the local search **repairs**, starting from there instead of from chance.

Step 4 now also has a random walk: with a fixed probability it replaces a word in
conflict **at random** instead of the worst one. Without that the search cycles
between the same two configurations, and that is why the residuals were what they
were.
"""
from __future__ import annotations

import numpy as np

from search_core import orbits_and_compatibility
from codes import fast_check
from groups import group_names
from tabu import _conflicts, _all_words, size_trial


def word_index(all_items: np.ndarray) -> dict[int, int]:
    return {int(p): k for k, p in enumerate(all_items)}


def best_invariant(n: int, d: int, w: int, *, restarts: int = 300,
                       max_orbits: int = 4_000) -> tuple[list[int], str]:
    """The best invariant code under one of the repertoire's groups.

    The cap on orbits is 4,000 and not 40,000 for a measured reason: the clique
    search costs about m^2 per completion, so with 27,000 orbits (the case of
    `blocks9x3` on A(27,8,5), a group of order 3) a single restart is half a billion
    operations and the function never returns. And small groups are no use: the whole
    advantage of the method lies in having FEW large orbits.
    """
    from math import comb
    from search_core import weighted_clique
    best: list[int] = []
    best_name = ""
    for name, G in group_names(n).items():
        if comb(n, w) / len(G) > max_orbits:
            continue
        orbits, weights, neighbours = orbits_and_compatibility(n, d, w, G)
        if not orbits:
            continue
        chosen = weighted_clique(weights, neighbours, restarts=restarts)
        words = [x for i in chosen for x in orbits[i]]
        if len(words) > len(best):
            best, best_name = words, name
    return sorted(best), best_name


def extend(words: list[int], all_items: np.ndarray, d: int) -> list[int]:
    """Greedily add every word compatible with all those already inside."""
    inside = list(words)
    if not inside:
        return inside
    choices = np.array(inside, dtype=np.uint64)
    while True:
        dist = np.bitwise_count(np.bitwise_xor(all_items[:, None], choices[None, :]))
        permitted = np.flatnonzero((dist >= d).all(axis=1))
        if len(permitted) == 0:
            return [int(x) for x in choices]
        # the first admitted one, then re-checked: so it stays valid at every step
        choices = np.append(choices, all_items[permitted[0]])


def da_gruppo(n: int, d: int, w: int, goal: int, *, iterations: int = 30_000,
              seeds: int = 3, restarts: int = 300) -> dict:
    """Cerca `goal` words partendo dal miglior code invariante."""
    all_items = _all_words(n, w)
    position = word_index(all_items)
    word_seed, group = best_invariant(n, d, w, restarts=restarts)
    word_seed = extend(word_seed, all_items, d)
    result = {"invariante": len(word_seed), "group": group,
             "goal": goal}
    if len(word_seed) >= goal:
        words = sorted(word_seed)[:goal]
        result.update({"violations": 0, "words": words,
                      "note": "the invariant code was enough"})
        return result

    base = [position[p] for p in word_seed]
    rng = np.random.default_rng(0)
    best_violations = None
    best_words: list[int] = []
    for s in range(seeds):
        free = np.setdiff1d(np.arange(len(all_items)), np.array(base, dtype=np.int64))
        extra = rng.choice(free, size=goal - len(base), replace=False)
        start = base + [int(x) for x in extra]
        words, violations = size_trial(n, d, w, goal,
                                              iterations=iterations, seed=s,
                                              words=all_items, start=start)
        if best_violations is None or violations < best_violations:
            best_violations, best_words = violations, words
        if violations == 0:
            break
    result["violations"] = best_violations
    if best_violations == 0 and fast_check(best_words, n, d, w).ok:
        result["words"] = sorted(best_words)
    return result


def sali_a_gradini(n: int, d: int, w: int, goal: int, *,
                   iterations_per_step: int = 4_000, restarts: int = 300,
                   pazienza: int = 3) -> dict:
    """Dal code invariante all'goal, **one word alla volta**.

    WHY IN STEPS, AND NOT IN ONE LEAP
    -----------------------------------
    Measured: starting from the invariant code and adding in one go the words
    missing up to the target leaves many violations the repair cannot clear — on
    A(17,6,6) the leap from 85 to 113 leaves 63 violations. Adding one word at a
    time, every repair starts from a **valid** configuration and has very little to
    fix. It is the difference between solving a problem and
    risolverne ventotto insieme.

    Si sale finché si riesce; after `pazienza` steps failed di fila si smette e si
    returns the best valid code reached.
    """
    all_items = _all_words(n, w)
    position = word_index(all_items)
    words, group = best_invariant(n, d, w, restarts=restarts)
    words = extend(words, all_items, d)
    history = {"invariante": len(words), "group": group, "steps": {}}
    rng = np.random.default_rng(0)
    failed = 0

    while len(words) < goal and failed < pazienza:
        milestone = len(words) + 1
        base = [position[p] for p in words]
        free = np.setdiff1d(np.arange(len(all_items)), np.array(base, dtype=np.int64))
        won = None
        for attempt in range(pazienza):
            extra = int(rng.choice(free))
            new_items, violations = size_trial(
                n, d, w, milestone, iterations=iterations_per_step,
                seed=milestone * 17 + attempt, words=all_items,
                start=base + [extra])
            if violations == 0:
                won = new_items
                break
        history["steps"][milestone] = "succeeded" if won else "failed"
        if won is None:
            failed += 1
        else:
            failed = 0
            words = sorted(won)

    valid = fast_check(words, n, d, w)
    history.update({"size": len(words), "goal": goal,
                   "valid": valid.ok,
                   "words": sorted(words) if valid.ok else []})
    if not valid.ok:
        history["findings"] = valid.findings[:3]
    return history
