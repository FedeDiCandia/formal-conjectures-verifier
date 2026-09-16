"""
Il motore ibrido: **si parte dal gruppo, si ripara a mano.**

PERCHÉ, MISURATO L'11-12 SETTEMBRE 2026
---------------------------------------
Sulle 34 celle con divario aperto, i due motori presi da soli falliscono in modi
opposti e complementari:

  * la **ricerca locale da parole casuali** ha pareggiato 1 cella su 34, con residui
    di 69–441 violazioni: non è vicina, è nella regione sbagliata. Lo spazio è
    troppo grande per partire dal nulla;
  * il **motore a orbite** pareggia subito dove il record è invariante (A(19,6,5) in
    0,8 s, A(22,6,5) in 48 s) ma si blocca sotto dove non lo è: A(17,6,6) arriva a
    85 contro 113, perché nessuna somma di taglie di orbite fa 113.

I record veri stanno nel mezzo, ed è esattamente come sono stati costruiti: **un
gruppo dà la struttura, e poche mosse locali la aggiustano.** Un codice di 5558
parole è un gruppo di ordine 504 più 19 semi *scelti a mano*.

COME
----
  1. il motore a orbite dà il miglior codice invariante sotto un gruppo;
  2. lo si **estende** avidamente con ogni parola compatibile (spesso poche o
     nessuna: il codice invariante è già massimale nella sua classe);
  3. si aggiungono parole fino alla taglia obiettivo, accettando violazioni;
  4. la ricerca locale **ripara**, partendo da lì invece che dal caso.

Il passo 4 ha ora anche una passeggiata casuale: con probabilità fissa sostituisce
una parola in conflitto **a caso** invece della peggiore. Senza quella la ricerca
cicla fra le stesse due configurazioni, ed è la ragione per cui i residui erano
grandi e costanti.
"""
from __future__ import annotations

import numpy as np

from search_core import orbite_e_compatibilita
from codes import verifica_veloce
from groups import nome_gruppi
from tabu import _conflitti, _tutte_le_parole, prova_dimensione


def indice_parole(tutte: np.ndarray) -> dict[int, int]:
    return {int(p): k for k, p in enumerate(tutte)}


def miglior_invariante(n: int, d: int, w: int, *, riavvii: int = 300,
                       massimo_orbite: int = 4_000) -> tuple[list[int], str]:
    """Il miglior codice invariante sotto uno dei gruppi del repertorio.

    Il tetto sulle orbite e' 4.000 e non 40.000 per una ragione misurata: la
    ricerca di clique costa circa m^2 per completamento, quindi con 27.000 orbite
    (il caso di `blocchi9x3` su A(27,8,5), gruppo di ordine 3) un solo riavvio e'
    mezzo miliardo di operazioni e la funzione non ritorna piu'. E i gruppi piccoli
    non servono: tutto il vantaggio del metodo sta nell'avere POCHE orbite grandi.
    """
    from math import comb
    from search_core import clique_pesata
    migliore: list[int] = []
    nome_migliore = ""
    for nome, G in nome_gruppi(n).items():
        if comb(n, w) / len(G) > massimo_orbite:
            continue
        orbite, pesi, vicini = orbite_e_compatibilita(n, d, w, G)
        if not orbite:
            continue
        scelti = clique_pesata(pesi, vicini, riavvii=riavvii)
        parole = [x for i in scelti for x in orbite[i]]
        if len(parole) > len(migliore):
            migliore, nome_migliore = parole, nome
    return sorted(migliore), nome_migliore


def estendi(parole: list[int], tutte: np.ndarray, d: int) -> list[int]:
    """Aggiunge avidamente ogni parola compatibile con tutte quelle già dentro."""
    dentro = list(parole)
    if not dentro:
        return dentro
    scelte = np.array(dentro, dtype=np.uint64)
    while True:
        dist = np.bitwise_count(np.bitwise_xor(tutte[:, None], scelte[None, :]))
        ammesse = np.flatnonzero((dist >= d).all(axis=1))
        if len(ammesse) == 0:
            return [int(x) for x in scelte]
        # la prima ammessa, poi si ricontrolla: cosi' resta valido a ogni passo
        scelte = np.append(scelte, tutte[ammesse[0]])


def da_gruppo(n: int, d: int, w: int, obiettivo: int, *, iterazioni: int = 30_000,
              semi: int = 3, riavvii: int = 300) -> dict:
    """Cerca `obiettivo` parole partendo dal miglior codice invariante."""
    tutte = _tutte_le_parole(n, w)
    posizione = indice_parole(tutte)
    seme_parole, gruppo = miglior_invariante(n, d, w, riavvii=riavvii)
    seme_parole = estendi(seme_parole, tutte, d)
    esito = {"invariante": len(seme_parole), "gruppo": gruppo,
             "obiettivo": obiettivo}
    if len(seme_parole) >= obiettivo:
        parole = sorted(seme_parole)[:obiettivo]
        esito.update({"violazioni": 0, "parole": parole,
                      "nota": "il codice invariante bastava"})
        return esito

    base = [posizione[p] for p in seme_parole]
    rng = np.random.default_rng(0)
    migliore_violazioni = None
    migliori_parole: list[int] = []
    for s in range(semi):
        libere = np.setdiff1d(np.arange(len(tutte)), np.array(base, dtype=np.int64))
        extra = rng.choice(libere, size=obiettivo - len(base), replace=False)
        inizio = base + [int(x) for x in extra]
        parole, violazioni = prova_dimensione(n, d, w, obiettivo,
                                              iterazioni=iterazioni, seme=s,
                                              parole=tutte, inizio=inizio)
        if migliore_violazioni is None or violazioni < migliore_violazioni:
            migliore_violazioni, migliori_parole = violazioni, parole
        if violazioni == 0:
            break
    esito["violazioni"] = migliore_violazioni
    if migliore_violazioni == 0 and verifica_veloce(migliori_parole, n, d, w).ok:
        esito["parole"] = sorted(migliori_parole)
    return esito


def sali_a_gradini(n: int, d: int, w: int, obiettivo: int, *,
                   iterazioni_per_gradino: int = 4_000, riavvii: int = 300,
                   pazienza: int = 3) -> dict:
    """Dal codice invariante all'obiettivo, **una parola alla volta**.

    PERCHÉ A GRADINI, E NON IN UN SALTO
    -----------------------------------
    Misurato: partire dal codice invariante e aggiungere in un colpo le parole che
    mancano fino all'obiettivo lascia molte violazioni che la riparazione non
    smaltisce — su A(17,6,6) il salto da 85 a 113 lascia 63 violazioni. Aggiungendo
    una parola per volta, ogni riparazione parte da una configurazione **valida** e
    deve sistemare pochissimo. È la differenza fra risolvere un problema e
    risolverne ventotto insieme.

    Si sale finché si riesce; dopo `pazienza` gradini falliti di fila si smette e si
    restituisce il miglior codice valido raggiunto.
    """
    tutte = _tutte_le_parole(n, w)
    posizione = indice_parole(tutte)
    parole, gruppo = miglior_invariante(n, d, w, riavvii=riavvii)
    parole = estendi(parole, tutte, d)
    storia = {"invariante": len(parole), "gruppo": gruppo, "gradini": {}}
    rng = np.random.default_rng(0)
    falliti = 0

    while len(parole) < obiettivo and falliti < pazienza:
        traguardo = len(parole) + 1
        base = [posizione[p] for p in parole]
        libere = np.setdiff1d(np.arange(len(tutte)), np.array(base, dtype=np.int64))
        vinto = None
        for tentativo in range(pazienza):
            extra = int(rng.choice(libere))
            nuove, violazioni = prova_dimensione(
                n, d, w, traguardo, iterazioni=iterazioni_per_gradino,
                seme=traguardo * 17 + tentativo, parole=tutte,
                inizio=base + [extra])
            if violazioni == 0:
                vinto = nuove
                break
        storia["gradini"][traguardo] = "riuscito" if vinto else "fallito"
        if vinto is None:
            falliti += 1
        else:
            falliti = 0
            parole = sorted(vinto)

    valido = verifica_veloce(parole, n, d, w)
    storia.update({"dimensione": len(parole), "obiettivo": obiettivo,
                   "valido": valido.ok,
                   "parole": sorted(parole) if valido.ok else []})
    if not valido.ok:
        storia["difetti"] = valido.difetti[:3]
    return storia
