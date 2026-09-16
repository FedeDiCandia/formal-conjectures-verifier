"""
The real attack: an invariant seed under a group, then a climb in steps.

THE THREE ENGINES, AND WHY ALL THREE ARE NEEDED (measured 11-12 September 2026)
---------------------------------------------------------------------------
  * **orbits** — matches at once where the record is invariant under a group
    (A(19,6,5) = 76 in 0.8 s) and stalls where it is not: on A(17,6,6) it reaches 85
    against 113, because 113 is not a sum of orbit sizes under Z17.
  * **ricerca local da words casuali** — 1 cell pareggiata su 34, residui di
    69-441 violations. The space is too large to start from nothing.
  * **precomputed conflicts** — the conflict matrix is built once, and
    one mossa costa one total_sum di N interi invece di N·m conteggi di bit. Da migliaia
    di moves a centinaia di migliaia.

This script lines them up as the literature does: **the group gives the structure,
and the climb in steps extends it one word at a time.** Every step starts from a
valid code, so the repair has little to fix.

A success goes through the slow judge in `codes.py` and then through the whole protocol in `docs/04-finding-protocol.md`.
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


def one(arguments) -> dict:
    n, d, w, entry, moves, restarts = arguments
    t0 = time.time()
    result = {"cell": f"A({n},{d},{w})", "published": entry["lower"],
             "upper": entry["upper"], "source": entry["source"],
             "candidate": comb(n, w)}
    N = comb(n, w)
    if N * ((N + 7) // 8) > MEMORY_CAP_BYTES:
        result["saltata"] = f"matrice da {N * ((N + 7) // 8) / 1e9:.1f} GB"
        return result
    try:
        seed, group = best_invariant(n, d, w, restarts=restarts)
        all_items = _all_words(n, w)
        seed = extend(seed, all_items, d)
        result.update({"invariante": len(seed), "group": group})
        r = climb(n, d, w, seed, entry["lower"] + 1,
                 moves_per_step=moves, seed=1, attempts=3)
        result.update({"reached": r["size"], "valid": r["valid"],
                      "gradini_riusciti": sum(1 for v in r["steps"].values()
                                              if v == "succeeded")})
        if r["size"] > entry["lower"] and r["valid"]:
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
    items = targets(maximum, how_many)
    print(f"{len(items)} cells with an open gap. Invariant seed + climb in "
          f"steps, {moves:,} moves per step.\n")
    jobs = [(n, d, w, v, moves, restarts) for _, n, d, w, v in items]
    results = []
    with Pool(processes=min(6, os.cpu_count() or 1)) as pool:
        for e in pool.imap_unordered(one, jobs):
            results.append(e)
            if "saltata" in e:
                print(f"    saltata  {e['cell']:<13} {e['saltata']}")
            else:
                discard = e["reached"] - e["published"]
                mark = ("SUPERATO" if discard > 0 else
                         "matched" if discard == 0 else f"{discard:+d}")
                print(f"{mark:>11}  {e['cell']:<13} pubbl {e['published']:>5} "
                      f"invariante {e['invariante']:>5} ({e['group']:<13}) "
                      f"-> {e['reached']:>5}  "
                      f"+{e['gradini_riusciti']} steps  {e['seconds']:>7.1f}s")
            sys.stdout.flush()
            (DATA_DIR / "fase3_attacco.json").write_text(json.dumps(results, indent=1))
    useful = [e for e in results if "saltata" not in e]
    won = [e for e in useful if e["reached"] > e["published"]]
    even = sum(1 for e in useful if e["reached"] == e["published"])
    print(f"\n{'=' * 74}\n{len(useful)} cells tentate: "
          f"pareggiate {even}, superate {len(won)}")
    for e in won:
        print(f"  {e['cell']}: {e['reached']} invece di {e['published']}. "
              f"Giudice slow: {e.get('giudice_lento')}. APPLICARE docs/04.")
    if useful and not won:
        neighbours = sorted(useful, key=lambda e: e["published"] - e["reached"])[:6]
        print("The closest cells:")
        for e in neighbours:
            print(f"  {e['cell']}: {e['reached']} against {e['published']} "
                  f"({e['reached'] - e['published']:+d}), "
                  f"invariante {e['invariante']} below {e['group']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
