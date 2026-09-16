"""Aiuti condivisi dai test che fanno partire Lean davvero.

Serve a one cosa sola: gli stessi test devono girare su all_items e two gli
snapshot dell'archive. Su `bench-v1` il module di utility' si chiama
`FormalConjectures.Util.ProblemImports`, su `main` `FormalConjecturesUtil`.
Invece di tenere two copie di ogni file di trial, si riscrive la line di
import al volo.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import config   # noqa: E402

IMPORT_BENCH = "import FormalConjectures.Util.ProblemImports"


def adapt(text: str) -> str:
    """Riscrive l'import del module di utility' per lo snapshot in uso."""
    return text.replace(IMPORT_BENCH, f"import {config.utility_module()}")
