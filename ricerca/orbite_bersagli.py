"""
Il motore a orbite sulle celle che contano.

PERCHÉ, MISURATO
----------------
La ricerca locale su parole casuali (`tabu.py`) ha pareggiato 78 limiti su 119
sulle celle piccole, ma sulle 34 celle con **divario aperto** ha pareggiato 1 su
34, con residui di 69–441 violazioni. Non è vicina: è nella regione sbagliata.

La ragione è nei codici pubblicati, che avevamo già letto: i record di queste celle
sono **invarianti sotto un gruppo**. A(22,6,6) ≥ 343 è di Braun–Humpich–Laaksonen–
Östergård e usa un gruppo di automorfismi; A(24,6,12) ≥ 5558 è un gruppo di ordine
504 con 19 semi. Cercare fra 74.613 parole a caso non ha speranza; cercare fra 3391
orbite è un problema normale.

Questo script prova ogni gruppo del repertorio su ogni cella con divario aperto, e
dice quanto si arriva. È l'esperimento che decide se la strada A ha un motore o no.
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
sys.path.insert(0, str(RADICE / "ricerca"))

from cerca import cerca                 # noqa: E402
from codici import verifica             # noqa: E402
from gruppi import nome_gruppi          # noqa: E402
from spingi import bersagli             # noqa: E402

DATI = RADICE / "dati_ricerca"


def una(argomenti) -> dict:
    n, d, w, voce, riavvii = argomenti
    t0 = time.time()
    r = cerca(n, d, w, nome_gruppi(n), riavvii=riavvii, massimo_orbite=40_000)
    mio = r["migliore"]["dimensione"]
    esito = {"cella": f"A({n},{d},{w})", "pubblicato": voce["inferiore"],
             "superiore": voce["superiore"], "fonte": voce["fonte"],
             "nostro": mio, "gruppo": r["migliore"]["gruppo"],
             "candidate": comb(n, w), "secondi": round(time.time() - t0, 1),
             "per_gruppo": {k: v for k, v in r["per_gruppo"].items()}}
    if mio > voce["inferiore"]:
        g = verifica(r["migliore"]["parole"], n, d, w)
        esito["giudice_lento"] = g.ok
        if g.ok:
            esito["parole"] = sorted(r["migliore"]["parole"])
    return esito


def main() -> int:
    riavvii = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    quanti = int(sys.argv[2]) if len(sys.argv) > 2 else 34
    massimo = int(sys.argv[3]) if len(sys.argv) > 3 else 120_000
    lista = bersagli(massimo, quanti)
    print(f"{len(lista)} celle con divario aperto, motore a orbite, "
          f"{riavvii} riavvii per gruppo.\n")
    lavori = [(n, d, w, v, riavvii) for _, n, d, w, v in lista]
    esiti = []
    with Pool(processes=min(8, os.cpu_count() or 1)) as piscina:
        for e in piscina.imap_unordered(una, lavori):
            esiti.append(e)
            scarto = e["nostro"] - e["pubblicato"]
            marca = ("SUPERATO" if scarto > 0 else
                     "pareggiato" if scarto == 0 else f"{scarto:+d}")
            print(f"{marca:>11}  {e['cella']:<13} pubbl {e['pubblicato']:>5} "
                  f"nostro {e['nostro']:>5}  (sup {e['superiore']:>5})  "
                  f"gruppo {str(e['gruppo']):<14} {e['secondi']:>7.1f}s")
            sys.stdout.flush()
            (DATI / "fase3_orbite.json").write_text(json.dumps(esiti, indent=1))
    vinti = [e for e in esiti if e["nostro"] > e["pubblicato"]]
    pari = sum(1 for e in esiti if e["nostro"] == e["pubblicato"])
    print(f"\n{'=' * 70}\npareggiati {pari}/{len(esiti)}   superati {len(vinti)}")
    for e in vinti:
        print(f"  {e['cella']}: {e['nostro']} invece di {e['pubblicato']}. "
              f"Giudice lento: {e.get('giudice_lento')}. APPLICARE docs/04.")
    if not vinti:
        migliori = sorted(esiti, key=lambda e: e["pubblicato"] - e["nostro"])[:5]
        print("Nessun limite superato. Le cinque celle piu' vicine:")
        for e in migliori:
            print(f"  {e['cella']}: {e['nostro']} contro {e['pubblicato']} "
                  f"({e['nostro'] - e['pubblicato']:+d}), gruppo {e['gruppo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
