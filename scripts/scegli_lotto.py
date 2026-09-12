"""
Scelta del primo lotto della scala: dieci problemi fra i 54 della famiglia buona.

Il criterio è dichiarato e ordinato per importanza. Non è un giudizio estetico:
ogni voce dice che cosa rende il problema più aggredibile *da questo sistema*.

  1. il predicato è CALCOLABILE su un caso singolo — così `run_python` con
     `sympy` può cercare un controesempio e `decide` può verificarlo in Lean;
  2. l'enunciato è CORTO — meno pezzi da riprodurre esattamente, e la nostra
     misura dice che il costo cresce con la lunghezza;
  3. la confutazione è un CASO SINGOLO (`∀ n, P n`), non un'affermazione di
     infinità: un controesempio si verifica, «esistono infiniti» no;
  4. non è una congettura CON UN NOME (Sun, Erdős, Murthy...): quelle stanno
     nelle raccolte che i matematici leggono, e la lettura della letteratura ha
     mostrato che là la frontiera è lontana;
  5. il docstring NON dichiara una frontiera di verifica enorme.

Il punteggio è la somma dei punti, e l'ordine finale è per punteggio.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
from index import ProblemIndex   # noqa: E402

NOMI_FAMOSI = ("Sun", "Erdős", "Erdos", "Murthy", "Sierpinski", "Sierpiński",
               "Goldbach", "Levy", "Lemoine", "Catalan", "Mersenne", "Haken",
               "Selfridge", "Collatz", "Legendre", "Hardy", "Ramanujan")
SEGNI_CALCOLABILE = ("Nat.Prime", "Finset", "digits", "totient", "divisors",
                     "gcd", "Squarefree", "IsSquare", "Odd", "Even", "∣")
SEGNI_INFINITA = ("Infinite", "Set.Infinite", "Tendsto", "atTop")
RE_FRONTIERA = re.compile(r"(10\^\{?\d\d|\b\d{7,}\b)")


def punteggio(p) -> tuple[int, list[str]]:
    s = " ".join(p.statement.split())
    doc = " ".join((p.docstring or "").split())
    punti, note = 0, []
    if any(x in s for x in SEGNI_CALCOLABILE):
        punti += 30; note.append("predicato calcolabile")
    if len(s) <= 90:
        punti += 20; note.append(f"enunciato corto ({len(s)} caratteri)")
    elif len(s) <= 140:
        punti += 10; note.append(f"enunciato medio ({len(s)} caratteri)")
    if s.startswith("∀") and not any(x in s for x in SEGNI_INFINITA):
        punti += 25; note.append("confutabile con un caso singolo")
    if not any(n in doc for n in NOMI_FAMOSI):
        punti += 15; note.append("nessun nome celebre nel docstring")
    else:
        note.append("ATTENZIONE: congettura con un nome")
    if RE_FRONTIERA.search(doc):
        punti -= 20; note.append("il docstring dichiara una frontiera grande")
    return punti, note


def main() -> int:
    idx = ProblemIndex.load()
    bers = json.loads((RADICE / "docs/dati/bersagli.json").read_text(encoding="utf-8"))
    cand = {c["problema"]: c for c in bers["candidati"]}
    CONTINUO = ["ℝ", "ℂ", "Real.", "Complex.", "riemannZeta", "Filter", "Measure",
                "Topological", "Continuous", "Cardinal", "deriv", "∫", "Metric",
                "Manifold", "Polynomial", "Matrix"]
    famiglia = [p for p in idx.find(category="research open")
                if not p.statement_has_sorry
                and "OEIS" in p.module
                and not any(x in p.statement for x in CONTINUO)
                and cand.get(p.theorem, {}).get("mai_nel_loro_benchmark")]
    print(f"famiglia OEIS elementare mai toccata da Epoch: {len(famiglia)} problemi\n")
    classifica = sorted(((punteggio(p)[0], p, punteggio(p)[1]) for p in famiglia),
                        key=lambda x: -x[0])
    fuori = []
    for i, (pt, p, note) in enumerate(classifica, 1):
        if i <= 12:
            print(f"{i:3}. [{pt:3}] {p.theorem}")
            print(f"          {' '.join(p.statement.split())[:95]}")
            print(f"          {'; '.join(note)}")
            print(f"          fonte: {' '.join((p.docstring or '').split())[:110]}")
        fuori.append({"posizione": i, "punteggio": pt, "problema": p.theorem,
                      "modulo": p.module, "enunciato": " ".join(p.statement.split()),
                      "note": note,
                      "docstring": " ".join((p.docstring or "").split())})
    dest = RADICE / "docs/dati/lotto.json"
    dest.write_text(json.dumps(fuori, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nclassifica completa in {dest}")
    print("i dieci del primo lotto:")
    print("  " + " ".join(v["problema"] for v in fuori[:10]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
