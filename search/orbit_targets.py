"""
Il motore a orbits sulle cells che contano.

PERCHÉ, MISURATO
----------------
La ricerca local su words casuali (`tabu.py`) ha pareggiato 78 bounds su 119
sulle cells piccole, ma sulle 34 cells con **divario aperto** ha pareggiato 1 su
34, con residui di 69–441 violations. Non è vicina: è nella regione sbagliata.

La ragione è nei codici pubblicati, che avevamo già letto: i record di queste cells
sono **invarianti below un group**. A(22,6,6) ≥ 343 è di Braun–Humpich–Laaksonen–
Östergård e usa un group di automorfismi; A(24,6,12) ≥ 5558 è un group di order
504 con 19 seeds. Cercare fra 74.613 words a caso non ha speranza; cercare fra 3391
orbits è un problem normale.

Questo script trial ogni group del repertorio su ogni cell con divario aperto, e
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "search"))

from search_core import search_for                 # noqa: E402
from codes import check             # noqa: E402
from groups import group_names          # noqa: E402
from push import targets             # noqa: E402

DATA_DIR = ROOT / "research_data"


def one(arguments) -> dict:
    n, d, w, entry, restarts = arguments
    t0 = time.time()
    r = search_for(n, d, w, group_names(n), restarts=restarts, max_orbits=40_000)
    mio = r["best"]["size"]
    result = {"cell": f"A({n},{d},{w})", "pubblicato": entry["inferiore"],
             "superiore": entry["superiore"], "source": entry["source"],
             "nostro": mio, "group": r["best"]["group"],
             "candidate": comb(n, w), "seconds": round(time.time() - t0, 1),
             "per_gruppo": {k: v for k, v in r["per_gruppo"].items()}}
    if mio > entry["inferiore"]:
        g = check(r["best"]["words"], n, d, w)
        result["giudice_lento"] = g.ok
        if g.ok:
            result["words"] = sorted(r["best"]["words"])
    return result


def main() -> int:
    restarts = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    how_many = int(sys.argv[2]) if len(sys.argv) > 2 else 34
    maximum = int(sys.argv[3]) if len(sys.argv) > 3 else 120_000
    items = targets(maximum, how_many)
    print(f"{len(items)} cells con divario aperto, motore a orbits, "
          f"{restarts} restarts per group.\n")
    jobs = [(n, d, w, v, restarts) for _, n, d, w, v in items]
    results = []
    with Pool(processes=min(8, os.cpu_count() or 1)) as pool:
        for e in pool.imap_unordered(one, jobs):
            results.append(e)
            discard = e["nostro"] - e["pubblicato"]
            mark = ("SUPERATO" if discard > 0 else
                     "pareggiato" if discard == 0 else f"{discard:+d}")
            print(f"{mark:>11}  {e['cell']:<13} pubbl {e['pubblicato']:>5} "
                  f"nostro {e['nostro']:>5}  (sup {e['superiore']:>5})  "
                  f"group {str(e['group']):<14} {e['seconds']:>7.1f}s")
            sys.stdout.flush()
            (DATA_DIR / "fase3_orbite.json").write_text(json.dumps(results, indent=1))
    won = [e for e in results if e["nostro"] > e["pubblicato"]]
    even = sum(1 for e in results if e["nostro"] == e["pubblicato"])
    print(f"\n{'=' * 70}\npareggiati {even}/{len(results)}   passed {len(won)}")
    for e in won:
        print(f"  {e['cell']}: {e['nostro']} invece di {e['pubblicato']}. "
              f"Giudice slow: {e.get('giudice_lento')}. APPLICARE docs/04.")
    if not won:
        best_list = sorted(results, key=lambda e: e["pubblicato"] - e["nostro"])[:5]
        print("Nessun limit exceeded. Le cinque cells piu' neighbours:")
        for e in best_list:
            print(f"  {e['cell']}: {e['nostro']} against {e['pubblicato']} "
                  f"({e['nostro'] - e['pubblicato']:+d}), group {e['group']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
