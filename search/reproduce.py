"""
Step zero: **verify the published records independently.**

WHY THIS BEFORE SEARCHING
------------------------------
Before trying to beat a record one has to be able to read it and to check it. If we
cannot verify a code someone has already published, we are in no position to say
anything about one we find ourselves — and that is exactly the error this project
has already made five times.

This script downloads the explicit codes from Brouwer's tables, expands them, checks
them with our judge and compares the size with the lower bound the table claims.
Three outcomes are possible, and all three are information:

  CONFIRMED    the size and the validity match the table
  MISMATCH     the code is valid but of a different size from the one declared
  INVALID      the code does not satisfy the constraints (almost certainly our
               fault: a format we cannot read)

I file si scaricano one volta sola e restano in `research_data/codici/`.
"""
from __future__ import annotations

import json
import sys
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "search"))

from codes import Result, read, check, fast_check   # noqa: E402
from orbits import expand, expand_cyclic                  # noqa: E402

DATA_DIR = ROOT / "research_data"
CACHE = DATA_DIR / "codici"
BASE = "https://aeb.win.tue.nl/codes/"
PAUSE = 0.4      # courtesy towards a university server


def download(relative: str) -> Path:
    local = CACHE / relative.replace("/", "_")
    if local.is_file() and local.stat().st_size > 0:
        return local
    CACHE.mkdir(parents=True, exist_ok=True)
    # `curl` rather than urllib: this Mac's Python has no system certificates and
    # every https fails with CERTIFICATE_VERIFY_FAILED.
    result = subprocess.run(
        ["curl", "-sS", "-L", "--max-time", "45", "-A",
         "ricerca-codici/1.0 (check indipendente di bounds pubblicati)",
         "-o", str(local), BASE + relative],
        capture_output=True, text=True)
    if result.returncode != 0 or not local.is_file() or local.stat().st_size == 0:
        local.unlink(missing_ok=True)
        raise OSError(f"curl ha failed ({result.returncode}): "
                      f"{result.stderr.strip()[:120]}")
    time.sleep(PAUSE)
    return local


def load(path: Path) -> tuple[list[int], int, str]:
    """Read a code in any of the formats it is published in."""
    raw = path.read_text(errors="replace").lstrip()
    head = raw[:200].lower()
    if head.startswith("$base=16"):
        # listing di words in esadecimale
        words = [int(r.strip(), 16) for r in raw.splitlines()[1:] if r.strip()]
        width = max((len(r.strip()) for r in raw.splitlines()[1:] if r.strip()),
                        default=0)
        # the width in hexadecimal digits does not give n: the leading zeros are
        # lost. 0 is returned and the caller uses the cell's n.
        del width
        return words, 0, "listing esadecimale"
    if head.startswith("$exec orbit"):
        words, n, info = expand(path)
        return words, n, f"orbits (|G|={info['ordine_gruppo']}, {info['seeds']} seeds)"
    if head.startswith("$exec cycle"):
        words, n, info = expand_cyclic(path)
        return words, n, (f"cicli {info['blocks']} (|G|={info['ordine_gruppo']}, "
                           f"{info['seeds']} seeds)")
    if head.startswith("$exec"):
        raise ValueError(f"unhandled $EXEC command: {head.splitlines()[0]!r}")
    words, n = read(path)
    return words, n, "listing di words"


def one(key: str, entry: dict) -> dict:
    n, d, w = (int(x) for x in key.split(","))
    result = {"cell": f"A({n},{d},{w})", "expected": entry["lower"],
             "source": entry["source"], "file": entry["code"]}
    try:
        path = download(entry["code"])
        words, read_n, format = load(path)
        result["format"] = format
        if read_n and read_n != n:
            result["state"] = "DISCORDE"
            result["note"] = f"length letta {read_n}, waited {n}"
            return result
        v = fast_check(words, n, d, w)
        result["found"] = v.size
        if not v.ok:
            result["state"] = "INVALID"
            result["note"] = v.findings[0]
        elif v.size != entry["lower"]:
            result["state"] = "DISCORDE"
            result["note"] = (f"valid ma {v.size} words invece di "
                             f"{entry['lower']}")
        else:
            result["state"] = "CONFERMATO"
    except OSError as e:
        result["state"] = "NOT DOWNLOADED"
        result["note"] = str(e)[:120]
    except Exception as e:                                   # noqa: BLE001
        result["state"] = "NOT READ"
        result["note"] = f"{type(e).__name__}: {e}"[:160]
    return result


def main() -> int:
    bounds = json.loads((DATA_DIR / "limiti_cwc.json").read_text())
    to_do = {k: v for k, v in bounds.items() if v["code"]}
    print(f"{len(to_do)} cells with a published explicit code.\n")
    results = []
    count: dict[str, int] = {}
    for i, (k, v) in enumerate(sorted(to_do.items(),
                                      key=lambda kv: kv[1]["lower"]), 1):
        e = one(k, v)
        results.append(e)
        count[e["state"]] = count.get(e["state"], 0) + 1
        mark = {"CONFIRMED": "ok", "MISMATCH": "??", "INVALID": "XX"}.get(
            e["state"], "--")
        print(f"[{i:3d}/{len(to_do)}] {mark} {e['cell']:<14} "
              f"expected {e['expected']:>6}  "
              f"found {str(e.get('found', '-')):>6}  "
              f"{e.get('format', '')}  {e.get('note', '')}")
        sys.stdout.flush()
    (DATA_DIR / "riproduzione.json").write_text(json.dumps(results, indent=1))
    print("\n" + "=" * 70)
    for state, how_many in sorted(count.items(), key=lambda kv: -kv[1]):
        print(f"  {state:<14} {how_many}")
    print(f"\nRapporto in {DATA_DIR / 'riproduzione.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
