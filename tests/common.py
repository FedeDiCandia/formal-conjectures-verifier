"""Aiuti condivisi dai test che fanno partire Lean davvero.

Serve a una cosa sola: gli stessi test devono girare su tutti e due gli
snapshot dell'archivio. Su `bench-v1` il modulo di utilita' si chiama
`FormalConjectures.Util.ProblemImports`, su `main` `FormalConjecturesUtil`.
Invece di tenere due copie di ogni file di prova, si riscrive la riga di
import al volo.
"""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))

import config   # noqa: E402

IMPORT_BENCH = "import FormalConjectures.Util.ProblemImports"


def adatta(testo: str) -> str:
    """Riscrive l'import del modulo di utilita' per lo snapshot in uso."""
    return testo.replace(IMPORT_BENCH, f"import {config.modulo_utilita()}")
