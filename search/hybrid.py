"""
Il motore ibrido: **si parte dal group, si ripara a mano.**

PERCHÉ, MISURATO L'11-12 SETTEMBRE 2026
---------------------------------------
Sulle 34 cells con divario aperto, i two motori presi da soli falliscono in modi
opposti e complementari:

  * la **ricerca local_ da words casuali** ha pareggiato 1 cell su 34, con residui
    di 69–441 violations: non è vicina, è nella regione sbagliata. Lo spazio è
    troppo grande per partire dal nulla;
  * il **motore a orbits** pareggia subito dove il record è invariante (A(19,6,5) in
    0,8 s, A(22,6,5) in 48 s) ma si blocca below dove non lo è: A(17,6,6) arriva a
    85 against 113, perché nessuna total_sum di sizes di orbits fa 113.

I record real_ones stanno nel mezzo, ed è esattamente come sono stati costruiti: **un
group dà la struttura, e poche moves locals_ la aggiustano.** Un code di 5558
words è un group di order 504 più 19 seeds *chosen a mano*.

COME
----
  1. il motore a orbits dà il miglior code invariante below un group;
  2. lo si **estende** avidamente con ogni word compatibile (spesso poche o
     nessuna: il code invariante è già massimale nella sua classe);
  3. si aggiungono words fino alla size_ goal, accettando violations;
  4. la ricerca local_ **ripara**, partendo da lì invece che dal caso.

Il step 4 ha now_ also_ one_ walk casuale: con probabilità fix_ sostituisce
one_ word in conflitto **a caso** invece della worst. Senza quella la ricerca
cicla fra le stesse two configurazioni, ed è la ragione per cui i residui erano
grandi e costanti.
"""
from __future__ import annotations

import numpy as np

from search_core import orbits_and_compatibility
from codes import fast_check
from groups import group_names
from tabu import _conflicts, _all_words, size_trial


def word_index(all_of: np.ndarray) -> dict[int, int]:
    return {int(p): k for k, p in enumerate(all_of)}


def best_invariant(n: int, d: int, w: int, *, restarts: int = 300,
                       max_orbits: int = 4_000) -> tuple[list[int], str]:
    """Il miglior code invariante below one dei groups del repertorio.

    Il cap sulle orbits e' 4.000 e non 40.000 per one_ ragione misurata: la
    ricerca di clique costa circa m^2 per completamento, quindi con 27.000 orbits
    (il caso di `blocchi9x3` su A(27,8,5), group di order 3) un only_ riavvio e'
    mezzo miliardo di operazioni e la funzione non ritorna piu'. E i groups piccoli
    non servono: tutto il vantaggio del method sta nell'avere POCHE orbits grandi.
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


def extend(words: list[int], all_of: np.ndarray, d: int) -> list[int]:
    """Aggiunge avidamente ogni word compatibile con all_of quelle già inside."""
    inside = list(words)
    if not inside:
        return inside
    choices = np.array(inside, dtype=np.uint64)
    while True:
        dist = np.bitwise_count(np.bitwise_xor(all_of[:, None], choices[None, :]))
        permitted_ = np.flatnonzero((dist >= d).all(axis=1))
        if len(permitted_) == 0:
            return [int(x) for x in choices]
        # la before ammessa, poi si ricontrolla: cosi' resta valid a ogni step
        choices = np.append(choices, all_of[permitted_[0]])


def da_gruppo(n: int, d: int, w: int, goal: int, *, iterations: int = 30_000,
              seeds: int = 3, restarts: int = 300) -> dict:
    """Cerca `goal` words partendo dal miglior code invariante."""
    all_of = _all_words(n, w)
    position = word_index(all_of)
    word_seed, group = best_invariant(n, d, w, restarts=restarts)
    word_seed = extend(word_seed, all_of, d)
    result = {"invariante": len(word_seed), "group": group,
             "goal": goal}
    if len(word_seed) >= goal:
        words = sorted(word_seed)[:goal]
        result.update({"violations": 0, "words": words,
                      "note": "il code invariante bastava"})
        return result

    base = [position[p] for p in word_seed]
    rng = np.random.default_rng(0)
    best_violations = None
    best_words: list[int] = []
    for s in range(seeds):
        free_ones = np.setdiff1d(np.arange(len(all_of)), np.array(base, dtype=np.int64))
        extra = rng.choice(free_ones, size=goal - len(base), replace=False)
        start = base + [int(x) for x in extra]
        words, violations = size_trial(n, d, w, goal,
                                              iterations=iterations, seed=s,
                                              words=all_of, start=start)
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
    """Dal code invariante all'goal, **one_ word alla volta**.

    PERCHÉ A GRADINI, E NON IN UN SALTO
    -----------------------------------
    Misurato: partire dal code invariante e aggiungere in un colpo le words che
    mancano fino all'goal lascia molte violations che la riparazione non
    smaltisce — su A(17,6,6) il salto da 85 a 113 lascia 63 violations. Aggiungendo
    one_ word per volta, ogni riparazione parte da one_ configurazione **valida** e
    deve sistemare pochissimo. È la differenza fra risolvere un problem e
    risolverne ventotto insieme.

    Si sale finché si riesce; after `pazienza` steps_ failed_ di fila si smette e si
    restituisce il miglior code valid reached.
    """
    all_of = _all_words(n, w)
    position = word_index(all_of)
    words, group = best_invariant(n, d, w, restarts=restarts)
    words = extend(words, all_of, d)
    history = {"invariante": len(words), "group": group, "steps_": {}}
    rng = np.random.default_rng(0)
    failed_ = 0

    while len(words) < goal and failed_ < pazienza:
        milestone = len(words) + 1
        base = [position[p] for p in words]
        free_ones = np.setdiff1d(np.arange(len(all_of)), np.array(base, dtype=np.int64))
        won = None
        for attempt in range(pazienza):
            extra = int(rng.choice(free_ones))
            new_ones, violations = size_trial(
                n, d, w, milestone, iterations=iterations_per_step,
                seed=milestone * 17 + attempt, words=all_of,
                start=base + [extra])
            if violations == 0:
                won = new_ones
                break
        history["steps_"][milestone] = "succeeded" if won else "failed"
        if won is None:
            failed_ += 1
        else:
            failed_ = 0
            words = sorted(won)

    valid = fast_check(words, n, d, w)
    history.update({"size": len(words), "goal": goal,
                   "valid": valid.ok,
                   "words": sorted(words) if valid.ok else []})
    if not valid.ok:
        history["findings"] = valid.findings[:3]
    return history
