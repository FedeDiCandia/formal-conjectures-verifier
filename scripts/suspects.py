"""
Trasforma le segnalazioni della sonda in fascicoli da esaminare a mano.

**Niente di quello che produce questo script è una soluzione, e nessuna
segnalazione è una formalizzazione sbagliata finché non è stata confrontata con
la fonte originale.** La regola sta in `docs/04-protocollo-ritrovamenti.md`,
sezione «Il caso più frequente».

Per ogni segnalazione il fascicolo mette accanto:
  * l'enunciato Lean elaborato, come lo vede il verificatore;
  * il sorgente della dichiarazione nell'archivio, riga per riga;
  * il docstring, che è il testo della fonte (spesso un commento OEIS);
  * quale tattica ha chiuso cosa, e i messaggi grezzi di Lean;
  * una lista di controllo dei difetti di traduzione già visti altrove, con il
    punto del sorgente da guardare per ciascuno.

Poi tocca a una persona. Il fascicolo serve a rendere quel lavoro rapido, non a
sostituirlo.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))

import config as config_verificatore   # noqa: E402
from index import ProblemIndex          # noqa: E402

#: I modi noti in cui una traduzione in Lean dice meno di quel che sembra.
#: Ognuno porta: come si riconosce nel sorgente, e perché rende l'enunciato più
#: debole o vacuo. I primi due vengono dai file di Epoch AI, gli altri sono
#: difetti classici della formalizzazione in Lean.
SOSPETTI_NOTI = [
    ("testimone vacuo (`C = 0`, insieme vuoto)",
     r"∃\s*[A-Za-z]",
     "un `∃` in testa può essere soddisfatto da zero o dall'insieme vuoto: "
     "guarda se l'enunciato chiede che il testimone sia non banale. "
     "È il caso di A211420 nei risultati di Epoch: «esiste C tale che ... divide "
     "C * a(n)» è vero con C = 0, perché tutto divide zero."),
    ("caso al bordo (n = 0, n = 1)",
     r"∀\s*\(?[a-z]+\s*:\s*ℕ\)?",
     "un `∀ n : ℕ` include n = 0 e n = 1, dove le definizioni spesso degenerano. "
     "Guarda se la fonte dice «per ogni n» o «per ogni n ≥ 2». È il caso di "
     "A262403: l'iniettività cade perché due valori valgono entrambi 0."),
    ("sottrazione troncata di ℕ",
     r"-\s*\d|\w\s*-\s*\w",
     "in ℕ la sottrazione non va sotto zero: `k - 1` con k = 0 fa 0, non -1. "
     "Se la fonte parla di interi, la traduzione cambia significato."),
    ("`sInf`/`sSup` su insieme vuoto",
     r"sInf|sSup|Finset\.sup|Finset\.inf",
     "`sInf ∅ = 0` e `Finset.sup ∅ = 0` in ℕ: un enunciato che dice «il minimo "
     "vale 0» può essere vero perché l'insieme è vuoto, non perché il minimo sia 0."),
    ("divisione intera",
     r"/\s*\d|\w\s*/\s*\w",
     "in ℕ e ℤ la divisione tronca: `7 / 2 = 3`. Se la fonte parla di razionali "
     "l'enunciato è diverso."),
    ("`answer(sorry)` nel sorgente",
     r"answer\s*\(",
     "l'elaboratore `answer( )` con l'opzione predefinita rende `answer(sorry)` "
     "uguale a `True`: l'enunciato afferma che la risposta alla domanda è «sì». "
     "Se la fonte pone una domanda aperta, il verso è già stato scelto."),
]


def fascicolo(p, voce: dict) -> str:
    r = []
    def s(x=""): r.append(x)
    s(f"# Sospetto: `{p.theorem}`")
    s()
    s("> **Questo non è un risultato.** Una tattica banale ha chiuso un enunciato")
    s("> aperto, e la spiegazione quasi sempre è che l'enunciato Lean non dice")
    s("> quello che dice la fonte. Va confrontato con la fonte prima di")
    s("> chiamarlo in qualunque modo. Vedi `docs/04-protocollo-ritrovamenti.md`.")
    s()
    s(f"**Categoria nell'archivio:** {p.category}  ")
    s(f"**Modulo:** `{p.module}`  ")
    s(f"**Che cosa ha ceduto:** {voce.get('ATTENZIONE', '—')}")
    s()
    s("## L'enunciato, come lo vede il verificatore")
    s()
    s("```")
    s(p.statement)
    s("```")
    s()
    s("## Il testo della fonte (docstring dell'archivio)")
    s()
    s((p.docstring or "(nessun docstring)").strip())
    s()
    s("## Il sorgente della dichiarazione")
    s()
    s("```lean")
    try:
        testo = p.source_text()
    except Exception as e:
        testo = f"(sorgente non leggibile: {e})"
    s(testo.rstrip())
    s("```")
    s()
    s("## Lista di controllo: i modi noti in cui una traduzione perde il senso")
    s()
    for nome, motivo, spiegazione in SOSPETTI_NOTI:
        presente = bool(re.search(motivo, p.statement)) or bool(re.search(motivo, testo))
        s(f"- [{'x' if presente else ' '}] **{nome}**"
          f"{' — compare in questo enunciato' if presente else ''}  ")
        s(f"      {spiegazione}")
    s()
    s("## Messaggi di Lean, grezzi")
    s()
    s("```")
    s((voce.get("messaggi_grezzi") or "(non conservati)")[:3000])
    s("```")
    s()
    s("## Che cosa fare, nell'ordine")
    s()
    s("1. leggere la fonte originale (OEIS, articolo, sito) e scrivere qui in che")
    s("   punto preciso la traduzione se ne discosta;")
    s("2. se se ne discosta: preparare la bozza di segnalazione per gli autori")
    s("   dell'archivio, **senza pubblicarla**;")
    s("3. se NON se ne discosta: è un caso da capire meglio, e va trattato con più")
    s("   sospetto ancora — un problema aperto che cade a `simp` con una")
    s("   formalizzazione fedele sarebbe una notizia, e le notizie qui sono")
    s("   quasi sempre errori nostri.")
    s()
    return "\n".join(r) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sonda", default=str(RADICE / "runs/caccia/artefatti.json"))
    ap.add_argument("--cartella", default=str(RADICE / "runs/sospetti"))
    args = ap.parse_args()

    f = Path(args.sonda)
    if not f.is_file():
        print(f"nessun risultato della sonda in {f}")
        return 0
    dati = json.loads(f.read_text(encoding="utf-8"))
    notevoli = [v for v in dati if "ATTENZIONE" in v]
    print(f"sondati {len(dati)} problemi, segnalazioni {len(notevoli)}")
    if not notevoli:
        print("\nNessuna segnalazione. E' l'esito piu' probabile e va letto per quello")
        print("che e': le formalizzazioni dell'archivio reggono alle tattiche banali.")
        return 0

    idx = ProblemIndex.load()
    dest = Path(args.cartella)
    dest.mkdir(parents=True, exist_ok=True)
    for v in notevoli:
        try:
            p = idx.get(v["problema"])
        except Exception as e:
            print(f"  {v['problema']}: non trovato nell'indice ({e})")
            continue
        nome = re.sub(r"[^A-Za-z0-9_.-]", "_", v["problema"])[:80]
        (dest / f"{nome}.md").write_text(fascicolo(p, v), encoding="utf-8")
        print(f"  fascicolo: {dest / (nome + '.md')}")
    print(f"\n{len(notevoli)} fascicoli. Nessuno e' una soluzione: vanno letti.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
