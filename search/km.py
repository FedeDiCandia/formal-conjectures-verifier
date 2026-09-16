"""
Kramer–Mesner: gruppo prescritto + programmazione lineare intera **esatta**.

PERCHÉ QUESTO È LO STRUMENTO GIUSTO, E LE EURISTICHE NON LO SONO
----------------------------------------------------------------
Un codice a peso costante con d pari è un oggetto di teoria dei disegni. Posto
t = w − d/2, due parole possono condividere al massimo t posizioni, cioè

    **ogni sottoinsieme di t+1 posizioni sta in al massimo una parola.**

Per A(27,8,5) si ha t = 1: sono i sottoinsiemi di 5 elementi di un insieme di 27, a
due a due intersecantisi in al massimo un punto. È il **numero di pacchetto**
D(27,5,2), e il limite di Schönheim dà 32 mentre la tabella pubblica 31. La domanda
non è vaga: **D(27,5,2) vale 31 o 32?**

Messo così diventa un problema di *set packing*, cioè un ILP:

    variabili   z_B ∈ {0,1} per ogni parola candidata B
    vincoli     per ogni (t+1)-sottoinsieme S:  Σ_{B ⊇ S} z_B ≤ 1
    obiettivo   massimizzare Σ z_B

Con un **gruppo prescritto** G l'ILP si riduce enormemente: si cercano *orbite*
invece di parole, e per simmetria basta **un vincolo per orbita di
(t+1)-sottoinsiemi**. Su A(27,8,5) sotto Z27 si passa da 80.730 variabili e 351
vincoli a 2.990 variabili e 13 vincoli.

**La differenza che conta:** l'ILP non restituisce «ho trovato», restituisce
«questo è il massimo». Il massimo codice G-invariante diventa un fatto dimostrato,
non un esito di ricerca. Una euristica non potrà mai dire «32 è impossibile sotto
Z27»; questo sì.

Il solutore è HiGHS, libero e su una macchina sola — il caso che nel piano avevo
chiamato «un'arma che possiamo prendere anche noi», non una barriera.
"""
from __future__ import annotations

from itertools import combinations

import highspy
import numpy as np

from codes import verifica_veloce


def sottoinsiemi_orbite(n: int, taglia: int, gruppo) -> tuple[list[tuple], dict]:
    """Le orbite dei sottoinsiemi di `taglia` punti, e la mappa insieme -> orbita."""
    di_chi: dict[tuple, int] = {}
    rappresentanti: list[tuple] = []
    for S in combinations(range(n), taglia):
        if S in di_chi:
            continue
        o = len(rappresentanti)
        rappresentanti.append(S)
        for p in gruppo:
            di_chi[tuple(sorted(p[i] for i in S))] = o
    return rappresentanti, di_chi


def orbite_parole(n: int, w: int, gruppo) -> list[tuple[int, ...]]:
    """Le orbite delle parole di peso w, come tuple di supporti."""
    viste = set()
    fuori = []
    for S in combinations(range(n), w):
        if S in viste:
            continue
        orbita = {tuple(sorted(p[i] for i in S)) for p in gruppo}
        viste |= orbita
        fuori.append(tuple(sorted(orbita)))
    return fuori


def risolvi(n: int, d: int, w: int, gruppo, *, secondi: float = 300.0,
            silenzio: bool = True) -> dict:
    """Il massimo codice G-invariante, per ILP esatto. Restituisce anche se è ottimo."""
    if d % 2:
        raise ValueError("serve d pari")
    t = w - d // 2
    if t < 0:
        return {"dimensione": 0, "ottimo": True, "nota": "d troppo grande"}
    if t >= w:
        return {"dimensione": 0, "ottimo": False, "nota": "nessun vincolo"}

    orbite = orbite_parole(n, w, gruppo)
    _, di_chi = sottoinsiemi_orbite(n, t + 1, gruppo)
    n_vincoli = max(di_chi.values()) + 1

    # coefficiente: quante parole dell'orbita contengono un dato (t+1)-sottoinsieme.
    # Per simmetria basta un vincolo per orbita di sottoinsiemi, e come
    # rappresentante si prende un qualunque S della classe.
    coef = np.zeros((n_vincoli, len(orbite)), dtype=np.float64)
    campione: dict[int, tuple] = {}
    for S, o in di_chi.items():
        campione.setdefault(o, S)
    for j, orbita in enumerate(orbite):
        for blocco in orbita:
            for S in combinations(blocco, t + 1):
                o = di_chi[S]
                if campione[o] == S:
                    coef[o, j] += 1

    h = highspy.Highs()
    if silenzio:
        h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", float(secondi))
    inf = highspy.kHighsInf
    for orbita in orbite:
        h.addVar(0.0, 1.0)
    h.changeColsIntegrality(len(orbite), np.arange(len(orbite), dtype=np.int32),
                            np.array([highspy.HighsVarType.kInteger] * len(orbite)))
    h.changeColsCost(len(orbite), np.arange(len(orbite), dtype=np.int32),
                     np.array([-float(len(o)) for o in orbite]))   # minimizza -Σ|O|z
    for i in range(n_vincoli):
        idx = np.flatnonzero(coef[i])
        if len(idx) == 0:
            continue
        h.addRow(-inf, 1.0, len(idx), idx.astype(np.int32), coef[i, idx])
    h.run()
    stato = h.getModelStatus()
    sol = h.getSolution()
    z = np.array(sol.col_value)
    scelte = [j for j in range(len(orbite)) if z[j] > 0.5]
    supporti = [b for j in scelte for b in orbite[j]]
    parole = sorted(sum(1 << i for i in b) for b in supporti)
    v = verifica_veloce(parole, n, d, w)
    return {"dimensione": len(parole),
            "ottimo": h.modelStatusToString(stato) == "Optimal",
            "stato": h.modelStatusToString(stato),
            "limite_lp": round(-h.getInfo().mip_dual_bound, 3),
            "orbite": len(orbite), "vincoli": n_vincoli,
            "valido": v.ok, "difetti": v.difetti[:2],
            "parole": parole if v.ok else []}


def risolvi_completo(n: int, d: int, w: int, *, secondi: float = 1800.0,
                     silenzio: bool = False, soglia: int | None = None) -> dict:
    """L'ILP **senza gruppo prescritto**: tutte le parole, tutti i vincoli.

    PERCHÉ VALE LA PENA
    -------------------
    Per A(27,8,5) sono 80.730 variabili binarie e 351 vincoli (uno per coppia di
    punti). È un *set packing* puro, la forma su cui i solutori moderni sono più
    forti. E l'esito è decisivo in **entrambi** i sensi:

      * se trova un codice di 32 parole, allora D(27,5,2) = 32 e la cella è chiusa;
      * se dimostra che 31 è l'ottimo, allora D(27,5,2) = 31 e la cella è chiusa
        ugualmente.

    La tabella oggi dice «fra 31 e 32». Qualunque delle due risposte la determina.
    Un'euristica non può dare la seconda; un ILP sì.

    `soglia`: se data, si aggiunge il vincolo Σ z ≥ soglia. Chiedere «esiste un
    codice di 32?» invece di «qual è il massimo?» è spesso molto più facile per il
    solutore, perché basta trovarne uno o dimostrare l'infattibilità.
    """
    t = w - d // 2
    if t < 0 or t >= w:
        raise ValueError(f"t = {t} fuori dai casi utili")

    supporti = list(combinations(range(n), w))
    indice_S = {S: i for i, S in enumerate(combinations(range(n), t + 1))}
    righe: list[list[int]] = [[] for _ in indice_S]
    for j, B in enumerate(supporti):
        for S in combinations(B, t + 1):
            righe[indice_S[S]].append(j)

    h = highspy.Highs()
    if silenzio:
        h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", float(secondi))
    h.setOptionValue("mip_rel_gap", 0.0)
    inf = highspy.kHighsInf
    for _ in supporti:
        h.addVar(0.0, 1.0)
    idx_tutti = np.arange(len(supporti), dtype=np.int32)
    h.changeColsIntegrality(
        len(supporti), idx_tutti,
        np.array([highspy.HighsVarType.kInteger] * len(supporti)))
    h.changeColsCost(len(supporti), idx_tutti,
                     np.full(len(supporti), -1.0))
    for colonne in righe:
        if colonne:
            a = np.array(colonne, dtype=np.int32)
            h.addRow(-inf, 1.0, len(a), a, np.ones(len(a)))
    if soglia is not None:
        h.addRow(float(soglia), inf, len(idx_tutti), idx_tutti,
                 np.ones(len(idx_tutti)))
    h.run()
    stato = h.modelStatusToString(h.getModelStatus())
    z = np.array(h.getSolution().col_value)
    scelte = [supporti[j] for j in range(len(supporti)) if z[j] > 0.5]
    parole = sorted(sum(1 << i for i in B) for B in scelte)
    v = verifica_veloce(parole, n, d, w) if parole else None
    return {"dimensione": len(parole), "stato": stato,
            "ottimo": stato == "Optimal",
            "infattibile": stato == "Infeasible",
            "limite_lp": round(-h.getInfo().mip_dual_bound, 3),
            "variabili": len(supporti), "vincoli": len(righe),
            "valido": bool(v and v.ok), "parole": parole if v and v.ok else []}
