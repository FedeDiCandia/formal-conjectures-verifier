"""
Il grafo residuo di un pacchetto di 32 blocchi su 27 punti: quante forme può avere?

PERCHÉ
------
Un pacchetto copre coppie; quelle non coperte formano il **grafo residuo** L. Con 32
blocchi si coprono 320 delle 351 coppie, quindi L ha **31 lati**. Il grado di un punto
x in L è 26 − 4·deg(x), perché ogni blocco per x copre 4 coppie con x. Con deg ≤ 6 e
deficienza totale 2 (docs/11) restano due casi soltanto:

  caso A  due punti di grado 5 → in L hanno grado 6; tutti gli altri grado 2
  caso B  un punto di grado 4  → in L ha grado 10; tutti gli altri grado 2

Un grafo in cui quasi tutti i vertici hanno grado 2 è fatto di cicli e di cammini
appesi ai pochi vertici speciali: si descrive con poche partizioni di interi. Quindi
le forme possibili di L, a meno di isomorfismo, si possono **elencare tutte**.

Per ciascuna forma il problema cambia natura: non più «scegli al più 32 blocchi che
non si sovrappongano» (packing, simmetria enorme), ma «**decomponi K27 − L in 32 K5**»
(copertura esatta: ogni coppia fuori da L coperta esattamente una volta), con la
simmetria ridotta al gruppo di automorfismi di L. È il modo classico in cui la teoria
dei disegni decide questi casi.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent


def partizioni(n: int, minimo: int, massimo: int | None = None):
    """Partizioni di n in parti >= minimo, in ordine non crescente."""
    if n == 0:
        yield ()
        return
    massimo = n if massimo is None else min(massimo, n)
    for p in range(massimo, minimo - 1, -1):
        for resto in partizioni(n - p, minimo, p):
            yield (p,) + resto


def multinsiemi(k: int, minimo: int, totale_max: int):
    """Multinsiemi di k parti >= minimo con somma <= totale_max (non crescenti)."""
    def ric(k, massimo, somma_max):
        if k == 0:
            yield ()
            return
        for p in range(min(massimo, somma_max - minimo * (k - 1)), minimo - 1, -1):
            for resto in ric(k - 1, p, somma_max - p):
                yield (p,) + resto
    yield from ric(k, totale_max, totale_max)


def caso_B():
    """Un vertice v di grado 10: cinque petali (cammini da v a v, >= 2 vertici interni)
    più cicli (>= 3) sui 26 vertici restanti."""
    fuori = []
    for petali in multinsiemi(5, 2, 26):
        resto = 26 - sum(petali)
        for cicli in partizioni(resto, 3):
            fuori.append({"caso": "B", "petali": petali, "cicli": cicli})
    return fuori


def caso_A():
    """Due vertici u, w di grado 6. Componenti: petali a u, petali a w (>= 2 interni),
    connettori u–w (>= 1 interno), eventuale lato uw, cicli (>= 3). Grado di u:
    2·petali_u + connettori + lato = 6, e lo stesso per w, quindi petali_u = petali_w."""
    fuori = []
    for lato in (0, 1):
        for conn in range(0, 7):
            if (6 - conn - lato) < 0 or (6 - conn - lato) % 2:
                continue
            p = (6 - conn - lato) // 2
            for K in multinsiemi(conn, 1, 25):
                for Pu in multinsiemi(p, 2, 25 - sum(K)):
                    for Pw in multinsiemi(p, 2, 25 - sum(K) - sum(Pu)):
                        if Pw > Pu:            # u e w sono scambiabili: una sola copia
                            continue
                        resto = 25 - sum(K) - sum(Pu) - sum(Pw)
                        for cicli in partizioni(resto, 3):
                            fuori.append({"caso": "A", "lato_uw": lato, "connettori": K,
                                          "petali_u": Pu, "petali_w": Pw, "cicli": cicli})
    return fuori


def costruisci(forma) -> list[tuple[int, int]]:
    """Un grafo concreto sui vertici 0..26 con quella forma."""
    lati = []
    prossimo = [0]

    def nuovo():
        prossimo[0] += 1
        return prossimo[0] - 1

    def cammino(a, b, interni):
        pts = [nuovo() for _ in range(interni)]
        catena = [a] + pts + [b]
        lati.extend(zip(catena, catena[1:]))

    def ciclo(n):
        pts = [nuovo() for _ in range(n)]
        lati.extend(zip(pts, pts[1:] + pts[:1]))

    if forma["caso"] == "B":
        v = nuovo()
        for s in forma["petali"]:
            cammino(v, v, s)
    else:
        u, w = nuovo(), nuovo()
        if forma["lato_uw"]:
            lati.append((u, w))
        for s in forma["connettori"]:
            cammino(u, w, s)
        for s in forma["petali_u"]:
            cammino(u, u, s)
        for s in forma["petali_w"]:
            cammino(w, w, s)
    for c in forma["cicli"]:
        ciclo(c)
    assert prossimo[0] == 27, (forma, prossimo[0])
    return lati


def main() -> int:
    import networkx as nx
    A, B = caso_A(), caso_B()
    print(f"forme possibili del grafo residuo: caso A {len(A)}, caso B {len(B)}, "
          f"totale {len(A) + len(B)}")
    # controlli: ogni forma costruita ha 27 vertici, 31 lati, grafo semplice, gradi giusti
    for forma in A + B:
        G = nx.Graph()
        G.add_nodes_from(range(27))
        lati = costruisci(forma)
        G.add_edges_from(lati)
        assert len(lati) == G.number_of_edges() == 31, forma      # niente lati doppi
        gradi = sorted((d for _, d in G.degree()), reverse=True)
        atteso = [6, 6] + [2] * 25 if forma["caso"] == "A" else [10] + [2] * 26
        assert gradi == atteso, (forma, gradi)
    print("tutte le forme: 27 vertici, 31 lati, grafo semplice, sequenza dei gradi corretta")
    # controllo di non isomorfismo su un campione (l'elenco non deve contare due volte)
    rng = random.Random(1)
    campione = rng.sample(A, min(120, len(A))) + rng.sample(B, min(60, len(B)))
    grafi = []
    for f in campione:
        G = nx.Graph(); G.add_nodes_from(range(27)); G.add_edges_from(costruisci(f))
        grafi.append(G)
    doppi = sum(1 for i in range(len(grafi)) for j in range(i + 1, len(grafi))
                if nx.faster_could_be_isomorphic(grafi[i], grafi[j])
                and nx.is_isomorphic(grafi[i], grafi[j]))
    print(f"campione di {len(grafi)} forme: coppie isomorfe fra loro = {doppi}")
    (RADICE / "dati_ricerca" / "residui_d27.json").write_text(
        json.dumps({"A": len(A), "B": len(B)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
