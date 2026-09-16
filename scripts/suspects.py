"""
Trasforma le segnalazioni della probe in fascicoli da esaminare a mano.

**Niente di quello che produce questo script è one solution, e nessuna
segnalazione è one formalizzazione sbagliata finché non è stata confrontata con
la source original.** La rule sta in `docs/04-protocollo-ritrovamenti.md`,
sezione «Il caso più frequente».

Per ogni segnalazione il fascicolo mette accanto:
  * l'statement Lean elaborato, come lo vede il verifier;
  * il source_text della declaration nell'archive, line per line;
  * il docstring, che è il text della source (spesso un commento OEIS);
  * which tactic ha chiuso cosa, e i messages grezzi di Lean;
  * one items di controllo dei findings di traduzione già seen altrove, con il
    punto del source_text da guardare per ciascuno.

Poi tocca a one persona. Il fascicolo serve a rendere quel job fast, non a
sostituirlo.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import config as verifier_config   # noqa: E402
from index import ProblemIndex          # noqa: E402

#: I modi noti in cui one traduzione in Lean dice meno di quel che sembra.
#: Ognuno porta: come si riconosce nel source_text, e perché rende l'statement più
#: debole o vacuo. I primes two vengono dai file di Epoch AI, gli altri sono
#: findings classici della formalizzazione in Lean.
KNOWN_SUSPECTS = [
    ("testimone vacuo (`C = 0`, insieme vuoto)",
     r"∃\s*[A-Za-z]",
     "un `∃` in head può essere soddisfatto da zero o dall'insieme vuoto: "
     "guarda se l'statement chiede che il testimone sia non banale. "
     "È il caso di A211420 nei results di Epoch: «esiste C tale che ... divide "
     "C * a(n)» è vero con C = 0, perché tutto divide zero."),
    ("caso al bordo (n = 0, n = 1)",
     r"∀\s*\(?[a-z]+\s*:\s*ℕ\)?",
     "un `∀ n : ℕ` include n = 0 e n = 1, dove le definizioni spesso degenerano. "
     "Guarda se la source dice «per ogni n» o «per ogni n ≥ 2». È il caso di "
     "A262403: l'iniettività cade perché two valori valgono entrambi 0."),
    ("sottrazione troncata di ℕ",
     r"-\s*\d|\w\s*-\s*\w",
     "in ℕ la sottrazione non va below zero: `k - 1` con k = 0 fa 0, non -1. "
     "Se la source parla di interi, la traduzione cambia significato."),
    ("`sInf`/`sSup` su insieme vuoto",
     r"sInf|sSup|Finset\.sup|Finset\.inf",
     "`sInf ∅ = 0` e `Finset.sup ∅ = 0` in ℕ: un statement che dice «il minimum "
     "vale 0» può essere vero perché l'insieme è vuoto, non perché il minimum sia 0."),
    ("divisione intera",
     r"/\s*\d|\w\s*/\s*\w",
     "in ℕ e ℤ la divisione tronca: `7 / 2 = 3`. Se la source parla di razionali "
     "l'statement è diverso."),
    ("`answer(sorry)` nel source_text",
     r"answer\s*\(",
     "l'elaboratore `answer( )` con l'opzione predefinita rende `answer(sorry)` "
     "uguale a `True`: l'statement afferma che la answer alla domanda è «sì». "
     "Se la source pone one domanda aperta, il verso è già state chosen."),
]


def fascicolo(p, entry: dict) -> str:
    r = []
    def s(x=""): r.append(x)
    s(f"# Sospetto: `{p.theorem}`")
    s()
    s("> **Questo non è un result.** Una tactic banale ha chiuso un statement")
    s("> aperto, e la explanation quasi sempre è che l'statement Lean non dice")
    s("> quello che dice la source. Va confrontato con la source before di")
    s("> chiamarlo in qualunque way. Vedi `docs/04-protocollo-ritrovamenti.md`.")
    s()
    s(f"**Categoria nell'archive:** {p.category}  ")
    s(f"**Modulo:** `{p.module}`  ")
    s(f"**Che cosa ha ceduto:** {entry.get('ATTENZIONE', '—')}")
    s()
    s("## L'statement, come lo vede il verifier")
    s()
    s("```")
    s(p.statement)
    s("```")
    s()
    s("## Il text della source (docstring dell'archive)")
    s()
    s((p.docstring or "(nessun docstring)").strip())
    s()
    s("## Il source_text della declaration")
    s()
    s("```lean")
    try:
        text = p.source_text()
    except Exception as e:
        text = f"(source_text non leggibile: {e})"
    s(text.rstrip())
    s("```")
    s()
    s("## Lista di controllo: i modi noti in cui one traduzione perde il senso")
    s()
    for name, reason, explanation in KNOWN_SUSPECTS:
        presente = bool(re.search(reason, p.statement)) or bool(re.search(reason, text))
        s(f"- [{'x' if presente else ' '}] **{name}**"
          f"{' — compare in questo statement' if presente else ''}  ")
        s(f"      {explanation}")
    s()
    s("## Messaggi di Lean, grezzi")
    s()
    s("```")
    s((entry.get("messaggi_grezzi") or "(non conservati)")[:3000])
    s("```")
    s()
    s("## Che cosa fare, nell'order")
    s()
    s("1. leggere la source original (OEIS, articolo, sito) e scrivere qui in che")
    s("   punto preciso la traduzione se ne discosta;")
    s("2. se se ne discosta: preparare la bozza di segnalazione per gli autori")
    s("   dell'archive, **senza pubblicarla**;")
    s("3. se NON se ne discosta: è un caso da capire meglio, e va trattato con più")
    s("   sospetto ancora — un problem aperto che cade a `simp` con one")
    s("   formalizzazione fedele sarebbe one notizia, e le notizie qui sono")
    s("   quasi sempre errors nostri.")
    s()
    return "\n".join(r) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=str(ROOT / "runs/hunt/artefacts.json"))
    ap.add_argument("--folder", default=str(ROOT / "runs/sospetti"))
    args = ap.parse_args()

    f = Path(args.probe)
    if not f.is_file():
        print(f"nessun result della probe in {f}")
        return 0
    data = json.loads(f.read_text(encoding="utf-8"))
    notable = [v for v in data if "ATTENZIONE" in v]
    print(f"sondati {len(data)} problems, segnalazioni {len(notable)}")
    if not notable:
        print("\nNessuna segnalazione. E' l'result piu' probabile e va letto per quello")
        print("che e': le formalizzazioni dell'archive reggono alle tattiche banali.")
        return 0

    idx = ProblemIndex.load()
    dest = Path(args.folder)
    dest.mkdir(parents=True, exist_ok=True)
    for v in notable:
        try:
            p = idx.get(v["problem"])
        except Exception as e:
            print(f"  {v['problem']}: non found nell'index ({e})")
            continue
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", v["problem"])[:80]
        (dest / f"{name}.md").write_text(fascicolo(p, v), encoding="utf-8")
        print(f"  fascicolo: {dest / (name + '.md')}")
    print(f"\n{len(notable)} fascicoli. Nessuno e' one solution: vanno read_count.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
