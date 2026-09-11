"""
Igiene dei bersagli: toglie dalla lista quello che non è più aperto.

Un problema marcato `research open` nel nostro snapshot può non essere più
aperto per tre motivi:

  1. Epoch AI l'ha risolto e pubblicato (corrispondenza per nome esatto: certa);
  2. combacia per numero di sequenza OEIS con qualcosa che loro hanno risolto,
     ma le formalizzazioni sono indipendenti e spesso riguardano un'altra
     congettura sulla stessa sequenza: **da leggere**, non da escludere;
  3. l'archivio stesso l'ha risolto dopo il commit su cui Epoch si è fermata.

Produce `docs/dati/bersagli.json`: esclusi con motivo, da verificare, e il
serbatoio dei candidati ancora validi.

Non spende niente e non tocca l'archivio.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
from index import ProblemIndex   # noqa: E402

EPOCH = RADICE / "external" / "LeanOpenProblems"
ESITI = RADICE / "external" / "LeanOpenProblems-results"


def campioni_epoch() -> dict:
    """Gli id dei campioni del loro benchmark, con l'insieme di provenienza."""
    fuori = {}
    base = EPOCH / "apn" / "data"
    if not base.is_dir():
        raise SystemExit(f"manca {base}: clona epoch-research/LeanOpenProblems")
    for insieme in sorted(p.name for p in base.iterdir() if p.is_dir()):
        f = base / insieme / "samples.jsonl"
        if not f.is_file():
            continue
        for riga in f.read_text(encoding="utf-8").splitlines():
            if riga.strip():
                r = json.loads(riga)
                r["insieme"] = insieme
                fuori.setdefault(r["id"], r)
    return fuori


def esiti_epoch() -> dict:
    """Per ogni campione: quante volte è stato tentato e se è stato risolto."""
    fuori = defaultdict(lambda: {"tentativi": 0, "risolto": False, "run": []})
    for scores in (ESITI / "runs").glob("*/*/scores.json"):
        prob, run = scores.parts[-2], scores.parts[-3]
        try:
            d = json.loads(scores.read_text(encoding="utf-8"))
        except ValueError:
            continue
        v = (d.get("proof_scorer") or {}).get("value")
        s = fuori[prob]
        s["tentativi"] += 1
        if v == "C":
            s["risolto"] = True
            s["run"].append(run)
    return fuori


def sequenza(modulo: str) -> int | None:
    m = re.search(r"OEIS\.«(\d+)»", modulo)
    return int(m.group(1)) if m else None


def main() -> int:
    idx = ProblemIndex.load(RADICE / "verifier" / "problem_index_main.json")
    aperti = [p for p in idx.find(category="research open")
              if not p.statement_has_sorry]
    camp, esiti = campioni_epoch(), esiti_epoch()

    # sequenze OEIS che loro hanno risolto
    seq_risolte = set()
    for i, r in camp.items():
        if r["insieme"] != "oeis" or not esiti.get(i, {}).get("risolto"):
            continue
        m = re.search(r"(\d{4,7})", r.get("oeis_id") or i)
        if m:
            seq_risolte.add(int(m.group(1)))
    seq_loro = set()
    for i, r in camp.items():
        if r["insieme"] != "oeis":
            continue
        m = re.search(r"(\d{4,7})", r.get("oeis_id") or i)
        if m:
            seq_loro.add(int(m.group(1)))

    esclusi, da_leggere, candidati = [], [], []
    for p in aperti:
        s = sequenza(p.module)
        e = esiti.get(p.theorem, {})
        if e.get("risolto"):
            esclusi.append({"problema": p.theorem, "motivo":
                            "risolto da Epoch AI, corrispondenza per nome esatto",
                            "run": e["run"][:2]})
        elif s in seq_risolte:
            da_leggere.append({"problema": p.theorem, "sequenza": f"A{s:06d}",
                               "motivo": "Epoch ha risolto un'altra congettura "
                                         "sulla stessa sequenza: verificare se è "
                                         "la stessa affermazione"})
        else:
            candidati.append({
                "problema": p.theorem, "modulo": p.module,
                "sequenza": f"A{s:06d}" if s else None,
                "mai_nel_loro_benchmark": p.theorem not in camp
                                          and (s is None or s not in seq_loro),
                "tentato_da_loro": e.get("tentativi", 0),
                "enunciato": p.statement[:200],
            })

    fuori = {
        "snapshot": "external/fc-main 0a8b856c (10 settembre 2026)",
        "confronto": "epoch-research/LeanOpenProblems + -results",
        "aperti_verificabili": len(aperti),
        "esclusi_perche_risolti": esclusi,
        "da_leggere_prima_di_usarli": da_leggere,
        "candidati": candidati,
    }
    dest = RADICE / "docs" / "dati" / "bersagli.json"
    dest.write_text(json.dumps(fuori, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"aperti verificabili           {len(aperti)}")
    print(f"esclusi (risolti da Epoch)    {len(esclusi)}")
    for x in esclusi:
        print(f"    {x['problema']}")
    print(f"da leggere (sequenza in comune) {len(da_leggere)}")
    print(f"candidati rimasti             {len(candidati)}")
    print(f"  di cui mai nel loro benchmark {sum(1 for c in candidati if c['mai_nel_loro_benchmark'])}")
    print(f"\nscritto in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
