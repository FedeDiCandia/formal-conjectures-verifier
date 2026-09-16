"""
Probe the open statements with automatic tactics, in direct and negated form.

THE IDEA
--------
Before writing a bespoke search program, it is worth asking Lean whether the answer
happens to be within reach of a tactic. Two tactics in particular:

  * `plausible` (from Mathlib) generates random cases and looks for a
    COUNTEREXAMPLE. If it finds one, the conjecture as formalised is false — which
    usually does not mean an open problem has been solved, but that an imprecise
    formalisation has been found. That is valuable information all the same.
  * `decide` closes decidable statements over finite domains. On an open problem it
    will almost never close, but if it does there is something to understand.

Two forms are tried: the statement as it stands, and its negation. An open problem
formalised as `True ↔ P` asserts that the answer is yes; if `plausible` finds a
counterexample to `P`, the answer might be no.

The timeout is deliberately SHORT: nothing is being solved here, we are looking for
the cases where the answer falls out on its own. Those that really need computation
go on to the next phase, with a bespoke program.
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

#: The tactics tried, in order of increasing cost.
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


#: `plausible` proves nothing: if it finds no counterexample it leaves the theorem
#: with a `sorry` and the file compiles anyway. Without this check an "Unable to
#: find a counter-example" would be read as a CLOSED statement, which is exactly the
#: error a project like this has to avoid.
SIGNS_OF_NOT_CLOSED = (
    "declaration uses 'sorry'",
    "Unable to find a counter-example",
    "Gave up",
)


def classify(messages: str, ok: bool) -> tuple[str, str | None]:
    """Give a verdict on Lean's messages. Returns (result, counterexample)."""
    if "Found a counter-example" in messages or "counterexample" in messages.lower():
        lines = [l for l in messages.split("\n") if l.strip()]
        return "counterexample", "\n".join(lines[:25])
    if "TIMED OUT" in messages:
        return "timed out", None
    if "maximum number of heartbeats" in messages:
        return "heartbeats exhausted", None
    if any(sign in messages for sign in SIGNS_OF_NOT_CLOSED):
        return "open", None
    return ("closed" if ok else "open"), None


def reclassify(path: Path) -> int:
    """Re-apply `classify` to a file of results already collected.

    This is for when the classification rule changes: Lean's messages are kept for
    the notable results, so a verdict can only be downgraded, never invented.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for entry in data:
        for pr in entry["trials"]:
            if pr["result"] not in ("closed", "counterexample"):
                continue
            new_item, against = classify(pr.get("messages") or "", True)
            if new_item != pr["result"]:
                pr["result"], pr["counterexample"] = new_item, against
                changed += 1
        notable = [pr for pr in entry["trials"]
                   if pr["result"] in ("closed", "counterexample")]
        if notable:
            pr = notable[0]
            entry["ATTENTION"] = (f"the tactic {pr['tactic']} returned {pr['result']} on "
                                  f"the {'negated' if pr['negated'] else 'direct'} form")
        else:
            entry.pop("ATTENTION", None)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    return changed


def trial(problem, tactic_name, tactic, negated: bool, heartbeats: int,
          timeout: int) -> dict:
    """Try one tactic on the statement (or on its negation)."""
    # The `@` is compulsory: without it Lean instantiates the implicit arguments as
    # metavariables and the probe tries a DIFFERENT statement from the archive's.
    # Without it `aesop` "refuted" Agrawal's conjecture, and the real verifier
    # rejected the same proof: that was the fourth false positive of this species.
    kind = f"type_of% @{problem.theorem}"
    statement = f"¬ ({kind})" if negated else kind
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
        "messages": messages[:1500] if result in ("closed", "counterexample") else "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--how-many", type=int, default=30, dest="how_many")
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--heartbeats", type=int, default=400000)
    ap.add_argument("--output", default=str(ROOT / "runs" / "hunt" / "probe_lean.json"))
    ap.add_argument("--problems", default="")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-apply the verdict rule to a file already collected")
    args = ap.parse_args()

    if args.reclassify:
        n = reclassify(Path(args.output))
        print(f"verdicts corrected: {n}")
        return 0

    idx = ProblemIndex.load()
    if args.problems:
        chosen = [idx.get(n) for n in args.problems.split()]
    else:
        # open, verifiable, about discrete objects, with a short statement
        CONTINUOUS_SIGNALS = ["ℝ", "ℂ", "Real.", "Complex.", "Filter", "Tendsto",
                            "Measure", "Topological", "Continuous", "Cardinal",
                            "deriv", "∫", "Metric", "Manifold", "NNReal", "ENNReal"]
        DISCRETE_SIGNALS = ["ℕ", "ℤ", "Finset", "Fin ", "Nat.", "Int.", "SimpleGraph"]
        open_problems = [p for p in idx.find(category="research open")
                  if not p.statement_has_sorry
                  and not any(s in p.statement for s in CONTINUOUS_SIGNALS)
                  and any(s in p.statement for s in DISCRETE_SIGNALS)]
        open_problems.sort(key=lambda p: len(p.statement))
        chosen = open_problems[:args.how_many]

    print(f"Probing {len(chosen)} problems with {len(TACTICS)} tactics x 2 forms.")
    print(f"Timeout per attempt: {args.timeout}s. No API spend.\n", flush=True)

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
                mark = {"closed": "!!! CLOSED !!!",
                        "counterexample": "!!! COUNTEREXAMPLE !!!"}.get(e["result"], "")
                form = "¬" if negated else " "
                print(f"      {form} {name:12} {e['result']:18} {e['seconds']:5.1f}s  {mark}",
                      flush=True)
                if e["result"] in ("closed", "counterexample"):
                    entry["ATTENTION"] = (
                        f"the tactic {name} returned {e['result']} on the "
                        f"{'negated' if negated else 'direct'} form")
        results.append(entry)
        output.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    notable = [v for v in results if "ATTENTION" in v]
    print(f"\n{'='*70}")
    print(f"Examined {len(results)} problems. Notable: {len(notable)}")
    for v in notable:
        print(f"  {v['problem']}: {v['ATTENTION']}")
    print(f"\nResults in {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
