#!/usr/bin/env python3
"""
Legge il report di un giro dell'agent sulle trials note e ne ricava i numbers
del punto 2 (misura) e del punto 3 (proiezione).

Ogni number viene dal report JSON scritto da agent/agent.py o dall'listing dei
candidates di scripts/select_formalisations.py: niente ricopiato a mano.

LIMIT DICHIARATO DI QUESTO GIRO: e' state lanciato con `--quiet`, quindi
il log non contiene i messages di error di Lean. La diagnosi dei fallimenti
si fa sulla kind delle checks consegnate (non compila / compila con un buco /
statement diverso) e sul riassunto del reasoning del model, iteration per
iteration, che il report conserva.

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

#: segni, nel reasoning del model, di un ostacolo di API e non di matematica
_API = re.compile(r"unknown (identifier|constant)|not found|doesn't exist|does not exist|"
                  r"deprecated|renamed|failed to synthesize|instance|coercion|cast|"
                  r"Mathlib (lemma|name|API)|lemma name|exact\?|apply\?|simp lemma|"
                  r"typeclass|elaborat|universe|Decidable", re.I)
#: segni di un ostacolo matematico
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
    if c["categoria"] == "textbook" and not hard:
        return "B"
    if not hard:
        return "C"
    if hard == {"source: articolo"}:
        return "D"
    return "E"


DESCRIZIONE = {
    "A": "la source dice che la trial e' corta, niente di hard",
    "B": "textbook, niente di hard",
    "C": "research solved senza segnali",
    "D": "trial citata da un articolo",
    "E": "segnali duri (theorem profondo, infinito/analisi, computation grande)",
}


def ostacolo(t: dict) -> str:
    """Matematica, API di Mathlib, o indeterminato, dal reasoning e dalle checks."""
    if t["solved"]:
        return "-"
    if not t.get("iteration_detail"):
        return (f"non determinabile dal report ({t.get('source', 'niente detail')}); "
                f"{t['explorations']} explorations, {t['checks']} checks")
    text =" ".join(it.get("reasoning", "") for it in t["iteration_detail"])
    api, mate = len(_API.findall(text)), len(_MATE.findall(text))
    nat = t.get("verifications_by_kind") or {}
    if not t["checks"]:
        base = "nessun candidato consegnato"
    elif nat.get("buco_o_assioma") or nat.get("enunciato_sbagliato"):
        base = "ha compilato, la trial non c'era"
    else:
        base = "i candidates non compilavano"
    if api > 2 * max(mate, 1):
        verdict = "API di Mathlib"
    elif mate > api:
        verdict = "matematica"
    else:
        verdict = "misto"
    return f"{verdict} ({base}; segni API {api}, segni matematica {mate})"


def main() -> int:
    # Piu' reports si sommano, nell'order dato: il giro del 12 settembre e' state
    # interrotto da un error di rete ed e' ripreso in un second processo.
    reports = [json.loads(Path(a).read_text(encoding="utf-8")) for a in sys.argv[1:]]
    report = reports[0]
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    by_name = {c["problem"]: c for c in candidates}
    attempts = [t for r in reports for t in r["attempts"]]
    spent = sum(r["spent"] for r in reports)
    non_registrato = sum(1.0 for r in reports if r.get("interruzione"))

    print(f"model {report['model']}, effort {report['effort']}, istruzioni "
          f"{report['instructions']}, cap ${report['problem_cap']:.2f}")
    print(f"spesa misurata: ${spent:.4f}" + (
        f"  + al maximum ${non_registrato:.2f} non registrati (attempts interrotti "
        f"dalla rete: {', '.join(r['interruzione']['problem'] for r in reports if r.get('interruzione'))})"
        if non_registrato else ""))
    print()
    print(f"{'#':>2} {'band':6} {'result':11} {'cost':>7} {'it':>3} {'ver':>3}  problem")
    for i, t in enumerate(attempts, 1):
        f = band(by_name[t["problem"]]) if t["problem"] in by_name else "?"
        print(f"{i:2d} {f:6} {'ACCEPTED' if t['solved'] else 'non chiuso':11} "
              f"${t['cost']:6.3f} {t['iterations']:3d} {t['checks']:3d}  {t['problem']}")
        if not t["solved"]:
            print(f"{'':26}{t['reason'][:90]}")
            print(f"{'':26}ostacolo: {ostacolo(t)}")

    solved = [t for t in attempts if t["solved"]]
    # la spesa dei attempts interrotti non e' registrata: si count al suo maximum
    spesa = spent + non_registrato
    print(f"\nACCETTATI DAL VERIFICATORE: {len(solved)} su {len(set(t['problem'] for t in attempts))} "
          f"problems tentati")
    if solved:
        print(f"cost per successo (spesa total / successi): ${spesa / len(solved):.3f}"
              + (" (con la spesa non registrata al maximum)" if non_registrato else ""))
        print(f"cost mean di un successo, da only: "
              f"${sum(t['cost'] for t in solved) / len(solved):.3f}")
    failed = [t for t in attempts if not t["solved"]]
    if failed:
        print(f"cost mean di un failure: ${sum(t['cost'] for t in failed) / len(failed):.3f}")

    # --- proiezione
    rate: dict[str, tuple[int, int]] = {}
    for t in attempts:
        if t["problem"] in by_name:
            f = band(by_name[t["problem"]])
            ok, n = rate.get(f, (0, 0))
            rate[f] = (ok + t["solved"], n + 1)
    count = collections.Counter(band(c) for c in candidates)
    print("\nPROIEZIONE PER FASCIA")
    for f in "ABCDE":
        ok, n = rate.get(f, (0, 0))
        misurato = f"{ok}/{n} misurati" if n else "non misurata"
        print(f"  {f} {count[f]:5d} candidates  {misurato:15s}  {DESCRIZIONE[f]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
