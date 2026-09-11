"""
Sonda gli enunciati aperti con tattiche automatiche, sia diritti sia negati.

IDEA
----
Prima di scrivere un programma di ricerca su misura, conviene chiedere a Lean se
per caso la risposta e' a portata di tattica. Due tattiche in particolare:

  * `plausible` (di Mathlib) genera casi a caso e cerca un CONTROESEMPIO. Se ne
    trova uno, la congettura come e' formalizzata e' falsa — il che di solito
    non significa aver risolto un problema aperto, ma aver trovato una
    formalizzazione imprecisa. E' un'informazione preziosa lo stesso.
  * `decide` chiude gli enunciati decidibili su domini finiti. Su un problema
    aperto non chiudera' quasi mai, ma se lo fa c'e' qualcosa da capire.

Si prova su DUE forme: l'enunciato com'e' e la sua negazione. Un problema aperto
formalizzato come `True ↔ P` afferma che la risposta e' si'; se `plausible`
trova un controesempio a `P`, la risposta potrebbe essere no.

Il timeout e' volutamente BREVE: qui non si cerca di risolvere niente, si
cercano i casi in cui la risposta salta fuori da sola. Quelli che richiedono
davvero calcolo passano alla fase successiva, con un programma su misura.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))

import config as config_verificatore
import esplora
from index import ProblemIndex

#: Le tattiche provate, in ordine di costo crescente.
TATTICHE = [
    ("decide", "decide"),
    ("plausible", "plausible"),
    ("norm_num", "norm_num"),
    ("simp_arith", "simp_arith"),
]

MODELLO = """import {utilita}
import {modulo}

set_option maxHeartbeats {heartbeats} in
example : {enunciato} := by
  {tattica}
"""


def prova(problema, tattica_nome, tattica, negato: bool, heartbeats: int,
          timeout: int) -> dict:
    """Prova una tattica sull'enunciato (o sulla sua negazione)."""
    tipo = f"type_of% {problema.theorem}"
    enunciato = f"¬ ({tipo})" if negato else tipo
    codice = MODELLO.format(utilita=config_verificatore.modulo_utilita(),
                            modulo=problema.module, enunciato=enunciato,
                            tattica=tattica, heartbeats=heartbeats)
    t0 = time.time()
    r = esplora.esplora(codice, timeout=timeout)
    durata = time.time() - t0
    messaggi = r.messaggi
    esito = "chiusa" if r.ok else "aperta"
    controesempio = None
    if "Found a counter-example" in messaggi or "counterexample" in messaggi.lower():
        esito = "controesempio"
        righe = [l for l in messaggi.split("\n") if l.strip()]
        controesempio = "\n".join(righe[:25])
    elif "TEMPO SCADUTO" in messaggi:
        esito = "tempo scaduto"
    elif "maximum number of heartbeats" in messaggi:
        esito = "heartbeat esauriti"
    return {
        "tattica": tattica_nome, "negato": negato, "esito": esito,
        "secondi": round(durata, 1),
        "controesempio": controesempio,
        "messaggi": messaggi[:1500] if esito in ("chiusa", "controesempio") else "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quanti", type=int, default=30)
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--heartbeats", type=int, default=400000)
    ap.add_argument("--uscita", default=str(RADICE / "runs" / "caccia" / "sonda_lean.json"))
    ap.add_argument("--problemi", default="")
    args = ap.parse_args()

    idx = ProblemIndex.load()
    if args.problemi:
        scelti = [idx.get(n) for n in args.problemi.split()]
    else:
        # aperti, verificabili, su oggetti discreti, enunciato corto
        SEGNALI_CONTINUI = ["ℝ", "ℂ", "Real.", "Complex.", "Filter", "Tendsto",
                            "Measure", "Topological", "Continuous", "Cardinal",
                            "deriv", "∫", "Metric", "Manifold", "NNReal", "ENNReal"]
        SEGNALI_DISCRETI = ["ℕ", "ℤ", "Finset", "Fin ", "Nat.", "Int.", "SimpleGraph"]
        aperti = [p for p in idx.find(category="research open")
                  if not p.statement_has_sorry
                  and not any(s in p.statement for s in SEGNALI_CONTINUI)
                  and any(s in p.statement for s in SEGNALI_DISCRETI)]
        aperti.sort(key=lambda p: len(p.statement))
        scelti = aperti[:args.quanti]

    print(f"Sondo {len(scelti)} problemi con {len(TATTICHE)} tattiche x 2 forme.")
    print(f"Timeout per prova: {args.timeout}s. Nessuna spesa API.\n", flush=True)

    risultati = []
    uscita = Path(args.uscita)
    uscita.parent.mkdir(parents=True, exist_ok=True)

    for i, p in enumerate(scelti, 1):
        voce = {"problema": p.theorem, "modulo": p.module,
                "enunciato": p.statement[:400], "prove": []}
        print(f"[{i}/{len(scelti)}] {p.theorem}", flush=True)
        for nome, tattica in TATTICHE:
            for negato in (False, True):
                e = prova(p, nome, tattica, negato, args.heartbeats, args.timeout)
                voce["prove"].append(e)
                marchio = {"chiusa": "!!! CHIUSA !!!", "controesempio": "!!! CONTROESEMPIO !!!"}.get(
                    e["esito"], "")
                forma = "¬" if negato else " "
                print(f"      {forma} {nome:12} {e['esito']:18} {e['secondi']:5.1f}s  {marchio}",
                      flush=True)
                if e["esito"] in ("chiusa", "controesempio"):
                    voce["ATTENZIONE"] = (
                        f"la tattica {nome} ha {e['esito']} la forma "
                        f"{'negata' if negato else 'diritta'}")
        risultati.append(voce)
        uscita.write_text(json.dumps(risultati, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    notevoli = [v for v in risultati if "ATTENZIONE" in v]
    print(f"\n{'='*70}")
    print(f"Esaminati {len(risultati)} problemi. Notevoli: {len(notevoli)}")
    for v in notevoli:
        print(f"  {v['problema']}: {v['ATTENZIONE']}")
    print(f"\nRisultati in {uscita}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
