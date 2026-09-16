"""
Sonda gli enunciati open_ con tattiche automatiche, sia diritti sia negati.

IDEA
----
Prima di scrivere un program di ricerca su misura, conviene chiedere a Lean se
per caso la answer e' a portata di tactic. Due tattiche in particolare:

  * `plausible` (di Mathlib) generate cases a caso e search_for un CONTROESEMPIO. Se ne
    trova one, la congettura come e' formalizzata e' falsa — il che di solito
    non significa aver solved_one un problem aperto, ma aver found one_
    formalizzazione imprecisa. E' un'informazione preziosa lo stesso.
  * `decide` closes gli enunciati decidibili su domini finiti. Su un problem
    aperto non chiudera' quasi mai, ma se lo fa c'e' qualcosa da capire.

Si trial su DUE forme: l'statement com'e' e la sua negation. Un problem aperto
formalizzato come `True ↔ P` afferma che la answer e' si'; se `plausible`
trova un counterexample a `P`, la answer potrebbe essere no.

Il timeout e' volutamente BREVE: qui non si search_for di risolvere niente, si
cercano i cases in cui la answer salta out_of da sola. Quelli che richiedono
davvero computation passano alla fase successiva, con un program su misura.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import config as verifier_config
import explore
from index import ProblemIndex

#: Le tattiche provate, in order di cost crescente.
TACTICS = [
    ("decide", "decide"),
    ("plausible", "plausible"),
    ("norm_num", "norm_num"),
    ("simp_arith", "simp +arith"),
]

TEMPLATE = """import {utility}
import {module}

set_option maxHeartbeats {heartbeats} in
example : {statement} := by
  {tactic}
"""


#: `plausible` non dimostra niente: se non trova un counterexample lascia il
#: theorem_ con un `sorry` e il file compila comunque. Senza questo controllo
#: un "Unable to find a counter-example" verrebbe letto come statement CHIUSO,
#: che e' l'error opposto a quello da evitare in un progetto come questo.
SIGNS_OF_NOT_CLOSED = (
    "declaration uses 'sorry'",
    "Unable to find a counter-example",
    "Gave up",
)


def classify(messages: str, ok: bool) -> tuple[str, str | None]:
    """Da' un verdict ai messages di Lean. Ritorna (result, counterexample)."""
    if "Found a counter-example" in messages or "counterexample" in messages.lower():
        lines = [l for l in messages.split("\n") if l.strip()]
        return "counterexample", "\n".join(lines[:25])
    if "TEMPO SCADUTO" in messages:
        return "tempo scaduto", None
    if "maximum number of heartbeats" in messages:
        return "heartbeat esauriti", None
    if any(sign in messages for sign in SIGNS_OF_NOT_CLOSED):
        return "aperta", None
    return ("chiusa" if ok else "aperta"), None


def reclassify(path: Path) -> int:
    """Riapplica `classify` a un file di results gia' raccolto.

    Serve quando la rule_ di classificazione cambia: i messages di Lean sono
    conservati per gli results notable, quindi un verdict si puo' only_
    declassare, mai inventare.
    """
    data_ = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for entry in data_:
        for pr in entry["trials"]:
            if pr["result"] not in ("chiusa", "counterexample"):
                continue
            new_one, against = classify(pr.get("messages") or "", True)
            if new_one != pr["result"]:
                pr["result"], pr["counterexample"] = new_one, against
                changed += 1
        notable = [pr for pr in entry["trials"]
                    if pr["result"] in ("chiusa", "counterexample")]
        if notable:
            pr = notable[0]
            entry["ATTENZIONE"] = (f"la tactic {pr['tactic']} ha {pr['result']} la "
                                 f"forma {'negata' if pr['negated'] else 'diritta'}")
        else:
            entry.pop("ATTENZIONE", None)
    path.write_text(json.dumps(data_, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    return changed


def trial(problem, tactic_name, tactic, negated: bool, heartbeats: int,
          timeout: int) -> dict:
    """Prova one_ tactic sull'statement (o sulla sua negation)."""
    # Il `@` e' obbligatorio: senza, Lean istanzia gli arguments
    # impliciti come metavariabili e la probe trial un statement DIVERSO
    # da quello dell'archive. Senza di esso `aesop` "confutava" la
    # congettura di Agrawal, e il verifier vero rifiutava la stessa
    # dimostrazione: era il quarto falso positivo di questa specie.
    kind_ = f"type_of% @{problem.theorem}"
    statement = f"¬ ({kind_})" if negated else kind_
    code = TEMPLATE.format(utility=verifier_config.utility_module(),
                            module=problem.module, statement=statement,
                            tactic=tactic, heartbeats=heartbeats)
    t0 = time.time()
    r = explore.explore(code, timeout=timeout)
    duration = time.time() - t0
    messages = r.messages
    result, counterexample = classify(messages, r.ok)
    return {
        "tactic": tactic_name, "negated": negated, "result": result,
        "seconds": round(duration, 1),
        "counterexample": counterexample,
        "messages": messages[:1500] if result in ("chiusa", "counterexample") else "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--how_many", type=int, default=30)
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--heartbeats", type=int, default=400000)
    ap.add_argument("--output", default=str(ROOT / "runs" / "hunt" / "probe_lean.json"))
    ap.add_argument("--problems", default="")
    ap.add_argument("--reclassify", action="store_true",
                    help="riapplica il verdict a un file gia' raccolto")
    args = ap.parse_args()

    if args.reclassify:
        n = reclassify(Path(args.output))
        print(f"verdetti corretti: {n}")
        return 0

    idx = ProblemIndex.load()
    if args.problems:
        chosen = [idx.get(n) for n in args.problems.split()]
    else:
        # open_, verificabili, su oggetti discreti, statement short
        CONTINUOUS_SIGNALS = ["ℝ", "ℂ", "Real.", "Complex.", "Filter", "Tendsto",
                            "Measure", "Topological", "Continuous", "Cardinal",
                            "deriv", "∫", "Metric", "Manifold", "NNReal", "ENNReal"]
        DISCRETE_SIGNALS = ["ℕ", "ℤ", "Finset", "Fin ", "Nat.", "Int.", "SimpleGraph"]
        open_ = [p for p in idx.find(category="research open")
                  if not p.statement_has_sorry
                  and not any(s in p.statement for s in CONTINUOUS_SIGNALS)
                  and any(s in p.statement for s in DISCRETE_SIGNALS)]
        open_.sort(key=lambda p: len(p.statement))
        chosen = open_[:args.how_many]

    print(f"Sondo {len(chosen)} problems con {len(TACTICS)} tattiche x 2 forme.")
    print(f"Timeout per trial: {args.timeout}s. Nessuna spesa API.\n", flush=True)

    results = []
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    for i, p in enumerate(chosen, 1):
        entry = {"problem": p.theorem, "module": p.module,
                "statement": p.statement[:400], "trials": []}
        print(f"[{i}/{len(chosen)}] {p.theorem}", flush=True)
        for name, tactic in TACTICS:
            for negated in (False, True):
                e = trial(p, name, tactic, negated, args.heartbeats, args.timeout)
                entry["trials"].append(e)
                marchio = {"chiusa": "!!! CHIUSA !!!", "counterexample": "!!! CONTROESEMPIO !!!"}.get(
                    e["result"], "")
                forma = "¬" if negated else " "
                print(f"      {forma} {name:12} {e['result']:18} {e['seconds']:5.1f}s  {marchio}",
                      flush=True)
                if e["result"] in ("chiusa", "counterexample"):
                    entry["ATTENZIONE"] = (
                        f"la tactic {name} ha {e['result']} la forma "
                        f"{'negata' if negated else 'diritta'}")
        results.append(entry)
        output.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    notable = [v for v in results if "ATTENZIONE" in v]
    print(f"\n{'='*70}")
    print(f"Esaminati {len(results)} problems. Notevoli: {len(notable)}")
    for v in notable:
        print(f"  {v['problem']}: {v['ATTENZIONE']}")
    print(f"\nRisultati in {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
