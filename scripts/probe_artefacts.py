"""
Look for the formalisations that give way to a defect rather than to mathematics.

WHERE THIS IDEA COMES FROM
--------------------------
Reading the ACCEPTED solutions of Epoch AI's OEIS Open benchmark shows that their 30%
of successes is not all mathematics. Three real examples, from their files:

  * `A211420_general_divisibility_conjecture` proved with `exact ⟨0, fun n => by simp⟩`:
    the statement said "there exists C such that for every n ... divides C * a(n)",
    and with C = 0 it is true for nothing. That was not the mathematical conjecture.
  * `A262403_conjecture_ii_distinctness` refuted because two boundary cases give the
    same value.
  * `A070823_conjecture` refuted with a small counterexample (n = 20), found by
    computation and checked with `decide`.

The first two are **faulty formalisations**, to be reported to the archive's authors
and not passed off as results; the third is a real counterexample. All three are found
with zero-cost tactics, with no API.

WHY ONE FILE PER PROBLEM
------------------------
Every compilation pays ~6 seconds of Mathlib imports. Trying twenty tactics in twenty
files costs twenty times that wait; putting them in the same file pays it once. Lean
declarations are independent: if one does not close, the error concerns it and the
others carry on. Each message is traced back to the tactic that produced it through
its line.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "scripts"))

import config as verifier_config   # noqa: E402
import explore                          # noqa: E402
from index import ProblemIndex          # noqa: E402

#: (name, tactic, also_on_the_negation). The order no longer matters: everything is
#: everything at once.
TACTICS = [
    ("testimone_zero",   "exact ⟨0, by simp⟩",            False),
    ("testimone_zero_d", "exact ⟨0, by decide⟩",          False),
    ("testimone_vuoto",  "exact ⟨∅, by simp⟩",            False),
    ("simp",             "simp",                          True),
    ("simp_arith",       "simp +arith",                   True),
    ("decide",           "decide",                        True),
    ("norm_num",         "norm_num",                      True),
    ("omega",            "omega",                         True),
    ("aesop",            "aesop",                         True),
    ("trivial",          "trivial",                       True),
    ("plausible",        "plausible",                     True),
]


def build(problem, heartbeats: int) -> tuple[str, dict[str, tuple[str, bool]]]:
    """The file with all the attempts, and the map theorem name -> (tactic, negated).

    After each attempt the file asks Lean for **the axioms** of that attempt. That is
    the decisive criterion, and it is the verifier's: a tactic has really closed the
    statement only if the resulting declaration does NOT depend on `sorryAx`. Counting
    error messages is not enough — a tactic that failed sometimes produced an error
    attributed to another line, and the attempt looked successful. With
    `#print axioms` the answer comes by name, not by position.
    """
    lines = [f"import {verifier_config.utility_module()}",
             f"import {problem.module}", ""]
    mapping: dict[str, tuple[str, bool]] = {}
    # The `@` is compulsory: without it Lean instantiates the implicit arguments as
    # metavariables and the probe tries a DIFFERENT statement from the archive's.
    # Without it `aesop` "refuted" Agrawal's conjecture, and the real verifier rejected
    # the same proof: that was the fourth false positive of this species.
    kind = f"type_of% @{problem.theorem}"
    for name, tactic, also_negated in TACTICS:
        for negated in (False, True) if also_negated else (False,):
            statement = f"¬ ({kind})" if negated else kind
            theorem = f"probe{name}{'_neg' if negated else ''}"
            mapping[theorem] = (name, negated)
            lines.append(f"set_option maxHeartbeats {heartbeats} in")
            lines.append(f"theorem {theorem} : {statement} := by")
            lines.append(f"  {tactic}")
            lines.append(f"#print axioms {theorem}")
            lines.append("")
    return "\n".join(lines) + "\n", mapping


#: `#print axioms name` prints a line of this shape.
_RE_AXIOMS = re.compile(r"'(\S+)' depends on axioms: \[([^\]]*)\]")
_RE_SENZA = re.compile(r"'(\S+)' does not depend on any axioms")
_RE_COUNTEREXAMPLE = re.compile(r"Found a counter-example", re.I)


def read(output: str, mapping: dict[str, tuple[str, bool]]) -> dict:
    """Give each tactic its verdict by reading the axioms, by name.

    The rule: a tactic has CLOSED the statement if the corresponding declaration
    exists and does not depend on `sorryAx`. If it depends on `sorryAx` the tactic
    proved nothing — that is `plausible`'s case, which when it finds no counterexample
    leaves a `sorry` and lets the file compile anyway. If the declaration does not
    appear among the printed axioms, the attempt failed before
    di arrivare a esistere.
    """
    axioms: dict[str, set[str]] = {}
    for line in output.split("\n"):
        m = _RE_AXIOMS.search(line)
        if m:
            axioms[m.group(1)] = {a.strip() for a in m.group(2).split(",") if a.strip()}
            continue
        m = _RE_SENZA.search(line)
        if m:
            axioms[m.group(1)] = set()
    counterexample = bool(_RE_COUNTEREXAMPLE.search(output))
    # A file that does not compile can still print a clean axiom line for a
    # declaration whose elaboration was salvaged: that is the case of
    # Erdos628.erdos_628, where `aesop` came out "closed, no axioms" while the file
    # had a notation error and the verifier then answered REJECTED: the file does not
    # compile. The probe must never show a positive result without this warning
    # beside it.
    errors = [r for r in output.split("\n") if " error: " in r or r.startswith("error:")]

    results = []
    for theorem, (name, negated) in mapping.items():
        ax = axioms.get(theorem)
        if ax is None:
            result, detail = "open", "the declaration does not exist: the tactic failed"
        elif "sorryAx" in ax:
            result, detail = "open", "depends on sorryAx: it proved nothing"
        else:
            result = "refuted" if negated else "closed"
            detail = "axioms: " + (", ".join(sorted(ax)) or "none")
            if errors:
                detail = (f"ATTENTION: the file contains {len(errors)} compilation "
                          f"errors, so this result is worth nothing until the verifier "
                          f"says ACCEPTED. "
                          f"First error: {errors[0].strip()[:160]}. " + detail)
        results.append({"tactic": name, "negated": negated, "result": result,
                      "detail": detail})
    if counterexample:
        results.append({"tactic": "plausible", "negated": None,
                      "result": "counterexample",
                      "detail": "plausible exhibited a counterexample: "
                                   "vedi i messages grezzi"})
    return {"trials": results}


def check_environment(targets: Path) -> None:
    """The targets and the archive have to come from the same snapshot.

    Fifth false positive: the probe was running with the default index (bench-v1)
    while the targets had been chosen on `main`. The imports failed, Lean's messages
    were rubbish, and the reader read successes into them.
    """
    data = json.loads(targets.read_text(encoding="utf-8"))
    expected = data.get("snapshot", "")
    current_one = str(verifier_config.ARCHIVE)
    if "fc-main" in expected and "fc-main" not in current_one:
        raise SystemExit(
            f"AMBIENTE SBAGLIATO.\n"
            f"  the targets were chosen on: {expected}\n"
            f"  l'archive in uso e':           {current_one}\n"
            f"Relaunch with:\n"
            f"  env FCS_ARCHIVE=$PWD/external/fc-main \\\n"
            f"      FCS_LEAN4EXPORT=$PWD/external/lean4export-433/.lake/build/bin/lean4export \\\n"
            f"      FCS_INDEX=$PWD/verifier/problem_index_main.json \\\n"
            f"    ./.venv/bin/python scripts/probe_artefacts.py")


def confirm_with_verifier(problem, tactic: str, negated: bool,
                              timeout: int) -> tuple[str, str]:
    """Submit the attempt to the real verifier. Returns (result, detail).

    It is the only judgement that counts. The candidate is written in the form
    `verify.py` expects: in refutation mode it is allowed to import the problem's
    module (and leaning on its proof is no use, because it is a `sorry` and the axiom
    check rejects it).
    """
    import tempfile
    from verify import verify, REFUTATION, STRICT
    body = (f"import {verifier_config.utility_module()}\n"
             f"import {problem.module}\n\n")
    if negated:
        name = f"{problem.theorem}_refutation"
        body += (f"theorem {name} : ¬ (type_of% @{problem.theorem}) := by\n"
                  f"  {tactic}\n")
        mode = REFUTATION
    else:
        name = f"{problem.theorem}_riprova"
        body += (f"theorem {name} : type_of% @{problem.theorem} := by\n"
                  f"  {tactic}\n")
        mode = STRICT
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False,
                                    encoding="utf-8") as fh:
        fh.write(body)
        path = Path(fh.name)
    try:
        r = verify(problem.theorem, path, mode=mode,
                   run_guard=False, timeout=timeout)
        return r.status, (r.message or "")[:300]
    finally:
        path.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default=str(ROOT / "docs/data/targets.json"))
    ap.add_argument("--how_many", type=int, default=0, help="0 = all_items")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--heartbeats", type=int, default=200000)
    ap.add_argument("--output", default=str(ROOT / "runs/hunt/artefacts.json"))
    args = ap.parse_args()

    check_environment(Path(args.targets))
    idx = ProblemIndex.load()
    data = json.loads(Path(args.targets).read_text(encoding="utf-8"))
    chosen = []
    for c in data["candidates"]:
        try:
            chosen.append(idx.get(c["problem"]))
        except Exception:
            continue

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else []
    seen = {v["problem"] for v in results}
    chosen = [p for p in chosen if p.theorem not in seen]
    if args.how_many:
        chosen = chosen[:args.how_many]

    print(f"Probing {len(chosen)} statements, {len(TACTICS)} tactics in ONE file each.")
    print(f"Already done: {len(seen)}. No API spend.\n", flush=True)

    notable = 0
    for i, p in enumerate(chosen, 1):
        t0 = time.time()
        code, mapping = build(p, args.heartbeats)
        r = explore.explore(code, timeout=args.timeout)
        entry = {"problem": p.theorem, "module": p.module,
                "statement": p.statement[:300], "seconds": round(time.time() - t0, 1)}
        if r.rejected_by_guard:
            entry["error"] = f"guard: {r.rejected_by_guard}"
        else:
            entry.update(read(r.messages, mapping))
            candidates = [x for x in entry["trials"]
                         if x["result"] in ("closed", "refuted", "counterexample")]
            if candidates:
                entry["messaggi_grezzi"] = r.messages[:20000]
                entry["candidates"] = []
                for x in candidates:
                    if x["result"] == "counterexample":
                        continue          # a counterexample is not a proof
                    tactic = dict((n, t) for n, t, _ in TACTICS)[x["tactic"]]
                    print(f"  ? {p.theorem}: {x['tactic']}"
                          f"{' (negata)' if x['negated'] else ''} sembra chiudere — "
                          f"submitting it to the verifier...", flush=True)
                    result, detail = confirm_with_verifier(
                        p, tactic, x["negated"], args.timeout * 4)
                    entry["candidates"].append(
                        {"tactic": x["tactic"], "negated": x["negated"],
                         "verifier": result, "detail": detail})
                    print(f"    -> verifier: {result}", flush=True)
                    if result == "ACCEPTED":
                        entry["ATTENTION"] = (
                            f"{x['tactic']}{' (negata)' if x['negated'] else ''} "
                            f"ACCETTATA DAL VERIFICATORE")
                if "ATTENTION" in entry:
                    notable += 1
                    print(f"  !!! {p.theorem}: {entry['ATTENTION']}", flush=True)
        results.append(entry)
        output.write_text(json.dumps(results, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"[{i}/{len(chosen)}] {p.theorem[:54]:54} "
              f"{'NOTABLE' if 'ATTENTION' in entry else '.':9} {entry['seconds']:6.0f}s",
              flush=True)

    print(f"\n{'='*70}\nEsaminati {len(chosen)}. Notevoli: {notable}\nRisultati in {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
