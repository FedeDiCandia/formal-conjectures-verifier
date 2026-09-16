"""
Isolating the verification (macOS).

WHY
---
To judge a proof you have to COMPILE it, and compiling a Lean file means
executing code: elaborators, macros, tactics. On Linux `comparator` isolates this
phase with `landrun`; on macOS `landrun` does not exist.

Here we use `sandbox-exec`, the macOS kernel's isolation mechanism. Deprecated by
Apple but working, and the only one available without containers.

WHAT IT ALLOWS
--------------
- reading: everything (Mathlib, the toolchain and the archive have to be read);
- writing: ONLY the three directories where `lake` puts the candidate's
  temporary module, plus the temporary-file directory. Measured in practice: a
  verification touches nothing else;
- network: NOTHING.

What the sandbox keeps out is candidate code that tries to rewrite the archive's
compiled files: exactly the attack described in assumption 2 of comparator's
README ("you have not previously tried to compile … potentially adversarial
files, as that might compromise your Challenge file"). As a second safety net,
`verifier/fingerprint.py` compares the archive's fingerprint before and after
every verification.
"""
from __future__ import annotations

import shutil
from pathlib import Path

#: `(subpath ...)` in a sandbox profile needs absolute, real paths (no
#: symlinks): on macOS /tmp is a link to /private/tmp, and using the unresolved
#: form makes the permission fail silently.
def _real(p: Path) -> str:
    return str(Path(p).resolve())


PROFILE = """(version 1)
(allow default)

; ---- no network access
(deny network*)

; ---- no writing, except where it is really needed
(deny file-write*)
(allow file-write*
{writable}
  (literal "/dev/null")
  (literal "/dev/zero")
  (literal "/dev/random")
  (literal "/dev/urandom")
  (literal "/dev/dtracehelper")
  (literal "/dev/tty"))

; ---- no reading of secrets
(deny file-read*
  (subpath "{home}/.ssh")
  (subpath "{home}/.aws")
  (subpath "{home}/.gnupg")
  (subpath "{home}/.config/anthropic")
  (subpath "{home}/.anthropic")
  (literal "{project_env}"))
"""


def writable_dirs(archive: Path, judge_subdir: str, tmp: Path) -> list[Path]:
    """The only directories a verification needs to modify.

    Obtained by measuring which files change during a successful verification:
    the sources of the temporary module and the two branches of `.lake/build`
    that concern it. Nothing else.
    """
    lake = archive / ".lake" / "build"
    return [
        archive / judge_subdir,
        lake / "ir" / judge_subdir,
        lake / "lib" / "lean" / judge_subdir,
        tmp,
    ]


def write_profile(destination: Path, writable: list[Path], project: Path) -> Path:
    lines = "\n".join(f'  (subpath "{_real(p)}")' for p in writable)
    destination.write_text(
        PROFILE.format(writable=lines, home=_real(Path.home()),
                       project_env=_real(project / ".env")),
        encoding="utf-8")
    return destination


def available() -> bool:
    return shutil.which("sandbox-exec") is not None


def wrap(command: list[str], profile: Path) -> list[str]:
    """Prefix the command with `sandbox-exec`."""
    return ["sandbox-exec", "-f", str(profile)] + command
