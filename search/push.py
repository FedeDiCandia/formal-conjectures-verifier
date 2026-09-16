"""
Phase 3: match and then **beat** the published lower bounds.

TARGETS
-------
The A(n,d,w) cells with a **gap still open** between the lower and upper bounds. On
a cell whose exact value is known there is nothing to beat; on one with no upper
bound in the table we could not say how much room is left. That leaves
274 cells, and the first are small: A(27,8,5) lies between 31 and 32, A(18,6,5) at
72, A(22,6,5) between 132 and 136.

HOW
----
For each cell, two questions in a row:
  1. can we **match** the published bound? (the admission threshold)
  2. can we do **+1**? (this is where a record would fall)
Many iterations, several seeds, and the cells spread over the Mac's cores.

A success is not a result until it passes (a) the slow judge in `codes.py` and (b)
the whole protocol in `docs/04-finding-protocol.md` -- in particular the check that
the published table is still the one downloaded today.

No success is an ordinary outcome, and it should be written down: it means those
bounds hold against a modern attack on modern hardware.
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
    bounds = json.loads((DATA_DIR / "bounds_cwc.json").read_text())
    outside = []
    for k, v in bounds.items():
        n, d, w = (int(x) for x in k.split(","))
        if d % 2 or not v["upper"] or v["upper"] <= v["lower"]:
            continue
        c = comb(n, w)
        if c > max_combinations:
            continue
        outside.append((c, n, d, w, v))
    # first the small cells with the narrowest gap: those are where a +1 is
    # plausible and where the verification costs least
    outside.sort(key=lambda b: (b[4]["upper"] - b[4]["lower"], b[0]))
    return outside[:how_many]


def single_cell(arguments) -> dict:
    n, d, w, entry, iterations, seeds = arguments
    all_items = _all_words(n, w)
    t0 = time.time()
    result = {"cell": f"A({n},{d},{w})", "published": entry["lower"],
             "upper": entry["upper"], "source": entry["source"],
             "candidate": comb(n, w)}
    # 1. match
    even_residue = []
    even = None
    for seed in range(seeds):
        p, viol = size_trial(n, d, w, entry["lower"],
                                   iterations=iterations, seed=200 + seed,
                                   words=all_items)
        even_residue.append(viol)
        if viol == 0:
            even = p
            break
    result["matched"] = even is not None
    result["violations_at_match"] = min(even_residue)
    # 2. +1, only if we matched: whoever does not match does not beat it
    if even is not None:
        residue_on = []
        won = None
        for seed in range(seeds):
            p, viol = size_trial(n, d, w, entry["lower"] + 1,
                                       iterations=iterations, seed=300 + seed,
                                       words=all_items, start=None)
            residue_on.append(viol)
            if viol == 0:
                won = p
                break
        result["violations_at_plus_one"] = min(residue_on)
        if won is not None and check(won, n, d, w).ok:
            result["exceeded"] = True
            result["words"] = sorted(won)
        else:
            result["exceeded"] = False
    else:
        result["exceeded"] = False
    result["seconds"] = round(time.time() - t0, 1)
    return result


def main() -> int:
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 30_000
    seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    how_many = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    maximum = int(sys.argv[4]) if len(sys.argv) > 4 else 120_000
    items = targets(maximum, how_many)
    print(f"{len(items)} cells with an open gap, {iterations:,} iterations "
          f"x {seeds} seeds, su {min(8, os.cpu_count() or 1)} processi.\n")
    for c, n, d, w, v in items:
        print(f"  A({n},{d},{w}): between {v['lower']} and {v['upper']} "
              f"(gap {v['upper'] - v['lower']}), "
              f"{c:,} words candidate, source {v['source']}")
    print()
    jobs = [(n, d, w, v, iterations, seeds) for _, n, d, w, v in items]
    results = []
    with Pool(processes=min(8, os.cpu_count() or 1)) as pool:
        for e in pool.imap_unordered(single_cell, jobs):
            results.append(e)
            mark = ("BEATEN" if e["exceeded"]
                     else "matched" if e["matched"] else "below")
            print(f"{mark:>11}  {e['cell']:<13} publ. {e['published']:>5} "
                  f"upper {e['upper']:>5}  "
                  f"violations: at match {e['violations_at_match']}, "
                  f"at +1 {e.get('violations_at_plus_one', '-')}  "
                  f"{e['seconds']:>7.1f}s")
            sys.stdout.flush()
            (DATA_DIR / "phase3_push.json").write_text(json.dumps(results, indent=1))
    won = [e for e in results if e["exceeded"]]
    even = sum(1 for e in results if e["matched"])
    print(f"\n{'=' * 70}\nmatched {even}/{len(results)}   beaten {len(won)}")
    for e in won:
        print(f"  {e['cell']}: {e['published'] + 1} words instead of "
              f"{e['published']}. APPLY docs/04-finding-protocol.md IN FULL.")
    if not won:
        print("No bound beaten. That is a result and should be written down: these "
              "bounds hold against a modern attack on modern hardware.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
