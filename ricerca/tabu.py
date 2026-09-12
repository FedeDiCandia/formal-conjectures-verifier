"""
Il secondo motore: ricerca locale diretta sulle parole.

PERCHÉ SERVE UN SECONDO MOTORE
------------------------------
Il primo motore (`cerca.py`) cerca codici **invarianti sotto un gruppo**. È
elegante e veloce, ma ha un limite di principio che si è visto subito: per
A(21,10,9) le orbite sotto Z21 hanno taglia 7 o 21, e nessuna somma di 7 e 21 fa
27, che è il limite pubblicato. Nessuna quantità di ricerca può arrivarci per
quella strada: **il record non è invariante sotto quel gruppo.**

Questo motore non assume niente. Fissa un obiettivo m (quante parole vogliamo),
parte da m parole qualunque, e minimizza il numero di coppie che violano la
distanza scambiando una parola alla volta. Se arriva a zero violazioni, abbiamo un
codice di m parole. È la tabu search «a livello di scambi» con cui sono stati
ottenuti i miglioramenti recenti nelle tabelle di Brouwer.

STRATEGIA
---------
Si parte da m = limite pubblicato e si tenta. Se riesce, si prova m+1: è lì che un
record cadrebbe. Se non riesce, si scende. Il costo della funzione obiettivo è
tenuto basso ricalcolando solo la riga della parola che cambia.
"""
from __future__ import annotations

import random
from itertools import combinations

import numpy as np


def _tutte_le_parole(n: int, w: int) -> np.ndarray:
    from math import comb
    return np.fromiter((sum(1 << i for i in c) for c in combinations(range(n), w)),
                       dtype=np.uint64, count=comb(n, w))


def _conflitti(parole: np.ndarray, scelte: np.ndarray, d: int) -> np.ndarray:
    """Per ogni parola scelta, quante delle altre scelte sono troppo vicine."""
    x = parole[scelte]
    dist = np.bitwise_count(np.bitwise_xor(x[:, None], x[None, :]))
    cattive = (dist < d)
    np.fill_diagonal(cattive, False)
    return cattive.sum(axis=1)


def prova_dimensione(n: int, d: int, w: int, m: int, *, iterazioni: int = 60_000,
                     seme: int = 0, parole: np.ndarray | None = None,
                     inizio: list[int] | None = None) -> tuple[list[int], int]:
    """Cerca un codice di esattamente m parole. Restituisce (parole, violazioni)."""
    rng = np.random.default_rng(seme)
    tutte = _tutte_le_parole(n, w) if parole is None else parole
    N = len(tutte)
    if m > N:
        return [], m * m
    scelte = (np.array(inizio, dtype=np.int64) if inizio is not None
              else rng.choice(N, size=m, replace=False))
    if len(scelte) != m:
        scelte = rng.choice(N, size=m, replace=False)

    conf = _conflitti(tutte, scelte, d)
    totale = int(conf.sum()) // 2
    migliore = totale
    tabu: dict[int, int] = {}
    for passo in range(iterazioni):
        if totale == 0:
            break
        # si sostituisce una delle parole piu' in conflitto
        peggiori = np.flatnonzero(conf == conf.max())
        posto = int(rng.choice(peggiori))
        vecchia = int(scelte[posto])
        altre = np.delete(scelte, posto)
        x = tutte[altre]
        # quante violazioni porterebbe ogni possibile sostituta
        costo = np.zeros(N, dtype=np.int32)
        blocco = 4096
        for i in range(0, N, blocco):
            fetta = tutte[i:i + blocco]
            dist = np.bitwise_count(np.bitwise_xor(fetta[:, None], x[None, :]))
            costo[i:i + blocco] = (dist < d).sum(axis=1)
        costo[altre] = 10_000                      # gia' nel codice
        for parola, fino in list(tabu.items()):
            if fino > passo:
                costo[parola] += 50
            else:
                del tabu[parola]
        minimo = costo.min()
        candidati = np.flatnonzero(costo == minimo)
        nuova = int(rng.choice(candidati))
        scelte[posto] = nuova
        tabu[vecchia] = passo + max(5, m // 4)
        conf = _conflitti(tutte, scelte, d)
        totale = int(conf.sum()) // 2
        migliore = min(migliore, totale)
    return [int(tutte[i]) for i in scelte], totale


def spingi(n: int, d: int, w: int, partenza: int, *, tetto: int = 6,
           iterazioni: int = 40_000, seme: int = 0) -> dict:
    """Parte da `partenza` parole e sale finche' riesce."""
    parole = _tutte_le_parole(n, w)
    riuscito: list[int] = []
    m = partenza
    esiti = {}
    while m <= partenza + tetto:
        trovate, violazioni = prova_dimensione(n, d, w, m, iterazioni=iterazioni,
                                               seme=seme, parole=parole)
        esiti[m] = violazioni
        if violazioni == 0:
            riuscito = trovate
            m += 1
        else:
            break
    return {"dimensione": len(riuscito), "parole": sorted(riuscito),
            "tentativi": esiti}
