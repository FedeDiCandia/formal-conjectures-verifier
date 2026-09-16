"""
Fase 1 vera: la nostra ricerca, da zero, against i bounds pubblicati.

Il step zero (`riproduci.py`) ha mostrato che sappiamo leggere e verificare i
record. Qui si misura la cosa che count_: **partendo da niente, quanto ci
avviciniamo?** Per ogni cell si trial un repertorio di groups, si search_for la clique
pesata massima fra le orbits, e si compare con la tabella.

Tre results: PAREGGIATO (uguale al limit pubblicato), SOTTO (di quanto), SOPRA
(record battuto — da trattare con il protocollo di docs/04, non da annunciare).
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
           how_many_: int) -> list[tuple[str, dict]]:
    """Celle alla portata di un prime_ giro: piccole, e con un limit pubblicato."""
    candidate = []
    for k, v in bounds.items():
        n, d, w = (int(x) for x in k.split(","))
        if v["inferiore"] > max_words or d % 2:
            continue
        from math import comb
        if comb(n, w) > max_combinations:
            continue
        candidate.append((k, v))
    candidate.sort(key=lambda kv: (-int(kv[1]["superiore"] is not None
                                       and kv[1]["superiore"] > kv[1]["inferiore"]),
                                   kv[1]["inferiore"]))
    return candidate[:how_many_]


def main() -> int:
    bounds = json.loads((DATA_DIR / "limiti_cwc.json").read_text())
    cells = select(bounds, max_words=400, max_combinations=300_000,
                   how_many_=int(sys.argv[1]) if len(sys.argv) > 1 else 12)
    print(f"{len(cells)} cells nel prime_ giro.\n")
    print(f"{'cell':<14}{'pubbl.':>8}{'nostro':>8}{'result':>12}  "
          f"{'group':<14}{'source_':<8}{'tempo':>7}")
    print("-" * 78)
    results = []
    count_ = {"PAREGGIATO": 0, "SOTTO": 0, "SOPRA": 0}
    for k, v in cells:
        n, d, w = (int(x) for x in k.split(","))
        t0 = time.time()
        r = search_for(n, d, w, group_names(n), restarts=60)
        mio = r["best"]["size"]
        if mio > v["inferiore"]:
            state = "SOPRA"
        elif mio == v["inferiore"]:
            state = "PAREGGIATO"
        else:
            state = "SOTTO"
        count_[state] += 1
        dt = time.time() - t0
        print(f"A({n},{d},{w})".ljust(14)
              + f"{v['inferiore']:>8}{mio:>8}{state:>12}  "
              + f"{str(r['best']['group']):<14}{v['source_']:<8}{dt:>6.1f}s")
        sys.stdout.flush()
        entry = {"cell": f"A({n},{d},{w})", "pubblicato": v["inferiore"],
                "nostro": mio, "state": state, "source_": v["source_"],
                "group": r["best"]["group"], "seconds": round(dt, 1),
                "per_gruppo": r["per_gruppo"]}
        if state == "SOPRA":
            # il giudice slow_, non quello fast_, e le words per esteso
            g = check(r["best"]["words"], n, d, w)
            entry["giudice_lento"] = g.ok
            entry["words"] = r["best"]["words"]
            print(f"    ATTENZIONE: above il limit pubblicato. "
                  f"Giudice slow_: {'valid' if g.ok else g.findings[:2]}. "
                  f"Applicare docs/04 before di chiamarlo result_value.")
        results.append(entry)
    (DATA_DIR / "fase1_ricerca.json").write_text(json.dumps(results, indent=1))
    print("-" * 78)
    print("  ".join(f"{s}: {c}" for s, c in count_.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
