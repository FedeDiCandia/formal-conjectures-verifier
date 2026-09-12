"""Verifica teoremi nuovi contro una sfida scritta a mano (verify.verify_libera).

    env FCS_ARCHIVE=$PWD/external/fc-main FCS_INDEX=$PWD/verifier/problem_index_main.json \\
      .venv/bin/python scripts/verifica_libera.py \\
        --sfida ricerca/lean/A105020Goldbach_sfida.lean \\
        --candidato ricerca/lean/A105020Goldbach_candidato.lean \\
        --teoremi A105020Goldbach.parametrizzazione,... \\
        --moduli "FormalConjectures.OEIS.«105020»,FormalConjectures.Wikipedia.GoldbachConjecture"
"""
import argparse
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))

from verify import verify_libera   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sfida", required=True)
    ap.add_argument("--candidato", required=True)
    ap.add_argument("--teoremi", required=True)
    ap.add_argument("--moduli", default="")
    ap.add_argument("--timeout", type=int, default=None)
    ap.add_argument("--rapporto", default=None)
    a = ap.parse_args()
    teoremi = [t.strip() for t in a.teoremi.split(",") if t.strip()]
    moduli = tuple(m.strip() for m in a.moduli.split(",") if m.strip())
    r = verify_libera(Path(a.sfida).read_text(encoding="utf-8"), a.candidato, teoremi,
                      moduli_permessi=moduli, timeout=a.timeout)
    print(f"ESITO: {r.status}   ({r.duration_s:.0f} s)")
    for c in r.checks:
        print(c)
    print("\n" + r.message)
    if r.errors:
        print("\n--- errori ---\n" + r.errors[:4000])
    if a.rapporto:
        Path(a.rapporto).write_text(json.dumps({
            "esito": r.status, "secondi": round(r.duration_s, 1),
            "controlli": [{"nome": c.name, "superato": c.passed, "dettaglio": c.detail}
                          for c in r.checks],
            "messaggio": r.message, "errori": r.errors,
            "uscita_comparator": r.raw_output[-6000:]}, indent=1, ensure_ascii=False))
    return 0 if r.status == "ACCETTATO" or r.status.upper().startswith("ACC") else 1


if __name__ == "__main__":
    raise SystemExit(main())
