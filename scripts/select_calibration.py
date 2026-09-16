"""
Sceglie i problemi su cui calibrare l'agent.

Un problema entra nella calibrazione solo se soddisfa TUTTE queste condizioni:

1. l'archivio ne fornisce una dimostrazione (non e' un problema aperto);
2. quella dimostrazione usa solo gli assiomi ammessi (niente native_decide,
   niente sorryAx ereditato da un lemma);
3. quella dimostrazione, estratta e compilata da sola, viene ACCETTATA da
   verify.py. E' il controllo che conta: i primi due sono necessari ma non
   sufficienti.

Per ciascuno si riportano:
- il LIVELLO DI DIFFICOLTA', dalla lunghezza della dimostrazione esistente;
- la DATA in cui la dimostrazione e' entrata nell'archivio pubblico;
- il RISCHIO DI MEMORIZZAZIONE, confrontando quella data con la data di taglio
  dell'addestramento del modello;
- l'ESITO della verifica della dimostrazione d'archivio.

Sul rischio di memorizzazione, una precisazione doverosa: il taglio dichiarato
per claude-opus-5 e' maggio 2026. Il tag di benchmark bench-v1-lean4.27.0 e' del
6 maggio 2026, quindi OGNI dimostrazione contenuta in quel tag e' anteriore al
taglio. Calibrare li' misura anche quanto il modello ricorda. Per avere problemi
post-taglio serve lo snapshot da main (vedi scripts/setup_snapshot_main.sh).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
sys.path.insert(0, str(RADICE / "agent"))

import config
from index import ProblemIndex
from hide import _posizione_separatore

#: Taglio dell'addestramento di claude-opus-5, come dichiarato dal modello.
TAGLIO = "2026-05"


def righe_prova(p) -> int:
    try:
        src = p.source_text()
        pos = _posizione_separatore(src)
        return src[pos + 2:].strip().count("\n") + 1 if pos is not None else -1
    except Exception:
        return -1


def livello(n: int) -> str:
    if n <= 0:
        return "?"
    return "facile" if n <= 3 else "medio" if n <= 12 else "difficile"


def git(archivio: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(archivio), *args],
                          capture_output=True, text=True).stdout


def data_prova(p, archivio: Path) -> tuple[str, str]:
    """(data, metodo) in cui la dimostrazione e' entrata nell'archivio."""
    try:
        rel = str(p.source_file.relative_to(archivio))
    except ValueError:
        return "?", "file fuori dall'archivio"
    try:
        src = p.source_text()
        pos = _posizione_separatore(src)
        prova = src[pos + 2:] if pos is not None else ""
    except Exception:
        prova = ""
    righe = [r.strip() for r in prova.split("\n")]
    righe = [r for r in righe if len(r) >= 18 and not r.startswith("--") and "sorry" not in r]
    if righe:
        riga = max(righe, key=len)
        out = git(archivio, "log", "--format=%ci|%h", "-S", riga, "--", rel).strip().splitlines()
        if out:
            return out[-1].split("|")[0][:10], "prima comparsa della riga di prova"
    out = git(archivio, "log", "--format=%ci|%h", "--diff-filter=A", "--", rel).strip().splitlines()
    if out:
        return out[-1].split("|")[0][:10], "creazione del file"
    return "?", "sconosciuto"


def rischio(data: str) -> str:
    if data == "?":
        return "ignoto"
    if data < TAGLIO:
        return "ALTO"
    if data < "2026-07":
        return "INCERTO"
    return "BASSO"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verifiche", default=str(RADICE / "runs" / "prove_archivio.json"),
                    help="esiti della verifica delle prove d'archivio")
    ap.add_argument("--quanti-per-livello", type=int, default=3)
    ap.add_argument("--uscita", default=str(RADICE / "runs" / "calibration_selection.json"))
    args = ap.parse_args()

    idx = ProblemIndex.load()
    archivio = config.ARCHIVE

    verificati: dict[str, dict] = {}
    f = Path(args.verifiche)
    if f.is_file():
        for d in json.loads(f.read_text(encoding="utf-8")):
            verificati[d["problema"]] = d
    else:
        print(f"ATTENZIONE: {f} non esiste. Senza le verifiche non posso dire")
        print("quali dimostrazioni d'archivio passano davvero il verificatore.")

    righe = []
    for p in idx.find(archive_proof_clean=True):
        if p.statement_has_sorry:
            continue
        v = verificati.get(p.theorem)
        esito = v["esito"] if v else "non verificata"
        if esito != "ACCETTATO":
            continue
        n = righe_prova(p)
        data, metodo = data_prova(p, archivio)
        righe.append({
            "problema": p.theorem, "modulo": p.module, "categoria": p.category,
            "righe_prova": n, "livello": livello(n),
            "data_prova": data, "metodo_data": metodo,
            "rischio_memorizzazione": rischio(data),
            "verifica_archivio": esito,
            "secondi_verifica": v.get("secondi") if v else None,
            "enunciato": p.statement[:300],
            "descrizione": (p.docstring or "").strip()[:300],
        })

    righe.sort(key=lambda r: (r["livello"] != "facile", r["livello"] != "medio",
                              r["righe_prova"]))

    # selezione: N per livello, preferendo il rischio di memorizzazione piu' basso
    selezione = []
    for lv in ("facile", "medio", "difficile"):
        candidati = [r for r in righe if r["livello"] == lv]
        candidati.sort(key=lambda r: ({"BASSO": 0, "INCERTO": 1, "ALTO": 2,
                                       "ignoto": 3}[r["rischio_memorizzazione"]],
                                      r["righe_prova"]))
        selezione += candidati[:args.quanti_per_livello]

    Path(args.uscita).write_text(
        json.dumps({"tutti": righe, "selezione": selezione}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"Archivio: {archivio}")
    print(f"Taglio dell'addestramento considerato: {TAGLIO}\n")
    print(f"Problemi con dimostrazione d'archivio ACCETTATA dal verificatore: {len(righe)}\n")
    print(f"{'liv':10} {'righe':>5} {'data':11} {'rischio':9} {'verifica':10} problema")
    print("-" * 104)
    for r in righe:
        print(f"{r['livello']:10} {r['righe_prova']:5d} {r['data_prova']:11} "
              f"{r['rischio_memorizzazione']:9} {r['verifica_archivio']:10} {r['problema']}")

    print(f"\n{'='*104}")
    print(f"SELEZIONE PROPOSTA ({args.quanti_per_livello} per livello)")
    print(f"{'='*104}")
    for r in selezione:
        print(f"  [{r['livello']:9}] {r['problema']}")
        print(f"      {r['righe_prova']} righe di prova | aggiunta il {r['data_prova']} "
              f"| memorizzazione {r['rischio_memorizzazione']}")
        if r["descrizione"]:
            print(f"      \"{r['descrizione'].splitlines()[0][:90]}\"")

    conteggio = {}
    for r in righe:
        conteggio[r["rischio_memorizzazione"]] = conteggio.get(r["rischio_memorizzazione"], 0) + 1
    print(f"\nRischio di memorizzazione su tutti i candidati: {conteggio}")
    if conteggio.get("ALTO", 0) == len(righe) and righe:
        print("\n  TUTTI ad alto rischio. E' atteso: il tag di benchmark e' del")
        print("  2026-05-06 e il taglio dell'addestramento e' maggio 2026, quindi")
        print("  ogni dimostrazione del tag e' anteriore. Per avere problemi")
        print("  post-taglio serve lo snapshot da main.")
    print(f"\nSalvato in {args.uscita}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
