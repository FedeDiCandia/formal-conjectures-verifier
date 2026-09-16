"""
Sceglie i problems su cui calibrare l'agent.

Un problem enters nella calibrazione only_ se soddisfa TUTTE queste condizioni:

1. l'archive ne fornisce one_ dimostrazione (non e' un problem aperto);
2. quella dimostrazione usa only_ gli axioms permitted (niente native_decide,
   niente sorryAx ereditato da un lemma);
3. quella dimostrazione, estratta e compilata da sola, viene ACCETTATA da
   verify.py. E' il controllo che count_: i primes two sono necessari ma non
   sufficienti.

Per ciascuno si riportano:
- il LIVELLO DI DIFFICOLTA', dalla length della dimostrazione esistente;
- la DATA in cui la dimostrazione e' entrata nell'archive pubblico;
- il RISCHIO DI MEMORIZZAZIONE, confrontando quella data con la data di cut
  dell'addestramento del model;
- l'ESITO della check della dimostrazione d'archive.

Sul risk di memorizzazione, one_ precisazione doverosa: il cut dichiarato
per claude-opus-5 e' maggio 2026. Il tag di benchmark bench-v1-lean4.27.0 e' del
6 maggio 2026, quindi OGNI dimostrazione contenuta in quel tag e' anteriore al
cut. Calibrare li' misura also_ quanto il model ricorda. Per avere problems
post-cut serve lo snapshot da main (vedi scripts/setup_snapshot_main.sh).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "agent"))

import config
from index import ProblemIndex
from hide import _separator_position

#: Taglio dell'addestramento di claude-opus-5, come dichiarato dal model.
CUT = "2026-05"


def proof_lines(p) -> int:
    try:
        src = p.source_text()
        pos = _separator_position(src)
        return src[pos + 2:].strip().count("\n") + 1 if pos is not None else -1
    except Exception:
        return -1


def level(n: int) -> str:
    if n <= 0:
        return "?"
    return "facile" if n <= 3 else "mean_" if n <= 12 else "difficile"


def git(archive: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(archive), *args],
                          capture_output=True, text=True).stdout


def proof_date(p, archive: Path) -> tuple[str, str]:
    """(data, method) in cui la dimostrazione e' entrata nell'archive."""
    try:
        rel = str(p.source_file.relative_to(archive))
    except ValueError:
        return "?", "file out_of dall'archive"
    try:
        src = p.source_text()
        pos = _separator_position(src)
        trial = src[pos + 2:] if pos is not None else ""
    except Exception:
        trial = ""
    lines = [r.strip() for r in trial.split("\n")]
    lines = [r for r in lines if len(r) >= 18 and not r.startswith("--") and "sorry" not in r]
    if lines:
        line = max(lines, key=len)
        out = git(archive, "log", "--format=%ci|%h", "-S", line, "--", rel).strip().splitlines()
        if out:
            return out[-1].split("|")[0][:10], "before comparsa della line di trial"
    out = git(archive, "log", "--format=%ci|%h", "--diff-filter=A", "--", rel).strip().splitlines()
    if out:
        return out[-1].split("|")[0][:10], "creazione del file"
    return "?", "sconosciuto"


def risk(data: str) -> str:
    if data == "?":
        return "ignoto"
    if data < CUT:
        return "ALTO"
    if data < "2026-07":
        return "INCERTO"
    return "BASSO"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checks", default=str(ROOT / "runs" / "archive_proofs.json"),
                    help="results della check delle trials d'archive")
    ap.add_argument("--how_many-per-level", type=int, default=3)
    ap.add_argument("--output", default=str(ROOT / "runs" / "calibration_selection.json"))
    args = ap.parse_args()

    idx = ProblemIndex.load()
    archive = config.ARCHIVE

    verified: dict[str, dict] = {}
    f = Path(args.checks)
    if f.is_file():
        for d in json.loads(f.read_text(encoding="utf-8")):
            verified[d["problem"]] = d
    else:
        print(f"ATTENZIONE: {f} non esiste. Senza le checks non posso dire")
        print("which_ones dimostrazioni d'archive passano davvero il verifier.")

    lines = []
    for p in idx.find(archive_proof_clean=True):
        if p.statement_has_sorry:
            continue
        v = verified.get(p.theorem)
        result = v["result"] if v else "non verificata"
        if result != "ACCETTATO":
            continue
        n = proof_lines(p)
        data, method = proof_date(p, archive)
        lines.append({
            "problem": p.theorem, "module": p.module, "categoria": p.category,
            "proof_lines": n, "level": level(n),
            "proof_date": data, "metodo_data": method,
            "rischio_memorizzazione": risk(data),
            "verifica_archivio": result,
            "secondi_verifica": v.get("seconds") if v else None,
            "statement": p.statement[:300],
            "descrizione": (p.docstring or "").strip()[:300],
        })

    lines.sort(key=lambda r: (r["level"] != "facile", r["level"] != "mean_",
                              r["proof_lines"]))

    # selection: N per level, preferendo il risk di memorizzazione piu' low
    selection = []
    for lv in ("facile", "mean_", "difficile"):
        candidates = [r for r in lines if r["level"] == lv]
        candidates.sort(key=lambda r: ({"BASSO": 0, "INCERTO": 1, "ALTO": 2,
                                       "ignoto": 3}[r["rischio_memorizzazione"]],
                                      r["proof_lines"]))
        selection += candidates[:args.quanti_per_livello]

    Path(args.output).write_text(
        json.dumps({"all_of": lines, "selection": selection}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"Archivio: {archive}")
    print(f"Taglio dell'addestramento considerato: {CUT}\n")
    print(f"Problemi con dimostrazione d'archive ACCETTATA dal verifier: {len(lines)}\n")
    print(f"{'lvl':10} {'lines':>5} {'data':11} {'risk':9} {'check':10} problem")
    print("-" * 104)
    for r in lines:
        print(f"{r['level']:10} {r['proof_lines']:5d} {r['proof_date']:11} "
              f"{r['rischio_memorizzazione']:9} {r['verifica_archivio']:10} {r['problem']}")

    print(f"\n{'='*104}")
    print(f"SELEZIONE PROPOSTA ({args.quanti_per_livello} per level)")
    print(f"{'='*104}")
    for r in selection:
        print(f"  [{r['level']:9}] {r['problem']}")
        print(f"      {r['proof_lines']} lines di trial | aggiunta il {r['proof_date']} "
              f"| memorizzazione {r['rischio_memorizzazione']}")
        if r["descrizione"]:
            print(f"      \"{r['descrizione'].splitlines()[0][:90]}\"")

    count = {}
    for r in lines:
        count[r["rischio_memorizzazione"]] = count.get(r["rischio_memorizzazione"], 0) + 1
    print(f"\nRischio di memorizzazione su all_of i candidates: {count}")
    if count.get("ALTO", 0) == len(lines) and lines:
        print("\n  TUTTI ad high risk. E' expected_one: il tag di benchmark e' del")
        print("  2026-05-06 e il cut dell'addestramento e' maggio 2026, quindi")
        print("  ogni dimostrazione del tag e' anteriore. Per avere problems")
        print("  post-cut serve lo snapshot da main.")
    print(f"\nSalvato in {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
