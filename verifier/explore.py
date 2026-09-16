"""
The EXPLORATION tool: compile a Lean file and return everything Lean says.

WHY IT IS SEPARATE FROM verify.py
---------------------------------
`verify.py` answers one question: "is this a valid proof of the problem?" To do
that it compiles, exports, compares the statements, checks the axioms and replays
everything through the kernel. It costs about thirty seconds and it is the right
thing to do when a proof is submitted.

But the first shakedown with the agent showed that **most calls were not
submissions**: they were attempts to find out how Mathlib defines something. Nine
verifications out of nine, in that case. Using the judge to inspect a definition
is like asking for a court ruling to find out the time: slow, expensive, and the
verdict ("rejected: the theorem is not there") is not the information wanted.

This module does only the part that is useful for exploring:

  * it runs `lake env lean` on the file, with no comparator, no export, no
    comparison and no replay through the kernel;
  * it returns **all** the messages, untruncated: the output of `#print`,
    `#check`, search tactics like `exact?`, and the full errors with the goal
    state;
  * it is NOT a verification and must not be counted as one. A file that "passes"
    here has proved nothing.

Measured: 8.0 seconds against 32.9 for a full verification, and the output is
cleaner, because `lean` invoked directly does not apply the style linters that
`lake build` applies to the archive's library.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import guard
import fingerprint as fingerprint_module
import sandbox


@dataclass
class Exploration:
    """The result of a trial compilation."""
    ok: bool                 # the file compiles without errors
    messages: str            # all of Lean's messages, untruncated
    seconds: float
    isolated: bool           # whether it ran inside the sandbox
    truncated: bool = False
    #: violations found by the syntactic pre-scan: if there are any, nothing is compiled
    rejected_by_guard: list = None

    def render(self) -> str:
        head = (f"{'compiles, no errors' if self.ok else 'has errors'}  "
                 f"({self.seconds:.1f}s"
                 f"{'' if self.isolated else ', NOT isolated'})")
        return f"{head}\n\n{self.messages}" if self.messages else head


#: A generous limit. It exists only to keep the context from exploding if
#: someone prints half of Mathlib; Lean's errors stay well below it.
MAX_CHARS = 40_000


#: How many inspection files can coexist. Each call takes one exclusively: they
#: are Lean MODULE names, so they have to be fixed and few.
AVAILABLE_SLOTS = 8


@contextlib.contextmanager
def _exclusive_slot(slot: int | None):
    """Take an inspection slot exclusively, with a lock on the file.

    This is needed because the inspection file lives inside the archive's tree
    and its name is the Lean module's name: two explorations using the same slot
    overwrite each other's file, and each reads the other's messages. It is a
    silent error of the worst kind — it once made it look as though a tactic had
    closed an open problem, when the messages being read belonged to a different
    problem compiled by a different process.

    The lock is a file held with `flock`, so it works across processes too and is
    released by the operating system if the process dies.
    """
    folder = config.ARCHIVE / config.SANDBOX_SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    candidates = [slot] if slot is not None else list(range(AVAILABLE_SLOTS))
    waited = 0.0
    while True:
        for n in candidates:
            lock = open(folder / f"E{n}.lock", "a+")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                lock.close()
                continue
            try:
                yield n
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                lock.close()
            return
        if slot is not None and waited > 600:
            raise TimeoutError(f"inspection slot {slot} busy for over 10 minutes")
        time.sleep(0.5)
        waited += 0.5


def explore(code: str, *, timeout: int = 240, slot: int | None = None) -> Exploration:
    """Compile `code` and report everything Lean has to say.

    `slot=None` (the default) takes the first free slot, which is what is wanted
    when several explorations run together. An explicit slot is waited for if it
    is busy.
    """
    problems = config.check_installation()
    if problems:
        return Exploration(False, "Environment not ready:\n  - " + "\n  - ".join(problems),
                            0.0, False)

    # The syntactic pre-scan applies here too: an inspection file is compiled
    # like any other, so it can execute code in just the same way. The only rule
    # relaxed is the one on imports (see guard.check_source).
    report = guard.check_source(code, exploration=True)
    if not report.ok:
        return Exploration(
            False,
            "The file contains forbidden constructs and was not compiled:\n\n"
            + "\n".join(str(f) for f in report.findings),
            0.0, False, rejected_by_guard=[f.rule for f in report.findings])

    with _exclusive_slot(slot) as taken_slot:
        return _explore_in_slot(code, timeout=timeout, slot=taken_slot)


def _explore_in_slot(code: str, *, timeout: int, slot: int) -> Exploration:
    folder = config.ARCHIVE / config.SANDBOX_SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"E{slot}.lean"
    path.write_text(code, encoding="utf-8")
    relative = str(path.relative_to(config.ARCHIVE))

    start = time.time()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            profile = None
            if config.USE_SANDBOX and sandbox.available():
                for d in sandbox.writable_dirs(
                        config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir):
                    d.mkdir(parents=True, exist_ok=True)
                profile = sandbox.write_profile(
                    tmp_dir / "explore.sb",
                    sandbox.writable_dirs(config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir),
                    config.ROOT)

            fingerprint_before = None
            if config.CHECK_FINGERPRINT:
                fingerprint_before = fingerprint_module.compute(
                    config.ARCHIVE, exclude=Path(config.SANDBOX_SUBDIR).name)

            environment = config.lean_env()
            environment["TMPDIR"] = str(tmp_dir)
            command = [str(config.ELAN_BIN / "lake"), "env", "lean", relative]
            if profile is not None:
                command = sandbox.wrap(command, profile)

            proc = subprocess.Popen(
                command, cwd=str(config.ARCHIVE), env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, start_new_session=True)
            try:
                output, _ = proc.communicate(timeout=timeout)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                output = (f"TIMED OUT: the compilation exceeded {timeout} seconds. "
                          f"Probably a tactic that does not terminate, or a `#reduce` on a "
                          f"huge term.")
                exit_code = -1

            if fingerprint_before is not None:
                differences = fingerprint_module.compare(
                    fingerprint_before,
                    fingerprint_module.compute(config.ARCHIVE,
                                            exclude=Path(config.SANDBOX_SUBDIR).name))
                if differences:
                    output = ("WARNING: compiling this file MODIFIED the archive.\n"
                              + "\n".join("  - " + d for d in differences)
                              + "\n\n" + output)
                    exit_code = -2
    finally:
        path.unlink(missing_ok=True)

    duration = time.time() - start
    truncated = len(output) > MAX_CHARS
    if truncated:
        output = output[:MAX_CHARS] + (
            f"\n\n... [output truncated at {MAX_CHARS} characters]")
    return Exploration(ok=(exit_code == 0), messages=output.strip(),
                        seconds=duration, isolated=(profile is not None), truncated=truncated)


if __name__ == "__main__":
    text = sys.stdin.read() if len(sys.argv) < 2 else Path(sys.argv[1]).read_text(encoding="utf-8")
    print(explore(text).render())
