"""
Choose the problems to calibrate the agent on.

A problem enters the calibration only if it satisfies ALL of these:

1. the archive supplies a proof of it (it is not an open problem);
2. that proof uses only the permitted axioms (no native_decide, no sorryAx
   inherited from a lemma);
3. that proof, extracted and compiled on its own, is ACCEPTED by verify.py. This is
   the check that counts: the first two are necessary but not sufficient.

For each of them the script reports:
- the DIFFICULTY LEVEL, from the length of the existing proof;
- the DATE on which the proof entered the public archive;
- the MEMORISATION RISK, comparing that date with the model's training cutoff;
- the OUTCOME of verifying the archive's proof.

One necessary remark about the memorisation risk: the declared cutoff for
claude-opus-5 is May 2026. The benchmark tag bench-v1-lean4.27.0 is dated 6 May
2026, so EVERY proof in that tag predates the cutoff. Calibrating there also
measures how much the model remembers. For post-cutoff problems the snapshot from
main is needed (see scripts/setup_snapshot_main.sh).
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

#: claude-opus-5's training cutoff, as the model declares it.
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
    return "facile" if n <= 3 else "mean" if n <= 12 else "difficile"


def git(archive: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(archive), *args],
                          capture_output=True, text=True).stdout


def proof_date(p, archive: Path) -> tuple[str, str]:
    """(date, method) on which the proof entered the archive."""
    try:
        rel = str(p.source_file.relative_to(archive))
    except ValueError:
        return "?", "file outside dall'archive"
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
            return out[-1].split("|")[0][:10], "first appearance of the proof line"
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
                    help="results of verifying the archive's proofs")
    ap.add_argument("--per-level", type=int, default=3, dest="per_level")
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
        print(f"ATTENTION: {f} does not exist. Without the verifications there is no")
        print("way to say which archive proofs really pass the verifier.")

    lines = []
    for p in idx.find(archive_proof_clean=True):
        if p.statement_has_sorry:
            continue
        v = verified.get(p.theorem)
        result = v["result"] if v else "not verified"
        if result != "ACCEPTED":
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
            "description": (p.docstring or "").strip()[:300],
        })

    lines.sort(key=lambda r: (r["level"] != "facile", r["level"] != "mean",
                              r["proof_lines"]))

    # selection: N per level, preferring the lowest memorisation risk
    selection = []
    for lv in ("facile", "mean", "difficile"):
        candidates = [r for r in lines if r["level"] == lv]
        candidates.sort(key=lambda r: ({"BASSO": 0, "INCERTO": 1, "ALTO": 2,
                                       "ignoto": 3}[r["rischio_memorizzazione"]],
                                      r["proof_lines"]))
        selection += candidates[:args.per_level]

    Path(args.output).write_text(
        json.dumps({"all_items": lines, "selection": selection}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"Archive: {archive}")
    print(f"Training cutoff assumed: {CUT}\n")
    print(f"Problems whose archive proof is ACCEPTED by the verifier: {len(lines)}\n")
    print(f"{'lvl':10} {'lines':>5} {'data':11} {'risk':9} {'check':10} problem")
    print("-" * 104)
    for r in lines:
        print(f"{r['level']:10} {r['proof_lines']:5d} {r['proof_date']:11} "
              f"{r['rischio_memorizzazione']:9} {r['verifica_archivio']:10} {r['problem']}")

    print(f"\n{'='*104}")
    print(f"PROPOSED SELECTION ({args.per_level} per level)")
    print(f"{'='*104}")
    for r in selection:
        print(f"  [{r['level']:9}] {r['problem']}")
        print(f"      {r['proof_lines']} proof lines | added on {r['proof_date']} "
              f"| memorizzazione {r['rischio_memorizzazione']}")
        if r["description"]:
            print(f"      \"{r['description'].splitlines()[0][:90]}\"")

    count = {}
    for r in lines:
        count[r["rischio_memorizzazione"]] = count.get(r["rischio_memorizzazione"], 0) + 1
    print(f"\nRischio di memorizzazione su all_items i candidates: {count}")
    if count.get("ALTO", 0) == len(lines) and lines:
        print("\n  ALL at high risk. That is expected: the benchmark tag is dated")
        print("  2026-05-06 and the training cutoff is May 2026, so every proof in")
        print("  the tag predates it. For post-cutoff problems the snapshot from")
        print("  main is needed.")
    print(f"\nSalvato in {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
