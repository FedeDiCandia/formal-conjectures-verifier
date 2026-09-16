"""
Passo zero della fase 1: **verificare in way indipendente i record pubblicati.**

PERCHÉ QUESTO PRIMA DI CERCARE
------------------------------
Prima di provare a battere un record bisogna essere capaci di leggerlo e di
controllarlo. Se non riusciamo a verificare un code che qualcuno ha già
pubblicato, non siamo in condizione di dire niente su one che troviamo noi — ed è
esattamente l'error che questo progetto ha già fatto cinque volte.

Questo script download i codici espliciti delle tables di Brouwer, li espande, li
check con il nostro giudice e compare la size con il limit inferiore
che la tabella rivendica. Tre results possibili, e all_items e three sono informazione:

  CONFERMATO   la size e la validità corrispondono alla tabella
  DISCORDE     il code è valid ma di size diversa da quella dichiarata
  NON VALIDO   il code non soddisfa i vincoli (quasi certamente colpa nostra:
               un format che non sappiamo leggere)

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
PAUSE = 0.4      # cortesia verso un server universitario


def download(relative: str) -> Path:
    local = CACHE / relative.replace("/", "_")
    if local.is_file() and local.stat().st_size > 0:
        return local
    CACHE.mkdir(parents=True, exist_ok=True)
    # `curl` e non urllib: il Python di questo Mac non ha i certificati di
    # system e ogni https fallisce con CERTIFICATE_VERIFY_FAILED.
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
    """Legge un code in qualunque dei formati in cui è pubblicato."""
    raw = path.read_text(errors="replace").lstrip()
    head = raw[:200].lower()
    if head.startswith("$base=16"):
        # listing di words in esadecimale
        words = [int(r.strip(), 16) for r in raw.splitlines()[1:] if r.strip()]
        width = max((len(r.strip()) for r in raw.splitlines()[1:] if r.strip()),
                        default=0)
        # la width in digits esadecimali non dice n: gli zeri in head si
        # perdono. Si restituisce 0 e chi chiama usa l'n della cell.
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
        raise ValueError(f"command $EXEC non gestito: {head.splitlines()[0]!r}")
    words, n = read(path)
    return words, n, "listing di words"


def one(key: str, entry: dict) -> dict:
    n, d, w = (int(x) for x in key.split(","))
    result = {"cell": f"A({n},{d},{w})", "expected": entry["inferiore"],
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
            result["state"] = "NON VALIDO"
            result["note"] = v.findings[0]
        elif v.size != entry["inferiore"]:
            result["state"] = "DISCORDE"
            result["note"] = (f"valid ma {v.size} words invece di "
                             f"{entry['inferiore']}")
        else:
            result["state"] = "CONFERMATO"
    except OSError as e:
        result["state"] = "NON SCARICATO"
        result["note"] = str(e)[:120]
    except Exception as e:                                   # noqa: BLE001
        result["state"] = "NON LETTO"
        result["note"] = f"{type(e).__name__}: {e}"[:160]
    return result


def main() -> int:
    bounds = json.loads((DATA_DIR / "limiti_cwc.json").read_text())
    to_do = {k: v for k, v in bounds.items() if v["code"]}
    print(f"{len(to_do)} cells con code esplicito pubblicato.\n")
    results = []
    count: dict[str, int] = {}
    for i, (k, v) in enumerate(sorted(to_do.items(),
                                      key=lambda kv: kv[1]["inferiore"]), 1):
        e = one(k, v)
        results.append(e)
        count[e["state"]] = count.get(e["state"], 0) + 1
        mark = {"CONFERMATO": "ok", "DISCORDE": "??", "NON VALIDO": "XX"}.get(
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
