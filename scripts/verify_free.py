"""Verifica theorems new_items against one challenge scritta a mano (verify.verify_free).

    env FCS_ARCHIVE=$PWD/external/fc-main FCS_INDEX=$PWD/verifier/problem_index_main.json \\
      .venv/bin/python scripts/verify_free.py \\
        --challenge ricerca/lean/A105020Goldbach_challenge.lean \\
        --candidato ricerca/lean/A105020Goldbach_candidate.lean \\
        --theorems A105020Goldbach.parametrizzazione,... \\
        --modules "FormalConjectures.OEIS.«105020»,FormalConjectures.Wikipedia.GoldbachConjecture"
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

from verify import verify_free   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenge", required=True)
    ap.add_argument("--candidato", required=True)
    ap.add_argument("--theorems", required=True)
    ap.add_argument("--modules", default="")
    ap.add_argument("--timeout", type=int, default=None)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()
    theorems = [t.strip() for t in a.theorems.split(",") if t.strip()]
    modules = tuple(m.strip() for m in a.modules.split(",") if m.strip())
    r = verify_free(Path(a.challenge).read_text(encoding="utf-8"), a.candidato, theorems,
                      allowed_modules=modules, timeout=a.timeout)
    print(f"ESITO: {r.status}   ({r.duration_s:.0f} s)")
    for c in r.checks:
        print(c)
    print("\n" + r.message)
    if r.errors:
        print("\n--- errors ---\n" + r.errors[:4000])
    if a.report:
        Path(a.report).write_text(json.dumps({
            "result": r.status, "seconds": round(r.duration_s, 1),
            "controlli": [{"name": c.name, "exceeded": c.passed, "detail": c.detail}
                          for c in r.checks],
            "message": r.message, "errors": r.errors,
            "uscita_comparator": r.raw_output[-6000:]}, indent=1, ensure_ascii=False))
    return 0 if r.status == "ACCEPTED" or r.status.upper().startswith("ACC") else 1


if __name__ == "__main__":
    raise SystemExit(main())
