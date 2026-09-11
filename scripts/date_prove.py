"""
Quando e' stata aggiunta all'archivio la dimostrazione di ciascun problema.

Serve a stimare il RISCHIO DI MEMORIZZAZIONE: se una dimostrazione era gia'
pubblica su GitHub prima della data di taglio dell'addestramento del modello,
il modello potrebbe averla vista, e un successo direbbe poco sulla sua capacita'
di dimostrare.

Il metodo: si cerca con `git log -S` il primo commit che ha introdotto nel file
una riga distintiva della dimostrazione. Non e' infallibile (una dimostrazione
riscritta risulta piu' recente di quanto sia l'idea), ma e' una misura, non una
supposizione.
"""
import re
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
sys.path.insert(0, str(RADICE / "agent"))
from index import ProblemIndex
from nascondi import _posizione_separatore
import config

ARCHIVIO = config.ARCHIVE


def git(*args) -> str:
    return subprocess.run(["git", "-C", str(ARCHIVIO), *args],
                          capture_output=True, text=True).stdout


def riga_distintiva(prova: str) -> str | None:
    """Una riga della dimostrazione lunga e specifica, buona per `git log -S`."""
    candidate = [r.strip() for r in prova.split("\n")]
    candidate = [r for r in candidate
                 if len(r) >= 18 and not r.startswith("--") and "sorry" not in r]
    if not candidate:
        return None
    return max(candidate, key=len)


def data_introduzione(p) -> tuple[str, str, str]:
    """(data, commit, metodo) del primo commit che ha introdotto la prova."""
    rel = str(p.source_file.relative_to(ARCHIVIO))
    try:
        src = p.source_text()
        pos = _posizione_separatore(src)
        prova = src[pos + 2:] if pos is not None else ""
    except Exception:
        prova = ""
    riga = riga_distintiva(prova)
    if riga:
        out = git("log", "--format=%ci|%h", "-S", riga, "--", rel).strip().splitlines()
        if out:
            data, commit = out[-1].split("|")
            return data[:10], commit, "prima comparsa della riga di prova (git log -S)"
    out = git("log", "--format=%ci|%h", "--diff-filter=A", "--", rel).strip().splitlines()
    if out:
        data, commit = out[-1].split("|")
        return data[:10], commit, "creazione del file (riga di prova non isolabile)"
    return "?", "?", "sconosciuto"


def main():
    idx = ProblemIndex.load()
    nomi = sys.argv[1:]
    problemi = [idx.get(n) for n in nomi] if nomi else []
    if not problemi:
        print("uso: date_prove.py NOME_TEOREMA [NOME_TEOREMA ...]")
        return
    CUTOFF = "2026-05"   # dichiarato nel prompt di sistema di claude-opus-5
    print(f"{'data':11} {'commit':9} {'rischio':10} teorema")
    print("-" * 100)
    for p in problemi:
        data, commit, metodo = data_introduzione(p)
        rischio = ("ALTO" if data < CUTOFF else
                   "BASSO" if data > "2026-06" else "INCERTO")
        print(f"{data:11} {commit:9} {rischio:10} {p.theorem}")
        print(f"{'':32} {metodo}")
        if p.formal_proof_link:
            print(f"{'':32} formal_proof: {p.formal_proof_kind} -> {p.formal_proof_link[:70]}")


if __name__ == "__main__":
    main()
