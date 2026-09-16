"""
Esegue le ricerche di controesempi, in queue, con checkpoint e ripresa.

Non usa l'API e non costa niente: gira only_ sul computer.
Ogni ricerca lascia in runs/hunt/<name>/ il program, il log, il checkpoint
e un report leggibile.
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
    """La frase che dice il result_value in matematica, non in numbers d'index.

    "position raggiunta 216816" non dice niente a chi legge: quello che count_
    e' "nessun prime_ fino a 3 milioni". I fields disponibili sono quelli
    dell'result, le variables della ricerca e l'last_ event del log_.
    """
    model = definition.get("esito_in_parole")
    if not model:
        return ""
    fields = {"position": result.position, "examined": result.examined,
             "seconds": round(result.seconds)}
    fields.update(definition.get("variables", {}))
    log_ = ROOT / "runs" / "hunt" / name / "search.log"
    if log_.is_file():
        for line in log_.read_text(encoding="utf-8").splitlines():
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
    kind = definition.get("natura_trovati", "da interpretare")
    lines = [
        f"# Search: {name}", "",
        f"**Problema:** `{definition['problem']}`", "",
        f"**Cosa search_for:** {definition['descrizione']}", "",
        f"**State noto del problem:** {definition['stato_noto']}", "",
        f"**La ricerca è conclusiva?** {definition['conclusivo']}", "",
        "## Result", "",
        f"| | |", "|---|---|",
        f"| completed | {'sì' if result.completed else 'no, interrupted'} |",
        f"| duration | {result.seconds:.0f} s |",
        f"| position raggiunta | {result.position} |",
        f"| cases examined | {result.examined} |",
        f"| entries nella list_ dei results | {len(result.found)} |",
        f"| kind di quelle entries | {kind} |",
        "",
    ]
    if result.found and kind == "controesempi":
        lines += ["## Ritrovamenti", "",
                  "⚠️ Da sottoporre al protocollo della fase 7 before di crederci.", ""]
    elif result.found:
        lines += [f"## Risultati ({kind})", "",
                  "**Non sono ritrovamenti.** Questa ricerca non puo' produrre un",
                  "counterexample: quello che segue e' materiale da leggere, non one_",
                  "confutazione.", ""]
    if result.found:
        for t in result.found[:40]:
            lines.append(f"- `{json.dumps(t, ensure_ascii=False)}`")
        if len(result.found) > 40:
            lines.append(f"- ... e altri {len(result.found) - 40}")
    else:
        words = _in_words(name, definition, result)
        lines += ["## Ritrovamenti", "",
                  "Nessuno. **Non è un failure:** un result negativo dice fin",
                  "dove si è guardato, e quella è un'informazione.", ""]
        if words:
            lines += [f"**Che cosa si sa adesso:** {words}", ""]
        else:
            lines += [f"Punto reached: {result.position}.", ""]
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only_", default="", help="run_ only_ questa ricerca")
    ap.add_argument("--hours", type=float, default=0, help="tempo maximum per ricerca")
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--dacapo", action="store_true")
    ap.add_argument("--shakedown", action="store_true",
                    help="esecuzione breve, only_ per controllare che i programmi funzionino")
    args = ap.parse_args()

    names = [args.only_] if args.only_ else list(SEARCHES)
    seconds = args.hours * 3600 if args.hours else None
    if args.shakedown:
        seconds = 25

    print(f"Ricerche in queue: {len(names)}")
    print(f"Tempo maximum per ricerca: "
          f"{'illimitato' if seconds is None else f'{seconds:.0f}s'}")
    print("Costo in crediti API: ZERO\n", flush=True)

    summary = []
    for name in names:
        d = SEARCHES[name]
        variables = dict(d.get("variables", {}))
        if args.shakedown:
            # valori piccoli: serve only_ a vedere che il program parta e salvi
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
                          "natura_trovati": d.get("natura_trovati",
                                                  "da interpretare")})
        label = ("ritrovamenti" if d.get("natura_trovati") == "controesempi"
                     else "results (non ritrovamenti)")
        print(f"  -> {'completed' if result.completed else 'interrupted'}, "
              f"position {result.position}, {label} {len(result.found)}",
              flush=True)

    dest = ROOT / "runs" / "hunt" / "summary.json"
    dest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRiepilogo in {dest}")
    with_findings = [r for r in summary if r["found"]
                        and r.get("natura_trovati") == "controesempi"]
    if with_findings:
        print("\n*** RITROVAMENTI DA ESAMINARE ***")
        for r in with_findings:
            print(f"  {r['name']}: {r['found']}  -> runs/hunt/{r['name']}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
