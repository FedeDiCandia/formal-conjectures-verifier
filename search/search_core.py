"""
La ricerca: un codice invariante sotto un gruppo, di dimensione massima.

IL PROBLEMA, RIDOTTO
--------------------
Fissati n, d, w e un gruppo G di permutazioni delle n posizioni:

  1. le parole di peso w si spezzano in orbite sotto G;
  2. un'orbita è **utilizzabile** se le sue parole sono a due a due a distanza
     ≥ d (altrimenti il codice non può contenerla tutta);
  3. due orbite utilizzabili sono **compatibili** se ogni parola dell'una dista
     ≥ d da ogni parola dell'altra;
  4. il più grande codice G-invariante è l'insieme di orbite a due a due
     compatibili di peso totale massimo: una **clique massima pesata**.

Il passo 4 è NP-difficile in generale, ma qui i grafi sono piccoli perché il
gruppo ha già fatto il lavoro. Si usa un greedy con riavvii casuali più una
ricerca locale (togli k orbite, riempi con le migliori ammesse): è lo stesso tipo
di euristica con cui sono stati trovati i record in tabella, e su un Mac basta.
"""
from __future__ import annotations

import random
from itertools import combinations

from math import comb

from codes import verifica_veloce


# ---------------------------------------------------------------------------
# DUE SEMPLIFICAZIONI ESATTE, non euristiche, che rendono il calcolo possibile
#
# 1. Un'orbita e' utilizzabile se e solo se **un suo rappresentante** dista >= d
#    da tutte le altre parole dell'orbita. Non serve controllare tutte le coppie:
#    se a' = g(a), allora dist(g(a), b) = dist(a, g^-1(b)) e g^-1(b) sta ancora
#    nell'orbita, quindi le coppie che coinvolgono a' sono le stesse che
#    coinvolgono a, riordinate.
#
# 2. Per lo stesso motivo, due orbite sono compatibili se e solo se **un
#    rappresentante della prima** dista >= d da tutte le parole della seconda.
#
# Insieme fanno risparmiare un fattore pari alla taglia dell'orbita -- da decine a
# centinaia. Il resto lo fa numpy: un solo XOR fra il rappresentante e l'intero
# vettore delle parole, e `bitwise_count` per i pesi.


def _tabella_orbite(n: int, w: int, gruppo):
    """Tutte le parole di peso w, l'orbita di ognuna, e un rappresentante."""
    import numpy as np
    parole = np.fromiter((sum(1 << i for i in c)
                          for c in combinations(range(n), w)),
                         dtype=np.uint64, count=comb(n, w))
    ordine = {int(p): k for k, p in enumerate(parole)}
    orbita_di = np.full(len(parole), -1, dtype=np.int64)
    rappresentanti: list[int] = []
    membri: list[list[int]] = []
    for k, p in enumerate(parole):
        if orbita_di[k] >= 0:
            continue
        o = len(rappresentanti)
        supporto = [i for i in range(n) if int(p) >> i & 1]
        gruppo_orbita = set()
        for perm in gruppo:
            f = 0
            for i in supporto:
                f |= 1 << perm[i]
            gruppo_orbita.add(f)
        indici = [ordine[x] for x in gruppo_orbita]
        orbita_di[indici] = o
        rappresentanti.append(int(p))
        membri.append(sorted(indici))
    return parole, orbita_di, rappresentanti, membri


def orbite_e_compatibilita(n: int, d: int, w: int, gruppo):
    """Le orbite utilizzabili, i loro pesi e il grafo di compatibilita."""
    import numpy as np
    parole, orbita_di, rapp, membri = _tabella_orbite(n, w, gruppo)
    # 1. utilizzabilita: il rappresentante contro i suoi compagni di orbita
    buone = []
    for o, r in enumerate(rapp):
        idx = np.array(membri[o], dtype=np.int64)
        dist = np.bitwise_count(np.bitwise_xor(parole[idx], np.uint64(r)))
        if bool(np.all((dist == 0) | (dist >= d))):
            buone.append(o)
    if not buone:
        return [], [], []
    nuovo_id = {o: i for i, o in enumerate(buone)}
    orbite = [tuple(sorted(int(parole[i]) for i in membri[o])) for o in buone]
    pesi = [len(o) for o in orbite]

    # 2. compatibilita: il rappresentante contro tutte le parole, in un colpo
    vicini = [set(range(len(buone))) - {i} for i in range(len(buone))]
    for i, o in enumerate(buone):
        dist = np.bitwise_count(np.bitwise_xor(parole, np.uint64(rapp[o])))
        colpevoli = orbita_di[(dist > 0) & (dist < d)]
        for c in set(int(x) for x in colpevoli):
            j = nuovo_id.get(c)
            if j is not None and j != i:
                vicini[i].discard(j)
                vicini[j].discard(i)
    return orbite, pesi, vicini


def orbite_utilizzabili(n: int, d: int, w: int, gruppo) -> list[tuple[int, ...]]:
    """Le orbite di peso w che al loro interno rispettano la distanza d."""
    t = w - d // 2
    visti = set()
    fuori = []
    for supporto in combinations(range(n), w):
        parola = sum(1 << i for i in supporto)
        if parola in visti:
            continue
        orbita = set()
        for p in gruppo:
            f = 0
            for i in supporto:
                f |= 1 << p[i]
            orbita.add(f)
        visti |= orbita
        orbita = tuple(sorted(orbita))
        buona = all((a ^ b).bit_count() >= d for a, b in combinations(orbita, 2))
        if buona:
            fuori.append(orbita)
    return fuori


def compatibilita(orbite: list[tuple[int, ...]], d: int) -> list[set[int]]:
    """Per ogni orbita, l'insieme delle orbite con cui può convivere."""
    m = len(orbite)
    vicini: list[set[int]] = [set() for _ in range(m)]
    for i in range(m):
        for j in range(i + 1, m):
            if all((a ^ b).bit_count() >= d for a in orbite[i] for b in orbite[j]):
                vicini[i].add(j)
                vicini[j].add(i)
    return vicini


def clique_pesata(pesi: list[int], vicini: list[set[int]], *,
                  riavvii: int = 200, seme: int = 0,
                  passi_locali: int = 60) -> list[int]:
    """Greedy con riavvii casuali e ricerca locale. Restituisce gli indici scelti."""
    rng = random.Random(seme)
    m = len(pesi)
    migliore: list[int] = []
    valore_migliore = 0

    def completa(scelti: list[int], ammessi: set[int]) -> tuple[list[int], int]:
        scelti = list(scelti)
        ammessi = set(ammessi)
        while ammessi:
            # preferisci il peso alto, a parità chi lascia più opzioni
            candidati = sorted(ammessi, key=lambda i: (-pesi[i], -len(vicini[i] & ammessi)))
            testa = candidati[:3]
            scelto = rng.choice(testa) if len(testa) > 1 and rng.random() < 0.3 else candidati[0]
            scelti.append(scelto)
            ammessi &= vicini[scelto]
        return scelti, sum(pesi[i] for i in scelti)

    for _ in range(riavvii):
        scelti, valore = completa([], set(range(m)))
        for _ in range(passi_locali):
            if len(scelti) <= 1:
                break
            k = min(len(scelti), rng.randint(1, 3))
            tenuti = rng.sample(scelti, len(scelti) - k)
            ammessi = set(range(m))
            for i in tenuti:
                ammessi &= vicini[i]
            ammessi -= set(tenuti)
            nuovi, nuovo_valore = completa(tenuti, ammessi)
            if nuovo_valore >= valore:
                scelti, valore = nuovi, nuovo_valore
        if valore > valore_migliore:
            migliore, valore_migliore = scelti, valore
    return migliore


def cerca(n: int, d: int, w: int, gruppi: dict, *, riavvii: int = 200,
          seme: int = 0, massimo_orbite: int = 8_000) -> dict:
    """Prova ogni gruppo e restituisce il migliore codice trovato.

    I gruppi troppo piccoli si scartano: con |G| piccolo le orbite sono tante
    quante le parole, il grafo di compatibilita' diventa enorme e il metodo perde
    il suo vantaggio. Il caso che ha fatto sbattere il naso: `blocchi7x3` su n=21
    ha ordine 3, quindi 98 mila orbite e 29 miliardi di confronti.
    """
    from math import comb
    esiti = {}
    migliore = {"parole": [], "dimensione": 0, "gruppo": None}
    for nome, G in groups.items():
        if comb(n, w) / len(G) > massimo_orbite:
            esiti[nome] = {"saltato": f"circa {comb(n, w) // len(G)} orbite"}
            continue
        orb, pesi, vic = orbite_e_compatibilita(n, d, w, G)
        if not orb:
            esiti[nome] = {"orbite": 0, "dimensione": 0}
            continue
        scelti = clique_pesata(pesi, vic, riavvii=riavvii, seme=seme)
        parole = [x for i in scelti for x in orb[i]]
        v = verifica_veloce(parole, n, d, w)
        assert v.ok, f"la ricerca ha prodotto un codice non valido: {v.difetti[:2]}"
        esiti[nome] = {"orbite": len(orb), "ordine": len(G),
                       "dimensione": len(parole)}
        if len(parole) > migliore["dimensione"]:
            migliore = {"parole": sorted(parole), "dimensione": len(parole),
                        "gruppo": nome}
    return {"migliore": migliore, "per_gruppo": esiti}
