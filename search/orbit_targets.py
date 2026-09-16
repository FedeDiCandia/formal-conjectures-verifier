"""
The orbit engine on the cells that matter.

WHY, MEASURED
----------------
The local search on random words (`tabu.py`) matched 78 bounds of 119 on the small
cells, but on the 34 cells with an **open gap** it matched 1 of 34, with residuals
of 69-441 violations. It is not close: it is in the wrong region.

The reason is in the published codes, which we had already read: the records of
these cells are **invariant under a group**. A(22,6,6) ≥ 343 is due to
Braun-Humpich-Laaksonen-Östergård and uses an automorphism group; A(24,6,12) ≥ 5558
is a group of order 504 with 19 seeds. Searching among 74,613 random words is
hopeless; searching among 3391 orbits is an ordinary problem.

This script tries every group in the repertoire on every cell with an open gap, and
says how far it gets. It is the experiment that decides whether this route has an
engine or not.
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
    ours = r["best"]["size"]
    result = {"cell": f"A({n},{d},{w})", "published": entry["lower"],
             "upper": entry["upper"], "source": entry["source"],
             "ours": ours, "group": r["best"]["group"],
             "candidate": comb(n, w), "seconds": round(time.time() - t0, 1),
             "per_group": {k: v for k, v in r["per_group"].items()}}
    if ours > entry["lower"]:
        g = check(r["best"]["words"], n, d, w)
        result["slow_judge"] = g.ok
        if g.ok:
            result["words"] = sorted(r["best"]["words"])
    return result


def main() -> int:
    restarts = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    how_many = int(sys.argv[2]) if len(sys.argv) > 2 else 34
    maximum = int(sys.argv[3]) if len(sys.argv) > 3 else 120_000
    items = targets(maximum, how_many)
    print(f"{len(items)} cells with an open gap, orbit engine, "
          f"{restarts} restarts per group.\n")
    jobs = [(n, d, w, v, restarts) for _, n, d, w, v in items]
    results = []
    with Pool(processes=min(8, os.cpu_count() or 1)) as pool:
        for e in pool.imap_unordered(one, jobs):
            results.append(e)
            discard = e["ours"] - e["published"]
            mark = ("BEATEN" if discard > 0 else
                     "matched" if discard == 0 else f"{discard:+d}")
            print(f"{mark:>11}  {e['cell']:<13} publ. {e['published']:>5} "
                  f"ours {e['ours']:>5}  (upper {e['upper']:>5})  "
                  f"group {str(e['group']):<14} {e['seconds']:>7.1f}s")
            sys.stdout.flush()
            (DATA_DIR / "phase3_orbits.json").write_text(json.dumps(results, indent=1))
    won = [e for e in results if e["ours"] > e["published"]]
    even = sum(1 for e in results if e["ours"] == e["published"])
    print(f"\n{'=' * 70}\nmatched {even}/{len(results)}   beaten {len(won)}")
    for e in won:
        print(f"  {e['cell']}: {e['ours']} instead of {e['published']}. "
              f"Slow judge: {e.get('slow_judge')}. APPLY docs/04.")
    if not won:
        best_list = sorted(results, key=lambda e: e["published"] - e["ours"])[:5]
        print("No bound beaten. The five closest cells:")
        for e in best_list:
            print(f"  {e['cell']}: {e['ours']} against {e['published']} "
                  f"({e['ours'] - e['published']:+d}), group {e['group']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
