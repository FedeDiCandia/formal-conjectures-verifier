"""
Sceglie i problemi aperti piu' adatti a una ricerca al computer.

CRITERI, in ordine di importanza
--------------------------------
1. L'enunciato deve parlare di oggetti DISCRETI e FINITAMENTE CONTROLLABILI:
   numeri naturali o interi, insiemi finiti, grafi finiti. Se compaiono reali,
   limiti, misure o topologia, un programma non puo' decidere nulla.

2. La forma logica deve rendere la ricerca CONCLUSIVA:
   - `∃ x, P x` — trovare un testimone RISOLVE il problema;
   - `True ↔ ∀ n, P n` — trovare un controesempio lo risolve al contrario, e la
     modalita' `--confutazione` del verificatore permette di dimostrarlo.
   Un `∀` senza `answer( )` non si puo' confutare nel nostro schema (non esiste
   la sfida negata), quindi vale meno.

3. Il predicato deve sembrare CALCOLABILE: divisibilita', primalita',
   congruenze, conteggi su insiemi finiti. Se contiene quantificatori annidati
   su domini infiniti, il calcolo non chiude il caso singolo.

4. Meglio se l'enunciato e' CORTO: piu' e' corto, meno margine c'e' per
   fraintendere cosa si sta cercando.

Il punteggio e' una euristica dichiarata, non una misura. Serve a ordinare, non
a garantire.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
from index import ProblemIndex

CONTINUI = ["ℝ", "ℂ", "Real.", "Complex.", "Filter", "Tendsto", "liminf", "limsup",
            "Measure", "volume", "Topological", "Continuous", "Differentiable",
            "Cardinal", "Ordinal", "deriv", "∫", "∑'", "Metric", "IsOpen",
            "IsClosed", "Compact", "Homeomorph", "Manifold", "NNReal", "ENNReal",
            "Polynomial", "MeasureTheory", "EuclideanSpace", "Matrix"]
DISCRETI = ["ℕ", "ℤ", "Finset", "Fin ", "Nat.", "Int.", "SimpleGraph", "List",
            "Multiset", "ZMod"]
#: predicati che un programma sa calcolare senza pensarci troppo
CALCOLABILI = ["Prime", "prime", "∣", "Dvd", "%", "Coprime", "gcd", "Squarefree",
               "divisors", "factorial", "choose", "fib", "card", "Odd", "Even",
               "digits", "sqrt", "^", "MOD", "ZMod", "totient", "sigma"]
#: segnali che il singolo caso NON e' decidibile
INFINITO = ["Infinite", "Set.Infinite", "atTop", "∀ᶠ", "Tendsto", "Summable",
            "HasDensity", "Function.Injective", "Set.Finite"]


def corpo(p) -> str:
    e = p.statement.strip()
    return e.split("↔", 1)[1].strip() if e.startswith("True ↔") else e


def con_answer(p) -> bool:
    return p.statement.strip().startswith("True ↔")


def forma(p) -> str:
    c = corpo(p).lstrip("(¬ \n")
    if c.startswith("∃"):
        return "esistenziale"
    if c.startswith("∀"):
        return "universale"
    return "altro"


def punteggio(p) -> tuple[int, list[str]]:
    e = p.statement
    punti, note = 0, []

    if any(s in e for s in CONTINUI):
        return -100, ["parla di oggetti continui: un programma non decide nulla"]
    if not any(s in e for s in DISCRETI):
        return -100, ["non parla di oggetti discreti"]

    f = forma(p)
    if f == "esistenziale":
        punti += 40
        note.append("esistenziale: trovare il testimone RISOLVE il problema")
    elif f == "universale" and con_answer(p):
        punti += 30
        note.append("universale con answer( ): un controesempio lo confuta, "
                    "verificabile con --confutazione")
    elif f == "universale":
        punti += 5
        note.append("universale senza answer( ): un controesempio non e' "
                    "verificabile nel nostro schema")
    else:
        punti += 10

    n_calc = sum(1 for s in CALCOLABILI if s in e)
    punti += min(25, 5 * n_calc)
    if n_calc:
        note.append(f"{n_calc} predicati calcolabili nell'enunciato")

    inf = [s for s in INFINITO if s in e]
    if inf:
        punti -= 25
        note.append(f"attenzione: {', '.join(inf[:3])} — il singolo caso "
                    f"potrebbe non essere decidibile")

    L = len(e)
    if L <= 80:
        punti += 15; note.append("enunciato molto corto")
    elif L <= 150:
        punti += 8
    elif L > 300:
        punti -= 10; note.append("enunciato lungo: piu' margine di fraintendimento")

    # quantificatori annidati profondi: il caso singolo diventa costoso
    annidati = corpo(p).count("∀") + corpo(p).count("∃")
    if annidati >= 4:
        punti -= 15; note.append(f"{annidati} quantificatori: caso singolo costoso")

    if p.docstring:
        punti += 5
    else:
        note.append("senza descrizione: difficile risalire alla fonte")
    return punti, note


def main() -> int:
    idx = ProblemIndex.load()
    aperti = [p for p in idx.find(category="research open") if not p.statement_has_sorry]
    valutati = []
    for p in aperti:
        s, note = punteggio(p)
        if s > 0:
            valutati.append({"problema": p.theorem, "modulo": p.module,
                             "punteggio": s, "forma": forma(p),
                             "con_answer": con_answer(p),
                             "enunciato": p.statement,
                             "descrizione": (p.docstring or "").strip(),
                             "note": note,
                             "AMS": p.subjects})
    valutati.sort(key=lambda v: -v["punteggio"])
    quanti = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    scelti = valutati[:quanti]

    dest = RADICE / "runs" / "caccia" / "selezione.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(scelti, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Problemi aperti verificabili: {len(aperti)}")
    print(f"Con punteggio positivo:       {len(valutati)}")
    print(f"Scelti:                       {len(scelti)}\n")
    print(f"{'pt':>4} {'forma':13} {'conf':5} problema")
    print("-" * 96)
    for v in scelti:
        conf = "si" if (v["con_answer"] and v["forma"] == "universale") else ""
        print(f"{v['punteggio']:4d} {v['forma']:13} {conf:5} {v['problema']}")
        print(f"     {v['enunciato'][:105]}")
    print(f"\nSalvato in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
