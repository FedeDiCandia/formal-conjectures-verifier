"""
Scelta del lotto: i problemi dove un risultato ha un TESTIMONE PICCOLO.

IL CRITERIO IN CIMA, E PERCHÉ
-----------------------------
Il verificatore certifica ciò che Lean riesce a controllare. Per un enunciato
della forma «per ogni n esiste k < n con P(n,k)», confutarlo su un n specifico
vuol dire dimostrare che NESSUNO dei n−1 valori di k funziona: per un n oltre il
milione sono un milione di fatti di compostezza, e il kernel non ci arriva. La
ricerca troverebbe il controesempio e il verificatore non potrebbe certificarlo.

Invece per un enunciato della forma «esiste un oggetto con la proprietà P», un
oggetto concreto **è** la dimostrazione: tre righe di Lean e `decide`. Lo stesso
vale per «P vale solo per n = a, b, c», dove un quarto valore chiude la
questione, e per «tutti i termini hanno la proprietà P», dove basta un termine
che non la ha.

Quindi la prima domanda non è «quanto è corto l'enunciato» ma **«se il risultato
esiste, Lean lo può controllare in poche righe?»**.

  1. TESTIMONE PICCOLO (+50): un esistenziale in testa, o un'affermazione del
     tipo «solo per questi valori», o «tutti i termini sono così». Un oggetto
     concreto risolve, e si verifica con `decide`/`norm_num`.
  2. testimone per enumerazione (+0): «per ogni n esiste k < n...». Cercabile,
     non certificabile: il controesempio richiederebbe di escludere tutti i k.
  3. nessun testimone (−40): «esistono infiniti...», limiti, densità. Né una
     ricerca né un oggetto concreto possono chiuderli.

Gli altri criteri restano, con peso minore: predicato calcolabile (+30),
enunciato corto (+20/+10), nessun nome celebre (+15), frontiera dichiarata
grande (−20).
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
    corpo = s.split("↔", 1)[1].strip() if s.startswith("True ↔") else s
    punti, note = 0, []

    # --- 1. la forma del testimone: il criterio che decide
    senza_testimone = any(x in s for x in SEGNI_INFINITA)
    esistenziale = corpo.startswith("∃")
    solo_per = bool(re.search(r"↔\s*(n|k|m)\s*=|= \d+ ∨", s))
    tutti_i_termini = bool(re.match(r"∀[^,]*,\s*(0 < |1 ≤ )?\w+\s*→?\s*"
                                    r"(Even|Odd|Nat\.Prime|IsSquare|Squarefree|¬)", corpo))
    enumerazione = bool(re.search(r"∃\s*\w+\s*<|∃\s*\w+\s*≤", corpo))
    if senza_testimone:
        punti -= 40; note.append("NESSUN testimone: affermazione di infinita'/limite")
    elif esistenziale:
        punti += 50; note.append("TESTIMONE PICCOLO: un oggetto concreto dimostra")
    elif solo_per:
        punti += 50; note.append("TESTIMONE PICCOLO: un valore in piu' confuta")
    elif tutti_i_termini:
        punti += 50; note.append("TESTIMONE PICCOLO: un termine che non rispetta confuta")
    elif enumerazione:
        note.append("testimone per ENUMERAZIONE: cercabile ma non certificabile")
    else:
        note.append("forma del testimone non riconosciuta")

    # --- gli altri criteri, con peso minore
    if any(x in s for x in SEGNI_CALCOLABILE):
        punti += 30; note.append("predicato calcolabile")
    if len(s) <= 90:
        punti += 20; note.append(f"enunciato corto ({len(s)})")
    elif len(s) <= 140:
        punti += 10; note.append(f"enunciato medio ({len(s)})")
    if any(n in doc for n in NOMI_FAMOSI):
        note.append("ATTENZIONE: congettura con un nome")
    else:
        punti += 15; note.append("nessun nome celebre")
    if RE_FRONTIERA.search(doc):
        punti -= 20; note.append("frontiera dichiarata grande")
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
