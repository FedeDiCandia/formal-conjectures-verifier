"""
The tools the agent can use.

  * `lean_explore` — compiles a trial Lean file and returns ALL of Lean's
                     messages. It is for inspection: `#print`, `#check`,
                     `exact?`, full errors. It is not a judgement.
  * `lean_check`   — submits a Lean file to the verifier and reports the verdict.
                     It is the only judgement that counts.
  * `run_python`   — runs Python code in an isolated environment (no network, no
                     writes outside its own directory, with a timeout).

Why `lean_explore` exists separately: in the first shakedown the agent used NINE
verifications out of nine to inspect Mathlib's API, not to submit a proof. Using
the judge for that costs 33 seconds instead of 8 and returns a verdict ("rejected:
the theorem is not there") that is not the information wanted.

Why `run_python`: looking for a proof often means doing arithmetic (checking a
hypothesis on small cases, looking for a counterexample, computing a constant).
Doing it in one's head is the fastest way to get it wrong.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import explore as explorer   # noqa: E402
import verify as verifier   # noqa: E402


# ---------------------------------------------------------------------------
# Tool 0: lean_explore
# ---------------------------------------------------------------------------

SCHEMA_LEAN_EXPLORE = {
    "name": "lean_explore",
    "description": (
        "Compiles a trial Lean 4 file and returns ALL of Lean's messages, "
        "untruncated. It is for INSPECTION, not for submitting a proof: it is not a "
        "judgement and does not count as an attempt.\n\n"
        "Anything that prints something works:\n"
        "  #print DefinitionName      - the body of a definition or the fields of a "
        "structure\n"
        "  #check @lemmaName          - the type, with all the implicit arguments\n"
        "  example ... := by exact?   - search for a lemma that closes the goal\n"
        "  example ... := by apply?   - the same, for application\n"
        "  #reduce e                  - reduce a term (mind how long it takes)\n"
        "and errors come back in full, with the goal state.\n\n"
        "Unlike lean_check, here you MAY import the problem's module (for instance "
        "`import FormalConjectures.Wikipedia.Selfridge`) and inspect its "
        "definitions.\n\n"
        "About 8-10 seconds, against 30 for lean_check. Use this one to understand, "
        "that one to submit."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "lean_code": {
                "type": "string",
                "description": "The trial Lean file. It need not contain the "
                               "problem's theorem.",
            }
        },
        "required": ["lean_code"],
        "additionalProperties": False,
    },
}


def run_lean_explore(lean_code: str, timeout: int = 240,
                     slot: int | None = None) -> str:
    r = explorer.explore(lean_code, timeout=timeout, slot=slot)
    return r.render()


# ---------------------------------------------------------------------------
# Tool 1: lean_check
# ---------------------------------------------------------------------------

SCHEMA_LEAN_CHECK = {
    "name": "lean_check",
    "description": (
        "Submits a complete Lean 4 file to the official verifier and reports the "
        "verdict. The file has to be self-contained: imports, namespace, any "
        "auxiliary definitions, and the requested theorem with a complete proof.\n\n"
        "The verifier accepts ONLY if: the file compiles; it contains no sorry, "
        "admit, axiom declarations or native_decide; the theorem's type is IDENTICAL "
        "to the original statement's; the archive's definitions have not been "
        "redefined; and the only axioms used are propext, Classical.choice and "
        "Quot.sound.\n\n"
        "Use it as often as you like: it is the only judge that counts. One "
        "verification takes about 30 seconds.\n\n"
        "You can use it to EXPLORE as well, not only to submit: Lean's informational "
        "messages are returned to you, so `#check constantName`, "
        "`#print definitionName`, `example ... := by exact?` and "
        "`open ... in #check ...` all work. The file will be rejected (the requested "
        "theorem is missing) but you will still get back what you asked to inspect."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "lean_code": {
                "type": "string",
                "description": "The full content of the Lean file to verify.",
            }
        },
        "required": ["lean_code"],
        "additionalProperties": False,
    },
}


def run_lean_check(problem: str, lean_code: str, timeout: int | None = None) -> tuple[str, bool]:
    """Return (a textual report for the model, accepted)."""
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, encoding="utf-8") as f:
        f.write(lean_code)
        path = Path(f.name)
    try:
        r = verifier.verify(problem, path, timeout=timeout)
    finally:
        path.unlink(missing_ok=True)

    lines = [f"VERDICT: {r.status}"]
    for c in r.checks:
        lines.append(f"  [{'ok' if c.passed else 'FAILED'}] {c.name}"
                     + (f" — {c.detail}" if c.detail and not c.passed else ""))
    if r.message:
        lines.append("")
        lines.append(r.message)
    if r.errors:
        lines.append("")
        lines.append("Messages from Lean / comparator:")
        # NOT truncated here: Lean's message is the most useful information this
        # tool returns, and an `unsolved goals` with the goal state can be long.
        # The real limit is in verify._lean_errors, declared and generous.
        lines.append(r.errors)
    return "\n".join(lines), r.accepted


# ---------------------------------------------------------------------------
# Tool 2: run_python
# ---------------------------------------------------------------------------

SCHEMA_RUN_PYTHON = {
    "name": "run_python",
    "description": (
        "Runs Python 3 code in an isolated environment and returns whatever the code "
        "prints. Useful for doing arithmetic, looking for counterexamples, and "
        "checking a hypothesis on small cases.\n\n"
        "Libraries available: the standard library plus `numpy`, `sympy` and "
        "`numba`. For number theory, `sympy` has `isprime`, `factorint`, "
        "`nextprime`, `divisors` and `totient`.\n\n"
        "THE WORKING DIRECTORY SURVIVES between calls: the files you write stay, so a "
        "long search can save a checkpoint to a JSON file and the next call can pick "
        "it up. Variables in memory do not: every run is a new process.\n\n"
        "Limits: no network access; you may write only in the working directory; "
        "there is a time limit per run, so a long search should proceed in blocks, "
        "saving how far it has got. Print results with print()."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "The Python code to run."},
        },
        "required": ["code"],
        "additionalProperties": False,
    },
}


#: The macOS sandbox profile. `sandbox-exec` is deprecated but working, and it is
#: the only kernel-level isolation available without containers.
_SANDBOX_PROFILE = """(version 1)
(allow default)

; --- no network: this is the main requirement
(deny network*)

; --- no writes, except in the working directory
(deny file-write*)
(allow file-write*
  (subpath "{job}")
  (literal "/dev/null")
  (literal "/dev/urandom")
  (literal "/dev/random")
  (literal "/dev/dtracehelper"))

; --- no reading of secrets
(deny file-read*
  (subpath "{home}/.ssh")
  (subpath "{home}/.aws")
  (subpath "{home}/.gnupg")
  (subpath "{home}/.config/anthropic")
  (subpath "{home}/.anthropic")
  (literal "{project}/.env"))
"""


def _python_interpreter() -> str:
    """The Python to use inside the sandbox.

    It uses the COMPUTATION environment (`.venv-compute`), which has `numpy`,
    `sympy` and `numba`, rather than the project's: the generated code must not see
    the agent's libraries nor its key. The isolation does not come from the
    environment being poor — it comes from `sandbox-exec` (no network, writes only
    in the working directory), from the reduced environment without the API key,
    and from the `-I` option. Whoever measured the OEIS Open benchmark gave the
    model SageMath: without computation libraries a problem to refute cannot be
    tackled at all.

    `/usr/bin/python3` is avoided because it is the `xcrun` wrapper, which prints
    spurious errors inside the sandbox.
    """
    compute = ROOT / ".venv-compute" / "bin" / "python"
    if compute.is_file():
        return str(compute)
    base = Path(sys.base_prefix) / "bin" / "python3"
    if base.is_file():
        return str(base)
    return shutil.which("python3") or sys.executable


def run_python_tool(code: str, timeout: int = 30, max_output: int = 20_000,
                    folder: Path | str | None = None) -> str:
    """Run the code inside the sandbox and return its output.

    If `folder` is given, that directory is NOT destroyed afterwards: the files the
    program wrote stay available to the next call. This is for searches that take
    several steps — without persistence a program cannot save a checkpoint, and
    every call starts from nothing.
    """
    if not shutil.which("sandbox-exec"):
        return ("ERROR: `sandbox-exec` is not available on this system, so the code "
                "cannot be run in isolation. The run_python tool is disabled.")

    if folder is not None:
        fixed = Path(folder).resolve()
        fixed.mkdir(parents=True, exist_ok=True)
        context = contextlib.nullcontext(str(fixed))
    else:
        context = tempfile.TemporaryDirectory(prefix="fcs_py_")

    with context as job:
        work_dir = str(Path(job).resolve())
        script = Path(work_dir) / "program.py"
        script.write_text(code, encoding="utf-8")
        profile = Path(work_dir) / "sandbox.sb"
        profile.write_text(_SANDBOX_PROFILE.format(
            job=work_dir, home=str(Path.home()), project=str(ROOT)), encoding="utf-8")

        # A reduced environment: above all, NO API key.
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": work_dir,
            "TMPDIR": work_dir,
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        try:
            p = subprocess.run(
                ["sandbox-exec", "-f", str(profile), _python_interpreter(), "-I", str(script)],
                cwd=work_dir, env=environment, capture_output=True, text=True,
                timeout=timeout, start_new_session=True,
            )
        except subprocess.TimeoutExpired:
            return (f"ERROR: the code exceeded the time limit of {timeout} seconds and "
                    f"was interrupted.")

        parts = []
        if p.stdout:
            parts.append(p.stdout)
        if p.stderr:
            parts.append("--- stderr ---\n" + p.stderr)
        if p.returncode != 0:
            parts.append(f"--- the program exited with code {p.returncode} ---")
        result = "\n".join(parts) if parts else "(the code printed nothing)"
        if folder is not None:
            leftovers = sorted(q.name for q in Path(work_dir).iterdir()
                               if q.name not in ("program.py", "sandbox.sb"))
            if leftovers:
                result += ("\n--- files in the working directory (they stay available "
                           "to the next call) ---\n"
                           + ", ".join(leftovers[:40]))
        if len(result) > max_output:
            result = result[:max_output] + f"\n... [output truncated at {max_output} characters]"
        return result
