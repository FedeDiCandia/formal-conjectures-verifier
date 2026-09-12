"""
Quanto costa decidere UNA forma del grafo residuo? Misura su un campione.

Per ogni forma L (vedi residui_d27.py) il problema è: esiste una decomposizione di
K27 − L in 32 copie di K5? È una copertura esatta — ogni coppia fuori da L coperta
esattamente una volta — e la si passa a CaDiCaL.

Qui NON si cerca di decidere D(27,5,2): si misura il tempo per forma, perché
25.158 forme per t secondi è il numero che dice se questa via è percorribile. Se
una forma risultasse SAT, vorrebbe dire che un pacchetto di 32 esiste: niente
annunci, docs/04.
"""
from __future__ import annotations

import json
import random
import sys
import threading
import time
from itertools import combinations
from multiprocessing import Pool
from pathlib import Path

from pysat.card import CardEnc, EncType
from pysat.formula import IDPool
from pysat.solvers import Solver

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "ricerca"))
from residui_d27 import caso_A, caso_B, costruisci   # noqa: E402


def decidi(argomenti):
    forma, limite = argomenti
    t0 = time.time()
    L = {tuple(sorted(e)) for e in costruisci(forma)}
    blocchi = [B for B in combinations(range(27), 5)
               if not any(c in L for c in combinations(B, 2))]
    pool = IDPool()
    x = [pool.id(i) for i in range(len(blocchi))]
    per_coppia: dict[tuple[int, int], list[int]] = {}
    for i, B in enumerate(blocchi):
        for c in combinations(B, 2):
            per_coppia.setdefault(c, []).append(x[i])
    clausole = []
    mancanti = [c for c in combinations(range(27), 2) if c not in L and c not in per_coppia]
    for lits in per_coppia.values():
        clausole.append(list(lits))                                   # almeno una volta
        if len(lits) > 1:
            clausole.extend(CardEnc.atmost(lits=lits, bound=1, vpool=pool,
                                           encoding=EncType.seqcounter).clauses)
    costruzione = time.time() - t0
    if mancanti:        # una coppia fuori da L che nessun K5 ammesso copre: impossibile subito
        return {"forma": forma, "stato": "UNSAT immediato", "candidati": len(blocchi),
                "secondi": round(time.time() - t0, 2), "costruzione": round(costruzione, 2)}
    s = Solver(name="cadical195", bootstrap_with=clausole)
    timer = threading.Timer(limite, s.interrupt)
    timer.start()
    r = s.solve_limited(expect_interrupt=True)
    timer.cancel()
    esito = {"forma": forma, "candidati": len(blocchi), "clausole": len(clausole),
             "costruzione": round(costruzione, 2),
             "stato": {None: "NON CONCLUSO", True: "SAT", False: "UNSAT"}[r],
             "secondi": round(time.time() - t0, 2)}
    if r:
        m = set(v for v in s.get_model() if v > 0)
        esito["blocchi"] = [blocchi[i] for i in range(len(blocchi)) if x[i] in m]
    s.delete()
    return esito


def main() -> int:
    quanti = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    limite = float(sys.argv[2]) if len(sys.argv) > 2 else 40.0
    rng = random.Random(27)
    A, B = caso_A(), caso_B()
    campione = rng.sample(A, quanti * 3 // 4) + rng.sample(B, quanti - quanti * 3 // 4)
    print(f"{len(campione)} forme su {len(A) + len(B)}, limite {limite:.0f} s ciascuna\n",
          flush=True)
    esiti = []
    with Pool(4) as p:
        for e in p.imap_unordered(decidi, [(f, limite) for f in campione]):
            esiti.append(e)
            descr = {k: v for k, v in e["forma"].items() if k != "caso"}
            print(f"  caso {e['forma']['caso']}  {e['stato']:<16} {e['secondi']:>6.1f} s "
                  f"(costruzione {e['costruzione']:.1f})  candidati {e['candidati']:>5}  {descr}",
                  flush=True)
    from collections import Counter
    print("\n", dict(Counter(e["stato"] for e in esiti)))
    conclusi = sorted(e["secondi"] for e in esiti if e["stato"] != "NON CONCLUSO")
    if conclusi:
        print(f"tempo per forma conclusa: mediana {conclusi[len(conclusi)//2]:.1f} s, "
              f"massimo {conclusi[-1]:.1f} s")
    (RADICE / "dati_ricerca" / "copertura_campione.json").write_text(
        json.dumps(esiti, indent=1, default=list))
    if any(e["stato"] == "SAT" for e in esiti):
        print("\nATTENZIONE: una forma e' SAT, cioe' esisterebbe un pacchetto di 32. "
              "NIENTE ANNUNCI: docs/04 per intero.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
