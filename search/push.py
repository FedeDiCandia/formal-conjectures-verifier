"""
Fase 3: pareggiare e poi **superare** i limiti inferiori pubblicati.

BERSAGLI
--------
Le celle A(n,d,w) con un **divario ancora aperto** fra limite inferiore e
superiore. Su una cella dal valore esatto noto non c'e' niente da superare; su una
senza limite superiore in tabella non sapremmo dire quanto spazio resta. Restano
274 celle, e le prime sono piccole: A(27,8,5) sta fra 31 e 32, A(18,6,5) fra 69 e
72, A(22,6,5) fra 132 e 136.

COME
----
Per ogni cella, due domande in fila:
  1. riusciamo a **pareggiare** il limite pubblicato? (soglia di ammissione)
  2. riusciamo a fare **+1**? (e' qui che cadrebbe un record)
Molte iterazioni, piu' semi, e le celle distribuite sui core del Mac.

Un successo non e' un risultato finche' non passa (a) dal giudice lento di
`codes.py` e (b) dal protocollo di `docs/04` per intero -- in particolare dal
controllo che la tabella pubblicata sia ancora quella che abbiamo scaricato oggi.

Nessun successo e' un esito normale, e va scritto: significa che quei limiti
reggono a un attacco moderno su hardware moderno.
"""
from __future__ import annotations

import json
import os
import sys
import time
from math import comb
from multiprocessing import Pool
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "search"))

from codes import verifica                            # noqa: E402
from tabu import _tutte_le_parole, prova_dimensione    # noqa: E402

DATI = RADICE / "research_data"


def bersagli(massimo_combinazioni: int, quanti: int) -> list[tuple]:
    limiti = json.loads((DATI / "limiti_cwc.json").read_text())
    fuori = []
    for k, v in limiti.items():
        n, d, w = (int(x) for x in k.split(","))
        if d % 2 or not v["superiore"] or v["superiore"] <= v["inferiore"]:
            continue
        c = comb(n, w)
        if c > massimo_combinazioni:
            continue
        fuori.append((c, n, d, w, v))
    # prima le celle piccole con divario strettissimo: sono quelle dove un +1 e'
    # plausibile e dove la verifica costa meno
    fuori.sort(key=lambda b: (b[4]["superiore"] - b[4]["inferiore"], b[0]))
    return fuori[:quanti]


def una_cella(argomenti) -> dict:
    n, d, w, voce, iterazioni, semi = argomenti
    tutte = _tutte_le_parole(n, w)
    t0 = time.time()
    esito = {"cella": f"A({n},{d},{w})", "pubblicato": voce["inferiore"],
             "superiore": voce["superiore"], "fonte": voce["fonte"],
             "candidate": comb(n, w)}
    # 1. pareggio
    residuo_pari = []
    pari = None
    for seme in range(semi):
        p, viol = prova_dimensione(n, d, w, voce["inferiore"],
                                   iterazioni=iterazioni, seme=200 + seme,
                                   parole=tutte)
        residuo_pari.append(viol)
        if viol == 0:
            pari = p
            break
    esito["pareggiato"] = pari is not None
    esito["violazioni_al_pareggio"] = min(residuo_pari)
    # 2. +1, solo se abbiamo pareggiato: chi non pareggia non supera
    if pari is not None:
        residuo_su = []
        vinto = None
        for seme in range(semi):
            p, viol = prova_dimensione(n, d, w, voce["inferiore"] + 1,
                                       iterazioni=iterazioni, seme=300 + seme,
                                       parole=tutte, inizio=None)
            residuo_su.append(viol)
            if viol == 0:
                vinto = p
                break
        esito["violazioni_al_piu_uno"] = min(residuo_su)
        if vinto is not None and verifica(vinto, n, d, w).ok:
            esito["superato"] = True
            esito["parole"] = sorted(vinto)
        else:
            esito["superato"] = False
    else:
        esito["superato"] = False
    esito["secondi"] = round(time.time() - t0, 1)
    return esito


def main() -> int:
    iterazioni = int(sys.argv[1]) if len(sys.argv) > 1 else 30_000
    semi = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    quanti = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    massimo = int(sys.argv[4]) if len(sys.argv) > 4 else 120_000
    lista = bersagli(massimo, quanti)
    print(f"{len(lista)} celle con divario aperto, {iterazioni:,} iterazioni "
          f"x {semi} semi, su {min(8, os.cpu_count() or 1)} processi.\n")
    for c, n, d, w, v in lista:
        print(f"  A({n},{d},{w}): fra {v['inferiore']} e {v['superiore']} "
              f"(divario {v['superiore'] - v['inferiore']}), "
              f"{c:,} parole candidate, fonte {v['fonte']}")
    print()
    lavori = [(n, d, w, v, iterazioni, semi) for _, n, d, w, v in lista]
    esiti = []
    with Pool(processes=min(8, os.cpu_count() or 1)) as piscina:
        for e in piscina.imap_unordered(una_cella, lavori):
            esiti.append(e)
            marca = ("SUPERATO" if e["superato"]
                     else "pareggiato" if e["pareggiato"] else "sotto")
            print(f"{marca:>11}  {e['cella']:<13} pubbl {e['pubblicato']:>5} "
                  f"sup {e['superiore']:>5}  "
                  f"violazioni: pareggio {e['violazioni_al_pareggio']}, "
                  f"+1 {e.get('violazioni_al_piu_uno', '-')}  "
                  f"{e['secondi']:>7.1f}s")
            sys.stdout.flush()
            (DATI / "fase3_spinta.json").write_text(json.dumps(esiti, indent=1))
    vinti = [e for e in esiti if e["superato"]]
    pari = sum(1 for e in esiti if e["pareggiato"])
    print(f"\n{'=' * 70}\npareggiati {pari}/{len(esiti)}   superati {len(vinti)}")
    for e in vinti:
        print(f"  {e['cella']}: {e['pubblicato'] + 1} parole invece di "
              f"{e['pubblicato']}. APPLICARE docs/04 PER INTERO.")
    if not vinti:
        print("Nessun limite superato. E' un esito e va scritto: questi limiti "
              "reggono a un attacco moderno su hardware moderno.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
