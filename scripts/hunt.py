"""
Run the counterexample searches, one after another, with checkpoints and resumption.

It does not use the API and costs nothing: it runs entirely on the machine.
Each search leaves its program, log, checkpoint and a readable report in
runs/hunt/<name>/.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "scripts"))

import search as search_module
from hunt_programs import SEARCHES


def _in_words(name: str, definition: dict, result) -> str:
    """The sentence that states the result in mathematics, not in index numbers.

    "position reached 216816" says nothing to a reader: what counts is "no prime up
    to 3 million". The fields available are those of the result, the search's
    variables, and the last event in the log.
    """
    model = definition.get("result_in_words")
    if not model:
        return ""
    fields = {"position": result.position, "examined": result.examined,
             "seconds": round(result.seconds)}
    fields.update(definition.get("variables", {}))
    log = ROOT / "runs" / "hunt" / name / "search.log"
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    fields.update(json.loads(line))
                except ValueError:
                    pass
    try:
        return model.format(**fields)
    except KeyError:
        return ""


def report(name: str, definition: dict, result) -> str:
    kind = definition.get("nature_of_findings", "da interpretare")
    lines = [
        f"# Search: {name}", "",
        f"**Problema:** `{definition['problem']}`", "",
        f"**Cosa search_for:** {definition['description']}", "",
        f"**State noto del problem:** {definition['known_state']}", "",
        f"**Is the search conclusive?** {definition['conclusive']}", "",
        "## Result", "",
        f"| | |", "|---|---|",
        f"| completed | {'sì' if result.completed else 'no, interrupted'} |",
        f"| duration | {result.seconds:.0f} s |",
        f"| position raggiunta | {result.position} |",
        f"| cases examined | {result.examined} |",
        f"| entries in the result list | {len(result.found)} |",
        f"| kind di quelle entries | {kind} |",
        "",
    ]
    if result.found and kind == "counterexamples":
        lines += ["## Ritrovamenti", "",
                  "⚠️ To be put through the finding protocol before believing it.", ""]
    elif result.found:
        lines += [f"## Risultati ({kind})", "",
                  "**These are not findings.** This search cannot produce a",
                  "counterexample: what follows is material to read, not a",
                  "confutazione.", ""]
    if result.found:
        for t in result.found[:40]:
            lines.append(f"- `{json.dumps(t, ensure_ascii=False)}`")
        if len(result.found) > 40:
            lines.append(f"- ... and {len(result.found) - 40} more")
    else:
        words = _in_words(name, definition, result)
        lines += ["## Ritrovamenti", "",
                  "None. **This is not a failure:** a negative outcome says how far",
                  "one has looked, and that is information.", ""]
        if words:
            lines += [f"**What is known now:** {words}", ""]
        else:
            lines += [f"Punto reached: {result.position}.", ""]
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="run only this search")
    ap.add_argument("--hours", type=float, default=0, help="time limit per search")
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--dacapo", action="store_true")
    ap.add_argument("--shakedown", action="store_true",
                    help="a short run, only to check that the programs work")
    args = ap.parse_args()

    names = [args.only] if args.only else list(SEARCHES)
    seconds = args.hours * 3600 if args.hours else None
    if args.shakedown:
        seconds = 25

    print(f"Ricerche in queue: {len(names)}")
    print(f"Time limit per search: "
          f"{'illimitato' if seconds is None else f'{seconds:.0f}s'}")
    print("Costo in crediti API: ZERO\n", flush=True)

    summary = []
    for name in names:
        d = SEARCHES[name]
        variables = dict(d.get("variables", {}))
        if args.shakedown:
            # small values: this only checks that the program starts and saves
            for k, v in list(variables.items()):
                if isinstance(v, int) and v > 1000:
                    variables[k] = 2000
        print(f"{'='*70}\n{name}\n{'='*70}", flush=True)
        r = search_module.Search(name, d["program"],
                                   folder=ROOT / "runs" / "hunt" / name,
                                   variables=variables)
        result = r.run(max_seconds=seconds, resume=not args.dacapo)
        (r.folder / "report.md").write_text(report(name, d, result), encoding="utf-8")
        summary.append({"name": name, "completed": result.completed,
                          "position": result.position, "examined": result.examined,
                          "found": len(result.found), "seconds": round(result.seconds),
                          "nature_of_findings": d.get("nature_of_findings",
                                                  "da interpretare")})
        label = ("findings" if d.get("nature_of_findings") == "counterexamples"
                     else "computed results (not findings)")
        print(f"  -> {'completed' if result.completed else 'interrupted'}, "
              f"position {result.position}, {label} {len(result.found)}",
              flush=True)

    dest = ROOT / "runs" / "hunt" / "summary.json"
    dest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRiepilogo in {dest}")
    with_findings = [r for r in summary if r["found"]
                        and r.get("nature_of_findings") == "counterexamples"]
    if with_findings:
        print("\n*** RITROVAMENTI DA ESAMINARE ***")
        for r in with_findings:
            print(f"  {r['name']}: {r['found']}  -> runs/hunt/{r['name']}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
