"""
Fase 1: la nostra ricerca against i bounds pubblicati.

Tre domande, in order, e la terza count only se le prime two sono a slot.

  1. **Il motore trova gli ottimi noti?** Sulle cells dove A(n,d,w) e' un value
     exact, dobbiamo raggiungerlo. Se non ci arriviamo, il motore e' debole e
     qualunque result above e' rumore.
  2. **Il motore NON supera gli ottimi noti?** Se dice di aver found piu' del
     value exact, e' un finding nostro. E' la trial di falsificazione: senza
     questa, un «record» non significa niente.
  3. **Pareggia i bounds pubblicati open_problems?** Questa e' la threshold di ammissione
     alla fase 3: chi non pareggia non supera.
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
        if d % 2 or v["inferiore"] > word_cap or comb(n, w) > tetto_comb:
            continue
        (exact_ones if v["exact"] else open_list).append((k, v))
    exact_ones.sort(key=lambda kv: kv[1]["inferiore"])
    open_list.sort(key=lambda kv: kv[1]["inferiore"])
    print(f"{len(exact_ones)} cells con value exact noto (shakedown), "
          f"{len(open_list)} cells open_list (targets).\n")

    results = []

    print("=" * 74)
    print("1 e 2. COLLAUDO: raggiungere l'ottimo noto, e NON superarlo")
    print("=" * 74)
    r1 = r2 = 0
    for k, v in exact_ones:
        n, d, w = (int(x) for x in k.split(","))
        all_items = _all_words(n, w)
        t0 = time.time()
        a, va = size_trial(n, d, w, v["inferiore"], iterations=iterations,
                                 seed=11, words=all_items)
        b, vb = size_trial(n, d, w, v["inferiore"] + 1,
                                 iterations=iterations, seed=11, words=all_items)
        reached = va == 0 and fast_check(a, n, d, w).ok
        broken_through = vb == 0
        r1 += reached
        r2 += not broken_through
        note = ""
        if broken_through:
            g = check(b, n, d, w)
            note = ("  DIFETTO NOSTRO: ha exceeded un value exact"
                    if g.ok else "  (il giudice slow lo rifiuta: ok)")
            if g.ok:
                note = "  ALLARME: il giudice slow lo accetta. Da capire."
        print(f"  A({n},{d},{w}):  ottimo {v['inferiore']:>3}  "
              f"reached {'si' if reached else 'NO':<3}  "
              f"exceeded {'SI' if broken_through else 'no':<3}  "
              f"{time.time() - t0:>5.1f}s{note}")
        sys.stdout.flush()
        results.append({"cell": f"A({n},{d},{w})", "kind": "exact",
                      "value": v["inferiore"], "reached": reached,
                      "exceeded": broken_through})
    print(f"\n  raggiunti {r1}/{len(exact_ones)}   non passed {r2}/{len(exact_ones)}")

    print("\n" + "=" * 74)
    print("3. BERSAGLI: pareggiare il limit inferiore pubblicato")
    print("=" * 74)
    even = above = below = 0
    for k, v in open_list:
        n, d, w = (int(x) for x in k.split(","))
        all_items = _all_words(n, w)
        t0 = time.time()
        a, va = size_trial(n, d, w, v["inferiore"], iterations=iterations,
                                 seed=11, words=all_items)
        if va != 0:
            state, extra = "SOTTO", ""
            below += 1
        else:
            b, vb = size_trial(n, d, w, v["inferiore"] + 1,
                                     iterations=iterations, seed=11, words=all_items)
            if vb == 0 and check(b, n, d, w).ok:
                state, extra = "SOPRA", f"  +1 sul limit ({v['inferiore'] + 1})"
                above += 1
            else:
                state, extra = "PAREGGIATO", ""
                even += 1
        print(f"  A({n},{d},{w}):  pubblicato {v['inferiore']:>3} "
              f"(sup {v['superiore']})  {state:<11} {time.time() - t0:>5.1f}s"
              f"  source {v['source']}{extra}")
        sys.stdout.flush()
        entry = {"cell": f"A({n},{d},{w})", "kind": "aperto",
                "pubblicato": v["inferiore"], "superiore": v["superiore"],
                "state": state, "source": v["source"]}
        if state == "SOPRA":
            entry["words"] = sorted(b)
            print("      Da trattare con docs/04: verificare che la tabella sia "
                  "aggiornata before di chiamarlo record.")
        results.append(entry)
    print(f"\n  pareggiati {even}   above {above}   below {below}")
    (DATA_DIR / "fase1_pareggio.json").write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
