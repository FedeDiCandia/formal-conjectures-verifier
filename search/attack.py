"""
L'attacco vero: seed invariante below un group, poi salita a steps_.

I TRE MOTORI, E PERCHÉ SERVONO TUTTI E TRE (misurato l'11-12 settembre 2026)
---------------------------------------------------------------------------
  * **orbits** — pareggia subito dove il record è invariante below un group
    (A(19,6,5) = 76 in 0,8 s) e si blocca dove non lo è: su A(17,6,6) arriva a 85
    against 113, perché 113 non è total_sum di sizes di orbits below Z17.
  * **ricerca local_ da words casuali** — 1 cell pareggiata su 34, residui di
    69–441 violations. Lo spazio è troppo grande per partire dal nulla.
  * **conflitti precalcolati** — la matrice dei conflitti si costruisce one_ volta, e
    one_ mossa costa one_ total_sum di N interi invece di N·m conteggi di bit. Da migliaia
    di moves a centinaia di migliaia.

Questo script li mette in fila come li mette in fila la letteratura: **il group dà
la struttura, la salita a steps_ la estende one_ word alla volta.** Ogni gradino
parte da un code valid, quindi la riparazione deve sistemare poco.

Un successo passa dal giudice slow_ di `codes.py` e poi da `docs/04` per intero.
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

from codes import check                                  # noqa: E402
from hybrid import extend, best_invariant                # noqa: E402
from push import targets                                   # noqa: E402
from tabu import _all_words                             # noqa: E402
from fast import MEMORY_CAP_BYTES, climb                    # noqa: E402

DATA_DIR = ROOT / "research_data"


def one_(arguments) -> dict:
    n, d, w, entry, moves, restarts = arguments
    t0 = time.time()
    result = {"cell": f"A({n},{d},{w})", "pubblicato": entry["inferiore"],
             "superiore": entry["superiore"], "source_": entry["source_"],
             "candidate": comb(n, w)}
    N = comb(n, w)
    if N * ((N + 7) // 8) > MEMORY_CAP_BYTES:
        result["saltata"] = f"matrice da {N * ((N + 7) // 8) / 1e9:.1f} GB"
        return result
    try:
        seed, group = best_invariant(n, d, w, restarts=restarts)
        all_of = _all_words(n, w)
        seed = extend(seed, all_of, d)
        result.update({"invariante": len(seed), "group": group})
        r = climb(n, d, w, seed, entry["inferiore"] + 1,
                 moves_per_step=moves, seed=1, attempts=3)
        result.update({"reached": r["size"], "valid": r["valid"],
                      "gradini_riusciti": sum(1 for v in r["steps_"].values()
                                              if v == "succeeded")})
        if r["size"] > entry["inferiore"] and r["valid"]:
            g = check(r["words"], n, d, w)
            result["giudice_lento"] = g.ok
            if g.ok:
                result["words"] = r["words"]
    except MemoryError as e:
        result["saltata"] = str(e)
    result["seconds"] = round(time.time() - t0, 1)
    return result


def main() -> int:
    moves = int(sys.argv[1]) if len(sys.argv) > 1 else 150_000
    how_many = int(sys.argv[2]) if len(sys.argv) > 2 else 34
    maximum = int(sys.argv[3]) if len(sys.argv) > 3 else 120_000
    restarts = int(sys.argv[4]) if len(sys.argv) > 4 else 250
    list_ = targets(maximum, how_many)
    print(f"{len(list_)} cells con divario aperto. Seme invariante + salita a "
          f"steps_, {moves:,} moves per gradino.\n")
    jobs = [(n, d, w, v, moves, restarts) for _, n, d, w, v in list_]
    results = []
    with Pool(processes=min(6, os.cpu_count() or 1)) as pool:
        for e in pool.imap_unordered(one_, jobs):
            results.append(e)
            if "saltata" in e:
                print(f"    saltata  {e['cell']:<13} {e['saltata']}")
            else:
                discard = e["reached"] - e["pubblicato"]
                mark = ("SUPERATO" if discard > 0 else
                         "pareggiato" if discard == 0 else f"{discard:+d}")
                print(f"{mark:>11}  {e['cell']:<13} pubbl {e['pubblicato']:>5} "
                      f"invariante {e['invariante']:>5} ({e['group']:<13}) "
                      f"-> {e['reached']:>5}  "
                      f"+{e['gradini_riusciti']} steps_  {e['seconds']:>7.1f}s")
            sys.stdout.flush()
            (DATA_DIR / "fase3_attacco.json").write_text(json.dumps(results, indent=1))
    useful = [e for e in results if "saltata" not in e]
    won_ = [e for e in useful if e["reached"] > e["pubblicato"]]
    even = sum(1 for e in useful if e["reached"] == e["pubblicato"])
    print(f"\n{'=' * 74}\n{len(useful)} cells tentate: "
          f"pareggiate {even}, superate {len(won_)}")
    for e in won_:
        print(f"  {e['cell']}: {e['reached']} invece di {e['pubblicato']}. "
              f"Giudice slow_: {e.get('giudice_lento')}. APPLICARE docs/04.")
    if useful and not won_:
        neighbours = sorted(useful, key=lambda e: e["pubblicato"] - e["reached"])[:6]
        print("Le cells piu' neighbours:")
        for e in neighbours:
            print(f"  {e['cell']}: {e['reached']} against {e['pubblicato']} "
                  f"({e['reached'] - e['pubblicato']:+d}), "
                  f"invariante {e['invariante']} below {e['group']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
