"""
The real first phase: our search, from nothing, against the published bounds.

Step zero (`reproduce.py`) showed that we can read and check the records. Here the
thing that counts is measured: **starting from nothing, how close do we get?** For
each cell a repertoire of groups is tried, the maximum weighted clique among the
orbits is sought, and the result is compared with the table.

Tre results: PAREGGIATO (uguale al limit pubblicato), SOTTO (di quanto), SOPRA
(a record beaten — to be handled with the protocol in docs/04-finding-protocol.md, not announced).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "search"))

from search_core import search_for                    # noqa: E402
from codes import check                # noqa: E402
from groups import group_names             # noqa: E402

DATA_DIR = ROOT / "research_data"


def select(bounds: dict, *, max_words: int, max_combinations: int,
           how_many: int) -> list[tuple[str, dict]]:
    """Cells within reach of a first round: small, and with a published bound."""
    candidate = []
    for k, v in bounds.items():
        n, d, w = (int(x) for x in k.split(","))
        if v["lower"] > max_words or d % 2:
            continue
        from math import comb
        if comb(n, w) > max_combinations:
            continue
        candidate.append((k, v))
    candidate.sort(key=lambda kv: (-int(kv[1]["upper"] is not None
                                       and kv[1]["upper"] > kv[1]["lower"]),
                                   kv[1]["lower"]))
    return candidate[:how_many]


def main() -> int:
    bounds = json.loads((DATA_DIR / "limiti_cwc.json").read_text())
    cells = select(bounds, max_words=400, max_combinations=300_000,
                   how_many=int(sys.argv[1]) if len(sys.argv) > 1 else 12)
    print(f"{len(cells)} cells in the first round.\n")
    print(f"{'cell':<14}{'pubbl.':>8}{'nostro':>8}{'result':>12}  "
          f"{'group':<14}{'source':<8}{'tempo':>7}")
    print("-" * 78)
    results = []
    count = {"PAREGGIATO": 0, "SOTTO": 0, "SOPRA": 0}
    for k, v in cells:
        n, d, w = (int(x) for x in k.split(","))
        t0 = time.time()
        r = search_for(n, d, w, group_names(n), restarts=60)
        mio = r["best"]["size"]
        if mio > v["lower"]:
            state = "SOPRA"
        elif mio == v["lower"]:
            state = "PAREGGIATO"
        else:
            state = "SOTTO"
        count[state] += 1
        dt = time.time() - t0
        print(f"A({n},{d},{w})".ljust(14)
              + f"{v['lower']:>8}{mio:>8}{state:>12}  "
              + f"{str(r['best']['group']):<14}{v['source']:<8}{dt:>6.1f}s")
        sys.stdout.flush()
        entry = {"cell": f"A({n},{d},{w})", "published": v["lower"],
                "nostro": mio, "state": state, "source": v["source"],
                "group": r["best"]["group"], "seconds": round(dt, 1),
                "per_gruppo": r["per_gruppo"]}
        if state == "SOPRA":
            # the slow judge, not the fast one, and the words in full
            g = check(r["best"]["words"], n, d, w)
            entry["giudice_lento"] = g.ok
            entry["words"] = r["best"]["words"]
            print(f"    ATTENTION: above the published bound. "
                  f"Giudice slow: {'valid' if g.ok else g.findings[:2]}. "
                  f"Applicare docs/04 before di chiamarlo result.")
        results.append(entry)
    (DATA_DIR / "fase1_ricerca.json").write_text(json.dumps(results, indent=1))
    print("-" * 78)
    print("  ".join(f"{s}: {c}" for s, c in count.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
