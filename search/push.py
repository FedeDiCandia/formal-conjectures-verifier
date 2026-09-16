"""
Fase 3: pareggiare e poi **superare** i bounds inferiori pubblicati.

BERSAGLI
--------
Le cells A(n,d,w) con un **divario ancora aperto** fra limit inferiore e
superiore. Su one_ cell dal value_ exact noto non c'e' niente da superare; su one_
senza limit superiore in tabella non sapremmo dire quanto spazio resta. Restano
274 cells, e le prime sono piccole: A(27,8,5) sta fra 31 e 32, A(18,6,5) fra 69 e
72, A(22,6,5) fra 132 e 136.

COME
----
Per ogni cell, two domande in fila:
  1. riusciamo a **pareggiare** il limit pubblicato? (threshold di ammissione)
  2. riusciamo a fare **+1**? (e' qui che cadrebbe un record)
Molte iterations, piu' seeds, e le cells distribuite sui core del Mac.

Un successo non e' un result_value finche' non passa (a) dal giudice slow_ di
`codes.py` e (b) dal protocollo di `docs/04` per intero -- in particolare dal
controllo che la tabella pubblicata sia ancora quella che abbiamo scaricato oggi.

Nessun successo e' un result normale, e va scritto: significa che quei bounds
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "search"))

from codes import check                            # noqa: E402
from tabu import _all_words, size_trial    # noqa: E402

DATA_DIR = ROOT / "research_data"


def targets(max_combinations: int, how_many: int) -> list[tuple]:
    bounds = json.loads((DATA_DIR / "limiti_cwc.json").read_text())
    out_of = []
    for k, v in bounds.items():
        n, d, w = (int(x) for x in k.split(","))
        if d % 2 or not v["superiore"] or v["superiore"] <= v["inferiore"]:
            continue
        c = comb(n, w)
        if c > max_combinations:
            continue
        out_of.append((c, n, d, w, v))
    # before le cells piccole con divario strettissimo: sono quelle dove un +1 e'
    # plausibile e dove la check costa meno
    out_of.sort(key=lambda b: (b[4]["superiore"] - b[4]["inferiore"], b[0]))
    return out_of[:how_many]


def one_cell(arguments) -> dict:
    n, d, w, entry, iterations, seeds = arguments
    all_of = _all_words(n, w)
    t0 = time.time()
    result = {"cell": f"A({n},{d},{w})", "pubblicato": entry["inferiore"],
             "superiore": entry["superiore"], "source_": entry["source_"],
             "candidate": comb(n, w)}
    # 1. pareggio
    even_residue = []
    even = None
    for seed in range(seeds):
        p, viol = size_trial(n, d, w, entry["inferiore"],
                                   iterations=iterations, seed=200 + seed,
                                   words=all_of)
        even_residue.append(viol)
        if viol == 0:
            even = p
            break
    result["pareggiato"] = even is not None
    result["violazioni_al_pareggio"] = min(even_residue)
    # 2. +1, only_ se abbiamo pareggiato: chi non pareggia non supera
    if even is not None:
        residue_on = []
        won = None
        for seed in range(seeds):
            p, viol = size_trial(n, d, w, entry["inferiore"] + 1,
                                       iterations=iterations, seed=300 + seed,
                                       words=all_of, start=None)
            residue_on.append(viol)
            if viol == 0:
                won = p
                break
        result["violazioni_al_piu_uno"] = min(residue_on)
        if won is not None and check(won, n, d, w).ok:
            result["passed_one"] = True
            result["words"] = sorted(won)
        else:
            result["passed_one"] = False
    else:
        result["passed_one"] = False
    result["seconds"] = round(time.time() - t0, 1)
    return result


def main() -> int:
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 30_000
    seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    how_many = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    maximum = int(sys.argv[4]) if len(sys.argv) > 4 else 120_000
    list_ = targets(maximum, how_many)
    print(f"{len(list_)} cells con divario aperto, {iterations:,} iterations "
          f"x {seeds} seeds, su {min(8, os.cpu_count() or 1)} processi.\n")
    for c, n, d, w, v in list_:
        print(f"  A({n},{d},{w}): fra {v['inferiore']} e {v['superiore']} "
              f"(divario {v['superiore'] - v['inferiore']}), "
              f"{c:,} words candidate, source_ {v['source_']}")
    print()
    jobs = [(n, d, w, v, iterations, seeds) for _, n, d, w, v in list_]
    results = []
    with Pool(processes=min(8, os.cpu_count() or 1)) as pool:
        for e in pool.imap_unordered(one_cell, jobs):
            results.append(e)
            mark = ("SUPERATO" if e["passed_one"]
                     else "pareggiato" if e["pareggiato"] else "below")
            print(f"{mark:>11}  {e['cell']:<13} pubbl {e['pubblicato']:>5} "
                  f"sup {e['superiore']:>5}  "
                  f"violations: pareggio {e['violazioni_al_pareggio']}, "
                  f"+1 {e.get('violazioni_al_piu_uno', '-')}  "
                  f"{e['seconds']:>7.1f}s")
            sys.stdout.flush()
            (DATA_DIR / "fase3_spinta.json").write_text(json.dumps(results, indent=1))
    won_ = [e for e in results if e["passed_one"]]
    even = sum(1 for e in results if e["pareggiato"])
    print(f"\n{'=' * 70}\npareggiati {even}/{len(results)}   passed_ {len(won_)}")
    for e in won_:
        print(f"  {e['cell']}: {e['pubblicato'] + 1} words invece di "
              f"{e['pubblicato']}. APPLICARE docs/04 PER INTERO.")
    if not won_:
        print("Nessun limit passed_one. E' un result e va scritto: questi bounds "
              "reggono a un attacco moderno su hardware moderno.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
