#!/usr/bin/env python3
"""
Read the report of an agent run on known proofs and derive the numbers
del punto 2 (misura) e del punto 3 (proiezione).

Every number comes from the JSON report written by agent/agent.py or from the list
candidates in scripts/select_formalisations.py: nothing copied by hand.

A DECLARED LIMIT OF THIS RUN: it was launched with `--quiet`, so the log
does not contain Lean's error messages. Failures are diagnosed from the kind of
verifications submitted (does not compile / compiles with a hole / different
statement) and from the summary of the model's reasoning, iteration by
iteration, which the report keeps.

Uso:
  .venv/bin/python scripts/measure_formalisations.py runs/formalizzazioni-lotto20.json
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = ROOT / "research_data" / "formalizzazioni_candidati.json"

#: signs, in the model's reasoning, of an API obstacle rather than a mathematical one
_API = re.compile(r"unknown (identifier|constant)|not found|doesn't exist|does not exist|"
                  r"deprecated|renamed|failed to synthesize|instance|coercion|cast|"
                  r"Mathlib (lemma|name|API)|lemma name|exact\?|apply\?|simp lemma|"
                  r"typeclass|elaborat|universe|Decidable", re.I)
#: signs of a mathematical obstacle
_MATE = re.compile(r"(don't|do not|can't|cannot) (see|find) (a|the|how)|need(s)? a (proof|argument)|"
                   r"key (step|lemma|difficulty)|not (true|obvious)|counterexample|"
                   r"hard(er)? than|deep|requires? (a|the) (theorem|result)|"
                   r"false as stated|misformaliz", re.I)


def band(c: dict) -> str:
    m = set(c["reasons"])
    hard = m & {"source: articolo", "source: theorem profondo",
                "statement: infinito/analisi", "computation grande"}
    if "source: trial corta" in m and not hard:
        return "A"
    if c["category"] == "textbook" and not hard:
        return "B"
    if not hard:
        return "C"
    if hard == {"source: articolo"}:
        return "D"
    return "E"


DESCRIPTION = {
    "A": "the source says the proof is short, nothing hard",
    "B": "textbook, nothing hard",
    "C": "research solved, no signal",
    "D": "proof cited from a paper",
    "E": "segnali duri (theorem profondo, infinito/analisi, computation grande)",
}


def ostacolo(t: dict) -> str:
    """Matematica, API di Mathlib, o indeterminato, dal reasoning e dalle checks."""
    if t["solved"]:
        return "-"
    if not t.get("iteration_detail"):
        return (f"not determinable from the report ({t.get('source', 'no detail')}); "
                f"{t['explorations']} explorations, {t['checks']} checks")
    text =" ".join(it.get("reasoning", "") for it in t["iteration_detail"])
    api, mate = len(_API.findall(text)), len(_MATE.findall(text))
    nat = t.get("verifications_by_kind") or {}
    if not t["checks"]:
        base = "no candidate submitted"
    elif nat.get("buco_o_assioma") or nat.get("enunciato_sbagliato"):
        base = "it compiled, the proof was not there"
    else:
        base = "the candidates did not compile"
    if api > 2 * max(mate, 1):
        verdict = "API di Mathlib"
    elif mate > api:
        verdict = "matematica"
    else:
        verdict = "misto"
    return f"{verdict} ({base}; segni API {api}, segni matematica {mate})"


def main() -> int:
    # Several reports are summed, in the order given: the run of 12 September was
    # interrupted by a network error and resumed in a second process.
    reports = [json.loads(Path(a).read_text(encoding="utf-8")) for a in sys.argv[1:]]
    report = reports[0]
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    by_name = {c["problem"]: c for c in candidates}
    attempts = [t for r in reports for t in r["attempts"]]
    spent = sum(r["spent"] for r in reports)
    unrecorded = sum(1.0 for r in reports if r.get("interruption"))

    print(f"model {report['model']}, effort {report['effort']}, istruzioni "
          f"{report['instructions']}, cap ${report['problem_cap']:.2f}")
    print(f"spend misurata: ${spent:.4f}" + (
        f"  + at most ${unrecorded:.2f} unrecorded (interrupted attempts "
        f"dalla rete: {', '.join(r['interruption']['problem'] for r in reports if r.get('interruption'))})"
        if unrecorded else ""))
    print()
    print(f"{'#':>2} {'band':6} {'result':11} {'cost':>7} {'it':>3} {'ver':>3}  problem")
    for i, t in enumerate(attempts, 1):
        f = band(by_name[t["problem"]]) if t["problem"] in by_name else "?"
        print(f"{i:2d} {f:6} {'ACCEPTED' if t['solved'] else 'not closed':11} "
              f"${t['cost']:6.3f} {t['iterations']:3d} {t['checks']:3d}  {t['problem']}")
        if not t["solved"]:
            print(f"{'':26}{t['reason'][:90]}")
            print(f"{'':26}ostacolo: {ostacolo(t)}")

    solved = [t for t in attempts if t["solved"]]
    # the spend of interrupted attempts is unrecorded: it is counted at its maximum
    spend = spent + unrecorded
    print(f"\nACCETTATI DAL VERIFICATORE: {len(solved)} su {len(set(t['problem'] for t in attempts))} "
          f"problems tentati")
    if solved:
        print(f"cost per success (total spend / successes): ${spend / len(solved):.3f}"
              + (" (with the unrecorded spend at its maximum)" if unrecorded else ""))
        print(f"mean cost of a success, on its own: "
              f"${sum(t['cost'] for t in solved) / len(solved):.3f}")
    failed = [t for t in attempts if not t["solved"]]
    if failed:
        print(f"mean cost of a failure: ${sum(t['cost'] for t in failed) / len(failed):.3f}")

    # --- proiezione
    rate: dict[str, tuple[int, int]] = {}
    for t in attempts:
        if t["problem"] in by_name:
            f = band(by_name[t["problem"]])
            ok, n = rate.get(f, (0, 0))
            rate[f] = (ok + t["solved"], n + 1)
    count = collections.Counter(band(c) for c in candidates)
    print("\nPROJECTION BY BAND")
    for f in "ABCDE":
        ok, n = rate.get(f, (0, 0))
        measured = f"{ok}/{n} measured" if n else "not measured"
        print(f"  {f} {count[f]:5d} candidates  {measured:15s}  {DESCRIPTION[f]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
