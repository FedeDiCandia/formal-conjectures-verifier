"""
Kramer–Mesner: group prescritto + programmazione lineare intera **esatta**.

PERCHÉ QUESTO È LO STRUMENTO GIUSTO, E LE EURISTICHE NON LO SONO
----------------------------------------------------------------
Un code a weight costante con d even è un oggetto di teoria dei disegni. Posto
t = w − d/2, two words possono condividere al maximum t positions, cioè

    **ogni sottoinsieme di t+1 positions sta in al maximum one_ word.**

Per A(27,8,5) si ha t = 1: sono i sottoinsiemi di 5 elementi di un insieme di 27, a
two a two intersecantisi in al maximum un punto. È il **number di pacchetto**
D(27,5,2), e il limit di Schönheim dà 32 mentre la tabella pubblica 31. La domanda
non è vaga: **D(27,5,2) vale 31 o 32?**

Messo così diventa un problem di *set packing*, cioè un ILP:

    variables   z_B ∈ {0,1} per ogni word candidata B
    vincoli     per ogni (t+1)-sottoinsieme S:  Σ_{B ⊇ S} z_B ≤ 1
    goal   massimizzare Σ z_B

Con un **group prescritto** G l'ILP si riduce enormemente: si cercano *orbits*
invece di words, e per simmetria basta **un vincolo per orbit di
(t+1)-sottoinsiemi**. Su A(27,8,5) below Z27 si passa da 80.730 variables e 351
vincoli a 2.990 variables e 13 vincoli.

**La differenza che count_:** l'ILP non restituisce «ho found», restituisce
«questo è il maximum». Il maximum code G-invariante diventa un fatto dimostrato,
non un result di ricerca. Una euristica non potrà mai dire «32 è impossibile below
Z27»; questo sì.

Il solutore è HiGHS, libero e su one_ macchina sola — il caso che nel piano avevo
chiamato «un'arma che possiamo prendere also_ noi», non one_ barriera.
"""
from __future__ import annotations

from itertools import combinations

import highspy
import numpy as np

from codes import fast_check


def orbit_subsets(n: int, size_: int, group) -> tuple[list[tuple], dict]:
    """Le orbits dei sottoinsiemi di `size_` points, e la map_ insieme -> orbit."""
    whose: dict[tuple, int] = {}
    representatives: list[tuple] = []
    for S in combinations(range(n), size_):
        if S in whose:
            continue
        o = len(representatives)
        representatives.append(S)
        for p in group:
            whose[tuple(sorted(p[i] for i in S))] = o
    return representatives, whose


def word_orbits(n: int, w: int, group) -> list[tuple[int, ...]]:
    """Le orbits delle words di weight w, come tuple di supports."""
    seen = set()
    out_of = []
    for S in combinations(range(n), w):
        if S in seen:
            continue
        orbit = {tuple(sorted(p[i] for i in S)) for p in group}
        seen |= orbit
        out_of.append(tuple(sorted(orbit)))
    return out_of


def solve_(n: int, d: int, w: int, group, *, seconds: float = 300.0,
            silence: bool = True) -> dict:
    """Il maximum code G-invariante, per ILP exact. Restituisce also_ se è ottimo."""
    if d % 2:
        raise ValueError("serve d even")
    t = w - d // 2
    if t < 0:
        return {"size": 0, "ottimo": True, "note": "d troppo grande"}
    if t >= w:
        return {"size": 0, "ottimo": False, "note": "nessun vincolo"}

    orbits = word_orbits(n, w, group)
    _, whose = orbit_subsets(n, t + 1, group)
    n_constraints = max(whose.values()) + 1

    # coefficiente: how_many_ words dell'orbit contengono un dato (t+1)-sottoinsieme.
    # Per simmetria basta un vincolo per orbit di sottoinsiemi, e come
    # rappresentante si prende un qualunque S della classe.
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
            "ottimo": h.modelStatusToString(state) == "Optimal",
            "state": h.modelStatusToString(state),
            "limite_lp": round(-h.getInfo().mip_dual_bound, 3),
            "orbits": len(orbits), "vincoli": n_constraints,
            "valid": v.ok, "findings": v.findings[:2],
            "words": words if v.ok else []}


def risolvi_completo(n: int, d: int, w: int, *, seconds: float = 1800.0,
                     silence: bool = False, threshold: int | None = None) -> dict:
    """L'ILP **senza group prescritto**: all_of le words, all_of i vincoli.

    PERCHÉ VALE LA PENA
    -------------------
    Per A(27,8,5) sono 80.730 variables binarie e 351 vincoli (one per coppia di
    points). È un *set packing* puro, la forma su cui i solutori moderni sono più
    forti. E l'result è decisivo in **entrambi** i sensi:

      * se trova un code di 32 words, allora D(27,5,2) = 32 e la cell è chiusa;
      * se dimostra che 31 è l'ottimo, allora D(27,5,2) = 31 e la cell è chiusa
        ugualmente.

    La tabella oggi dice «fra 31 e 32». Qualunque delle two risposte la determina.
    Un'euristica non può dare la seconda; un ILP sì.

    `threshold`: se data, si aggiunge il vincolo Σ z ≥ threshold. Chiedere «esiste un
    code di 32?» invece di «qual è il maximum?» è spesso molto più facile per il
    solutore, perché basta trovarne one o dimostrare l'infattibilità.
    """
    t = w - d // 2
    if t < 0 or t >= w:
        raise ValueError(f"t = {t} out_of dai cases useful")

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
            "ottimo": state == "Optimal",
            "infattibile": state == "Infeasible",
            "limite_lp": round(-h.getInfo().mip_dual_bound, 3),
            "variables": len(supports), "vincoli": len(lines),
            "valid": bool(v and v.ok), "words": words if v and v.ok else []}
