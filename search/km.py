"""
Kramer–Mesner: group prescritto + programmazione lineare intera **esatta**.

WHY THIS IS THE RIGHT TOOL, AND HEURISTICS ARE NOT
----------------------------------------------------------------
A constant-weight code with even d is an object of design theory. Setting
t = w − d/2, two words possono condividere al maximum t positions, cioè

    **every subset of t+1 positions lies in at most one word.**

For A(27,8,5) we have t = 1: these are the 5-element subsets of a 27-element set,
pairwise meeting in at most one point. It is the **packing number**
D(27,5,2), and Schönheim's bound gives 32 while the table publishes 31. The
question is not vague: **is D(27,5,2) 31 or 32?**

Put that way it becomes a *set packing* problem, that is an ILP:

    variables    z_B ∈ {0,1} for each candidate word B
    constraints  for each (t+1)-subset S:  Σ_{B ⊇ S} z_B ≤ 1
    goal   massimizzare Σ z_B

With a **prescribed group** G the ILP shrinks enormously: one looks for *orbits*
instead of words, and by symmetry **one constraint per orbit of
(t+1)-sottoinsiemi**. Su A(27,8,5) below Z27 si passa da 80.730 variables e 351
vincoli a 2.990 variables e 13 vincoli.

**The difference that counts:** the ILP does not return "I found one", it returns
"this is the maximum". The maximum G-invariant code becomes a proved fact, not a
search result. A heuristic can never say "32 is impossible under Z27"; this can.


The solver is HiGHS, free and on a single machine — the case the plan called "a
weapon we can pick up too", not a barrier.
"""
from __future__ import annotations

from itertools import combinations

import highspy
import numpy as np

from codes import fast_check


def orbit_subsets(n: int, size: int, group) -> tuple[list[tuple], dict]:
    """The orbits of the subsets of `size` points, and the map subset -> orbit."""
    whose: dict[tuple, int] = {}
    representatives: list[tuple] = []
    for S in combinations(range(n), size):
        if S in whose:
            continue
        o = len(representatives)
        representatives.append(S)
        for p in group:
            whose[tuple(sorted(p[i] for i in S))] = o
    return representatives, whose


def word_orbits(n: int, w: int, group) -> list[tuple[int, ...]]:
    """The orbits of the words of weight w, as tuples of supports."""
    seen = set()
    outside = []
    for S in combinations(range(n), w):
        if S in seen:
            continue
        orbit = {tuple(sorted(p[i] for i in S)) for p in group}
        seen |= orbit
        outside.append(tuple(sorted(orbit)))
    return outside


def solve(n: int, d: int, w: int, group, *, seconds: float = 300.0,
            silence: bool = True) -> dict:
    """The maximum G-invariant code, by exact ILP. It also says whether it is optimal."""
    if d % 2:
        raise ValueError("even d is required")
    t = w - d // 2
    if t < 0:
        return {"size": 0, "optimal": True, "note": "d too large"}
    if t >= w:
        return {"size": 0, "optimal": False, "note": "no constraint"}

    orbits = word_orbits(n, w, group)
    _, whose = orbit_subsets(n, t + 1, group)
    n_constraints = max(whose.values()) + 1

    # coefficient: how many words of the orbit contain a given (t+1)-subset.
    # By symmetry one constraint per orbit of subsets suffices, and any S of the
    # class serves as representative.
    coef = np.zeros((n_constraints, len(orbits)), dtype=np.float64)
    sample: dict[int, tuple] = {}
    for S, o in whose.items():
        sample.setdefault(o, S)
    for j, orbit in enumerate(orbits):
        for block in orbit:
            for S in combinations(block, t + 1):
                o = whose[S]
                if sample[o] == S:
                    coef[o, j] += 1

    h = highspy.Highs()
    if silence:
        h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", float(seconds))
    inf = highspy.kHighsInf
    for orbit in orbits:
        h.addVar(0.0, 1.0)
    h.changeColsIntegrality(len(orbits), np.arange(len(orbits), dtype=np.int32),
                            np.array([highspy.HighsVarType.kInteger] * len(orbits)))
    h.changeColsCost(len(orbits), np.arange(len(orbits), dtype=np.int32),
                     np.array([-float(len(o)) for o in orbits]))   # minimizza -Σ|O|z
    for i in range(n_constraints):
        idx = np.flatnonzero(coef[i])
        if len(idx) == 0:
            continue
        h.addRow(-inf, 1.0, len(idx), idx.astype(np.int32), coef[i, idx])
    h.run()
    state = h.getModelStatus()
    sol = h.getSolution()
    z = np.array(sol.col_value)
    choices = [j for j in range(len(orbits)) if z[j] > 0.5]
    supports = [b for j in choices for b in orbits[j]]
    words = sorted(sum(1 << i for i in b) for b in supports)
    v = fast_check(words, n, d, w)
    return {"size": len(words),
            "optimal": h.modelStatusToString(state) == "Optimal",
            "state": h.modelStatusToString(state),
            "limite_lp": round(-h.getInfo().mip_dual_bound, 3),
            "orbits": len(orbits), "vincoli": n_constraints,
            "valid": v.ok, "findings": v.findings[:2],
            "words": words if v.ok else []}


def risolvi_completo(n: int, d: int, w: int, *, seconds: float = 1800.0,
                     silence: bool = False, threshold: int | None = None) -> dict:
    """The ILP **without a prescribed group**: every word, every constraint.

    WHY IT IS WORTH IT
    -------------------
    For A(27,8,5) that is 80,730 binary variables and 351 constraints (one per pair
    of points). It is pure *set packing*, the form modern solvers are most
    forti. E l'result è decisivo in **entrambi** i sensi:

      * if it finds a code of 32 words, then D(27,5,2) = 32 and the cell is closed;
      * if it proves 31 is optimal, then D(27,5,2) = 31 and the cell is closed
        ugualmente.

    The table today says "between 31 and 32". Either answer settles it.
    A heuristic cannot give the second; an ILP can.

    `threshold`: if given, the constraint Σ z ≥ threshold is added. Asking "is there
    a code of 32?" instead of "what is the maximum?" is often far easier for the
    solver, because it only has to find one or prove infeasibility.
    """
    t = w - d // 2
    if t < 0 or t >= w:
        raise ValueError(f"t = {t} outside dai cases useful")

    supports = list(combinations(range(n), w))
    indice_S = {S: i for i, S in enumerate(combinations(range(n), t + 1))}
    lines: list[list[int]] = [[] for _ in indice_S]
    for j, B in enumerate(supports):
        for S in combinations(B, t + 1):
            lines[indice_S[S]].append(j)

    h = highspy.Highs()
    if silence:
        h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", float(seconds))
    h.setOptionValue("mip_rel_gap", 0.0)
    inf = highspy.kHighsInf
    for _ in supports:
        h.addVar(0.0, 1.0)
    idx_tutti = np.arange(len(supports), dtype=np.int32)
    h.changeColsIntegrality(
        len(supports), idx_tutti,
        np.array([highspy.HighsVarType.kInteger] * len(supports)))
    h.changeColsCost(len(supports), idx_tutti,
                     np.full(len(supports), -1.0))
    for columns in lines:
        if columns:
            a = np.array(columns, dtype=np.int32)
            h.addRow(-inf, 1.0, len(a), a, np.ones(len(a)))
    if threshold is not None:
        h.addRow(float(threshold), inf, len(idx_tutti), idx_tutti,
                 np.ones(len(idx_tutti)))
    h.run()
    state = h.modelStatusToString(h.getModelStatus())
    z = np.array(h.getSolution().col_value)
    choices = [supports[j] for j in range(len(supports)) if z[j] > 0.5]
    words = sorted(sum(1 << i for i in B) for B in choices)
    v = fast_check(words, n, d, w) if words else None
    return {"size": len(words), "state": state,
            "optimal": state == "Optimal",
            "infattibile": state == "Infeasible",
            "limite_lp": round(-h.getInfo().mip_dual_bound, 3),
            "variables": len(supports), "vincoli": len(lines),
            "valid": bool(v and v.ok), "words": words if v and v.ok else []}
