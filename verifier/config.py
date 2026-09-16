"""
Central configuration of the verifier.

Every path and every adjustable parameter lives here. Each value can be
overridden with an environment variable, so nothing has to be edited in code.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Paths ------------------------------------------------------------------

#: Project root (the directory containing verifier/, tests/, external/, …)
ROOT = Path(__file__).resolve().parent.parent

def _path(env_var: str, default: Path) -> Path:
    return Path(os.environ.get(env_var, default)).resolve()

#: The problem archive, already compiled with `lake build`.
ARCHIVE = _path("FCS_ARCHIVE", ROOT / "external" / "formal-conjectures")

#: The comparator binary: the judge of the proofs.
COMPARATOR = _path("FCS_COMPARATOR", ROOT / "external" / "comparator" / ".lake" / "build" / "bin" / "comparator")

#: lean4export: exports the Lean environment as text, so that comparator need
#: not trust the .olean files. It MUST be built with the same version of Lean as
#: the archive.
LEAN4EXPORT = _path("FCS_LEAN4EXPORT", ROOT / "external" / "lean4export-427" / ".lake" / "build" / "bin" / "lean4export")

#: The landrun shim for macOS (on Linux this can point at the real landrun).
LANDRUN = _path("FCS_LANDRUN", ROOT / "tools" / "bin" / "landrun")

#: Directory holding the elan/Lean binaries.
ELAN_BIN = _path("FCS_ELAN_BIN", Path.home() / ".elan" / "bin")

#: Where verify.py creates the temporary Lean modules to compile.
#: It has to sit inside the archive's source tree so that `lake` can find them:
#: the `FormalConjectures` library covers the glob `FormalConjectures.+`.
SANDBOX_SUBDIR = "FormalConjectures/_Judge"

#: The corresponding Lean module name.
SANDBOX_MODULE_PREFIX = "FormalConjectures._Judge"

def utility_module() -> str:
    """The module that problem files have to import.

    It changed between versions of the archive: in the tag `bench-v1-lean4.27.0`
    the utilities live in `FormalConjectures/Util/` and one imports
    `FormalConjectures.Util.ProblemImports`; on the `main` branch they became a
    library of their own, `FormalConjecturesUtil`, which the problem files
    import. Detecting it rather than hard-coding it saves having to remember
    which snapshot is in use.
    """
    if (ARCHIVE / "FormalConjecturesUtil.lean").is_file():
        return "FormalConjecturesUtil"
    return "FormalConjectures.Util.ProblemImports"


#: Where the problem index is stored (generated once).
INDEX_FILE = _path("FCS_INDEX", ROOT / "verifier" / "problem_index.json")


# --- Execution parameters ---------------------------------------------------

#: Maximum number of Lean processes in parallel.
MAX_PARALLEL = int(os.environ.get("FCS_MAX_PARALLEL", "4"))

#: Time limit for a single verification, in seconds.
TIMEOUT_SECONDS = int(os.environ.get("FCS_TIMEOUT", "900"))

#: Whether to run the verification inside sandbox-exec (macOS).
#: Set FCS_SANDBOX=0 to switch it off — but then the candidate's code runs
#: without isolation while it is compiled.
USE_SANDBOX = os.environ.get("FCS_SANDBOX", "1") not in ("0", "false", "no")

#: Whether to compare the fingerprint of the archive's compiled files before and
#: after every verification. See verifier/fingerprint.py.
CHECK_FINGERPRINT = os.environ.get("FCS_FINGERPRINT", "1") not in ("0", "false", "no")

#: The only permitted axioms. They are the three of Lean/Mathlib's logic:
#:   propext          - equivalent propositions are equal
#:   Classical.choice - the axiom of choice
#:   Quot.sound       - quotients behave
#: Any other axiom (including `sorryAx`, produced by `sorry`, and
#: `Lean.ofReduceBool`, produced by `native_decide`) fails the verification.
PERMITTED_AXIOMS = ["propext", "Classical.choice", "Quot.sound"]


def lean_env() -> dict:
    """Environment for the Lean subprocesses: elan and the judge's binaries on PATH."""
    env = dict(os.environ)
    extra = f"{LANDRUN.parent}:{ELAN_BIN}"
    env["PATH"] = extra + ":" + env.get("PATH", "")
    env["COMPARATOR_LANDRUN"] = str(LANDRUN)
    env["COMPARATOR_LEAN4EXPORT"] = str(LEAN4EXPORT)
    # Make Lean fail immediately on an internal panic instead of carrying on.
    env["LEAN_ABORT_ON_PANIC"] = "1"
    return env


def check_installation() -> list[str]:
    """Return the list of installation problems (empty if all is well)."""
    problems = []
    if not ARCHIVE.is_dir():
        problems.append(f"Archive not found: {ARCHIVE}")
    elif not (ARCHIVE / ".lake" / "build" / "lib").is_dir():
        problems.append(f"Archive not compiled (no .lake/build): run `lake build` in {ARCHIVE}")
    for name, path in [("comparator", COMPARATOR), ("lean4export", LEAN4EXPORT), ("landrun", LANDRUN)]:
        if not path.is_file() or not os.access(path, os.X_OK):
            problems.append(f"{name} missing or not executable: {path}")
    if not (ELAN_BIN / "lake").is_file():
        problems.append(f"lake not found in {ELAN_BIN}")
    return problems
