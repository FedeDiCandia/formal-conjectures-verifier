"""Shared helpers for the tests that really start Lean.

They exist for one thing only: the same tests have to run against both snapshots
of the archive. On `bench-v1` the utility module is called
`FormalConjectures.Util.ProblemImports`, on `main` it is `FormalConjecturesUtil`.
Rather than keeping two copies of every trial file, the import line is rewritten on
the fly.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import config   # noqa: E402

IMPORT_BENCH = "import FormalConjectures.Util.ProblemImports"


def adapt(text: str) -> str:
    """Rewrite the utility module's import for the snapshot in use."""
    return text.replace(IMPORT_BENCH, f"import {config.utility_module()}")
