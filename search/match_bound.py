"""
Our search against the published bounds.

Three questions, in order, and the third counts only if the first two are in place.

  1. **Does the engine find the known optima?** On the cells where A(n,d,w) is an
     exact value, we have to reach it. If we do not, the engine is weak and
     qualunque result above e' rumore.
  2. **Does the engine NOT exceed the known optima?** If it claims to have found
     more than the exact value, that is a defect of ours. It is the falsification
     test: without it a "record" means nothing.
  3. **Does it match the open published bounds?** That is the admission threshold
     for the next phase: whoever does not match does not beat.
"""
from __future__ import annotations

import json
import sys
import time
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "search"))

from codes import check, fast_check   # noqa: E402
from tabu import _all_words, size_trial   # noqa: E402

DATA_DIR = ROOT / "research_data"


def main() -> int:
    bounds = json.loads((DATA_DIR / "limiti_cwc.json").read_text())
    word_cap = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    tetto_comb = int(sys.argv[2]) if len(sys.argv) > 2 else 80_000
    iterations = int(sys.argv[3]) if len(sys.argv) > 3 else 3_000

    exact_ones, open_list = [], []
    for k, v in bounds.items():
        n, d, w = (int(x) for x in k.split(","))
        if d % 2 or v["lower"] > word_cap or comb(n, w) > tetto_comb:
            continue
        (exact_ones if v["exact"] else open_list).append((k, v))
    exact_ones.sort(key=lambda kv: kv[1]["lower"])
    open_list.sort(key=lambda kv: kv[1]["lower"])
    print(f"{len(exact_ones)} cells with a known exact value (shakedown), "
          f"{len(open_list)} cells open_list (targets).\n")

    results = []

    print("=" * 74)
    print("1 and 2. SHAKEDOWN: reach the known optimum, and do NOT exceed it")
    print("=" * 74)
    r1 = r2 = 0
    for k, v in exact_ones:
        n, d, w = (int(x) for x in k.split(","))
        all_items = _all_words(n, w)
        t0 = time.time()
        a, va = size_trial(n, d, w, v["lower"], iterations=iterations,
                                 seed=11, words=all_items)
        b, vb = size_trial(n, d, w, v["lower"] + 1,
                                 iterations=iterations, seed=11, words=all_items)
        reached = va == 0 and fast_check(a, n, d, w).ok
        broken_through = vb == 0
        r1 += reached
        r2 += not broken_through
        note = ""
        if broken_through:
            g = check(b, n, d, w)
            note = ("  OUR DEFECT: it exceeded an exact value"
                    if g.ok else "  (the slow judge rejects it: fine)")
            if g.ok:
                note = "  ALARM: the slow judge accepts it. To be understood."
        print(f"  A({n},{d},{w}):  optimum {v['lower']:>3}  "
              f"reached {'si' if reached else 'NO':<3}  "
              f"exceeded {'SI' if broken_through else 'no':<3}  "
              f"{time.time() - t0:>5.1f}s{note}")
        sys.stdout.flush()
        results.append({"cell": f"A({n},{d},{w})", "kind": "exact",
                      "value": v["lower"], "reached": reached,
                      "exceeded": broken_through})
    print(f"\n  reached {r1}/{len(exact_ones)}   not exceeded {r2}/{len(exact_ones)}")

    print("\n" + "=" * 74)
    print("3. TARGETS: match the published lower bound")
    print("=" * 74)
    even = above = below = 0
    for k, v in open_list:
        n, d, w = (int(x) for x in k.split(","))
        all_items = _all_words(n, w)
        t0 = time.time()
        a, va = size_trial(n, d, w, v["lower"], iterations=iterations,
                                 seed=11, words=all_items)
        if va != 0:
            state, extra = "SOTTO", ""
            below += 1
        else:
            b, vb = size_trial(n, d, w, v["lower"] + 1,
                                     iterations=iterations, seed=11, words=all_items)
            if vb == 0 and check(b, n, d, w).ok:
                state, extra = "SOPRA", f"  +1 sul limit ({v['lower'] + 1})"
                above += 1
            else:
                state, extra = "PAREGGIATO", ""
                even += 1
        print(f"  A({n},{d},{w}):  pubblicato {v['lower']:>3} "
              f"(sup {v['upper']})  {state:<11} {time.time() - t0:>5.1f}s"
              f"  source {v['source']}{extra}")
        sys.stdout.flush()
        entry = {"cell": f"A({n},{d},{w})", "kind": "aperto",
                "published": v["lower"], "upper": v["upper"],
                "state": state, "source": v["source"]}
        if state == "SOPRA":
            entry["words"] = sorted(b)
            print("      To be handled with docs/04-finding-protocol.md: check that the table is "
                  "aggiornata before di chiamarlo record.")
        results.append(entry)
    print(f"\n  pareggiati {even}   above {above}   below {below}")
    (DATA_DIR / "fase1_pareggio.json").write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
