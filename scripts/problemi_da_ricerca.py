"""
Problemi aperti attaccabili cercando un esempio o un controesempio.

Due famiglie:

  A. ESISTENZIALI — l'enunciato chiede `∃ x, P x` con `P` decidibile su oggetti
     discreti. Un programma cerca il testimone; trovato quello, la
     dimostrazione Lean e' spesso `use <testimone>; decide` o poco piu'.
     Si verificano in modalita' STRETTA.

  B. UNIVERSALI con `answer( )` proposizionale — l'enunciato dice
     `True ↔ ∀ n, P n`, cioe' "la risposta e' si'". Se esiste un controesempio,
     la cosa da dimostrare e' `False ↔ ∀ n, P n`, cioe' `¬∀ n, P n`: si
     verificano in modalita' CONFUTAZIONE, e la dimostrazione e' di nuovo
     "esibisci il controesempio e calcola".

Perche' questa famiglia conta: e' l'unico caso in cui un calcolo puo' davvero
risolvere un problema aperto. Su un universale senza controesempi il calcolo non
conclude mai; su un esistenziale, trovare il testimone E' la soluzione.
"""
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
from index import ProblemIndex

idx = ProblemIndex.load()

SEGNALI_CONTINUI = [
    "ℝ", "ℂ", "Real.", "Complex.", "Filter", "Tendsto", "liminf", "limsup",
    "Measure", "volume", "Topological", "Continuous", "Differentiable",
    "Cardinal", "Ordinal", "deriv", "∫", "∑'", "Metric", "IsOpen", "IsClosed",
    "Compact", "Homeomorph", "Manifold", "NNReal", "ENNReal",
]
SEGNALI_DISCRETI = ["ℕ", "ℤ", "Finset", "Fin ", "Nat.", "Int.", "SimpleGraph",
                    "Decidable", "List", "Multiset"]
#: un enunciato che parla di insiemi infiniti non si chiude con un calcolo
SEGNALI_INFINITO = ["Infinite", ".Infinite", "Set.Infinite", "∀ᶠ", "atTop"]


def discreto(e: str) -> bool:
    return (not any(s in e for s in SEGNALI_CONTINUI)
            and any(s in e for s in SEGNALI_DISCRETI))


def corpo(p):
    e = p.statement.strip()
    return e.split("↔", 1)[1].strip() if e.startswith("True ↔") else e


def con_answer(p) -> bool:
    return p.statement.strip().startswith("True ↔")


aperti = [p for p in idx.find(category="research open") if not p.statement_has_sorry]

esistenziali = [p for p in aperti
                if corpo(p).lstrip("(¬ \n").startswith("∃")
                and discreto(p.statement)
                and not any(s in p.statement for s in SEGNALI_INFINITO)]

universali_conf = [p for p in aperti
                   if con_answer(p)
                   and corpo(p).lstrip("(¬ \n").startswith("∀")
                   and discreto(p.statement)
                   and not any(s in p.statement for s in SEGNALI_INFINITO)]

print("=" * 78)
print("A. ESISTENZIALI DISCRETI — cercare il testimone (modalita' stretta)")
print("=" * 78)
print(f"  {len(esistenziali)} problemi\n")
for p in sorted(esistenziali, key=lambda x: len(x.statement)):
    print(f"  [{len(p.statement):3d} car] {p.theorem}")
    print(f"      {p.statement[:150]}")
    if p.docstring:
        print(f"      \"{p.docstring.strip().splitlines()[0][:110]}\"")
    print()

print("=" * 78)
print("B. UNIVERSALI DISCRETI con answer( ) — cercare il controesempio (--confutazione)")
print("=" * 78)
print(f"  {len(universali_conf)} problemi\n")
for p in sorted(universali_conf, key=lambda x: len(x.statement))[:14]:
    print(f"  [{len(p.statement):3d} car] {p.theorem}")
    print(f"      {p.statement[:150]}")
    if p.docstring:
        print(f"      \"{p.docstring.strip().splitlines()[0][:110]}\"")
    print()
