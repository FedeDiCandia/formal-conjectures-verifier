#!/usr/bin/env python3
"""
verify.py — the proof verifier.

WHAT IT DOES
------------
It takes a candidate Lean file and the name of the archive's original theorem, and
answers ACCEPTED / REJECTED. It accepts only if ALL of these hold:

  1. the file contains no forbidden constructs (syntactic pre-scan);
  2. the file compiles without errors;
  3. it contains no `sorry`, no `admit` and no new `axiom` declarations;
  4. the axioms the theorem uses are only propext, Classical.choice, Quot.sound;
  5. the TYPE of the theorem is identical to the original statement — the
     comparison is on Lean's exported syntax tree, not on the text;
  6. the file neither redefines nor modifies the archive's definitions used in the
     statement;
  7. the proof term is accepted by a replay through the Lean kernel;
  8. it uses no options that switch off the kernel's checks.

HOW IT DOES IT
--------------
Points 2, 4, 5, 6 and 7 are not implemented here: they are delegated to
`comparator` (https://github.com/leanprover/comparator), the judge written by the
Lean FRO precisely to validate proofs produced by language models. comparator
compiles the two modules, exports them as text with `lean4export` (never trusting
the .olean files), compares the statements, checks the axioms and finally REPLAYS
everything through the Lean kernel. It is far more reliable than anything we could
write ourselves.

Points 1, 3 and 8 are the syntactic pre-scan in `guard.py`, which is defence in
depth (see the comment at the top of that file).

USAGE
-----
    python3 verifier/verify.py THEOREM_NAME FILE.lean
    python3 verifier/verify.py THEOREM_NAME FILE.lean --json
    python3 verifier/verify.py --batch jobs.jsonl --jobs 4
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import guard
import fingerprint as fingerprint_module
import negation
import sandbox
from index import ProblemIndex, Problem


# ---------------------------------------------------------------------------
# The result
# ---------------------------------------------------------------------------

#: Verification modes.
#:   strict     -> the archive's statement is checked as written.
#:   refutation -> the NEGATION of a problem with a propositional `answer(sorry)`
#:                 is checked, against a challenge we generate ourselves (trusted).
#:                 See verifier/negation.py.
STRICT = "strict"
REFUTATION = "refutation"

ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
ERROR = "ERROR"
TIMEOUT = "TIMEOUT"
UNVERIFIABLE = "UNVERIFIABLE"


@dataclass
class Check:
    """One individual check, with its outcome."""
    name: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:
        mark = "OK  " if self.passed else "NO  "
        return f"  [{mark}] {self.name}" + (f"\n         {self.detail}" if self.detail else "")


@dataclass
class Result:
    problem: str
    status: str
    checks: list[Check] = field(default_factory=list)
    message: str = ""
    #: compilation errors or comparator messages, useful to the agent
    errors: str = ""
    duration_s: float = 0.0
    raw_output: str = ""

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED

    def to_json(self) -> str:
        d = asdict(self)
        d["accepted"] = self.accepted
        return json.dumps(d, ensure_ascii=False, indent=2)

    def render(self) -> str:
        head = f"{self.status}  —  {self.problem}   ({self.duration_s:.1f}s)"
        body = "\n".join(str(c) for c in self.checks)
        out = f"{head}\n{body}"
        if self.message:
            out += f"\n\n{self.message}"
        if self.errors:
            out += f"\n\n--- messages from Lean / comparator ---\n{self.errors}"
        return out


# ---------------------------------------------------------------------------
# Slots: bound how many Lean processes run at once
# ---------------------------------------------------------------------------

class SlotPool:
    """A queue of N places. Each verification takes one and uses its own Lean
    module name, so two verifications in parallel do not tread on each other."""

    def __init__(self, size: int):
        self.size = size
        self._free: queue.Queue[int] = queue.Queue()
        for i in range(size):
            self._free.put(i)

    def acquire(self, timeout: Optional[float] = None) -> int:
        return self._free.get(timeout=timeout)

    def release(self, slot: int) -> None:
        self._free.put(slot)


_default_pool: Optional[SlotPool] = None
_pool_lock = threading.Lock()

#: Challenge modules already brought up to date, and the lock that serialises the
#: operation. It is needed because bringing a module up to date MODIFIES the
#: archive, and if one verification did that while another was taking its
#: fingerprint, the second would report (rightly) that the archive had changed.
#: It really happened.
_ready_challenges: set[str] = set()
_challenges_lock = threading.Lock()


def prepare_challenge(module: str, timeout: int) -> tuple[bool, str]:
    """Compile the original statement's module, OUTSIDE the sandbox.

    This is legitimate: the challenge is either a file of the archive or generated
    by us from its source, so it is trusted. comparator's README says so too ("as
    Challenge is trusted, both the sandbox and lean4export step for Challenge are
    not necessary").

    And it is necessary: inside the sandbox `lake` cannot remove the archive's
    artefacts, so if the module is not already up to date the compilation stops
    with "failed to remove output artifacts".

    Done once per module, under a lock.
    """
    with _challenges_lock:
        if module in _ready_challenges:
            return True, ""
        result, output = _run_with_timeout(
            [str(config.ELAN_BIN / "lake"), "build", module],
            cwd=config.ARCHIVE, env=config.lean_env(), timeout=timeout)
        if result == 0:
            _ready_challenges.add(module)
            return True, output
        return False, output


def get_pool(size: Optional[int] = None) -> SlotPool:
    global _default_pool
    with _pool_lock:
        if _default_pool is None:
            _default_pool = SlotPool(size or config.MAX_PARALLEL)
        return _default_pool


# ---------------------------------------------------------------------------
# Running comparator
# ---------------------------------------------------------------------------

def _run_with_timeout(cmd: list[str], cwd: Path, env: dict, timeout: int,
                      sandbox_profile: Optional[Path] = None) -> tuple[int, str]:
    """Run a command with a timeout, killing the WHOLE process tree.

    This is needed because comparator launches `lake`, which launches `lean`:
    killing only the parent would leave the children burning CPU for ever.
    `start_new_session` puts everything in one process group we can terminate as a
    block.
    """
    if sandbox_profile is not None:
        cmd = sandbox.wrap(cmd, sandbox_profile)
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            out, _ = proc.communicate(timeout=30)
        except Exception:
            out = ""
        return -signal.SIGKILL, out or ""


def _clean_leftovers(folder: Path, slot: int) -> None:
    """Remove artefacts left by OUR OWN slot in runs that ended badly.

    Only our own: the other slots may be in use by verifications running in
    parallel, and deleting their files while they work makes the compilation fail
    with "failed to remove output artifacts". That really happened, on all twelve
    verifications of one run.
    """
    built = config.ARCHIVE / ".lake" / "build"
    for name in (f"S{slot}", f"Challenge{slot}", f"E{slot}"):
        source_text = folder / f"{name}.lean"
        artefacts = [Path(str(built / branch / config.SANDBOX_SUBDIR / name) + ext)
                     for branch in ("lib/lean", "ir")
                     for ext in (".olean", ".ilean", ".trace", ".hash", ".c",
                                 ".o", ".c.hash", ".setup.json", ".olean.hash",
                                 ".ilean.hash")]
        # If the source is gone but the artefacts are still there, lake gets
        # confused: remove everything and start clean.
        if not source_text.is_file():
            for a in artefacts:
                a.unlink(missing_ok=True)


def _classify(output: str) -> tuple[str, str]:
    """Turn comparator's output into (name of the failed check, explanation)."""
    m = re.search(r"Illegal axiom detected: '([^']+)'", output)
    if m:
        ax = m.group(1)
        explain = {
            "sorryAx": "the proof contains a `sorry` (a hole), either directly or "
                       "inherited from an auxiliary lemma",
            "Lean.ofReduceBool": "`native_decide` was used, which trusts the compiler "
                                 "rather than the kernel",
            "Lean.trustCompiler": "the compiler was asked to be trusted",
        }.get(ax, f"the theorem depends on the axiom `{ax}`, which is not among the "
                  f"permitted ones ({', '.join(config.PERMITTED_AXIOMS)})")
        return "permitted axioms", f"illegal axiom `{ax}`: {explain}"

    if "theorem statement do not match" in output:
        return ("type identical to the original",
                "the statement proved is NOT identical to the archive's. It may be a "
                "weaker statement, one with extra hypotheses, or simply written in a "
                "way Lean elaborates differently.")
    if "constant kind don't match" in output:
        return ("type identical to the original",
                "in the candidate the declaration has a different kind (e.g. `def` instead of `theorem`)")
    if "Solution constant is not a theorem" in output:
        return ("type identical to the original", "in the candidate the declaration is not a theorem")
    if "Const does not match between challenge and target" in output or \
       "does not match between challenge" in output:
        m2 = re.search(r"target '([^']+)'", output)
        which = f" (`{m2.group(1)}`)" if m2 else ""
        return ("archive definitions intact",
                f"the candidate REDEFINES, differently, a definition used in the "
                f"statement{which}. The statement looks the same but talks about "
                f"something else.")
    if "Const not found in solution" in output or "Constant not found in solution" in output:
        m2 = re.search(r"in solution:? '([^']+)'", output)
        which = f" `{m2.group(1)}`" if m2 else ""
        return ("theorem present", f"the candidate does not declare{which}. The name has "
                                  f"to match the archive's EXACTLY, namespace included.")
    if "kernel rejected the solution" in output:
        return ("accepted by the kernel", "Lean's kernel rejected the proof term")
    if "error:" in output:
        return ("compiles without errors", "the file does not compile")
    if "Child exited with" in output:
        return ("compiles without errors", "the compilation failed")
    return ("comparator's check", "comparator rejected the candidate")


#: Lines with which `lake` announces its state: they are not Lean messages.
_LAKE_STATE = re.compile(r"^(Building |Exporting |Build completed|Running |"
                         r"[✔⚠✖ℹ] |info: \[|error: build failed|trace:)")

#: The start of a Lean message. The message continues on the following lines
#: until another one begins or a lake state line appears.
_MESSAGE_START = re.compile(r"^(info|warning|error): ")

#: The archive's STYLE linters: they complain that our temporary module has no
#: copyright header, no module docstring, and so on. They are irrelevant — the
#: candidate file is not a contribution to the archive — and they repeat fifteen
#: lines of licence with every message, flooding the context.
_LINTER_NOISE = re.compile(
    r"linter\.style\.(copyright|namespace|ams_attribute|category_attribute|moduleDocstring)"
    r"|The copyright header is incorrect"
    r"|missing a module docstring")

#: comparator's messages: isolated lines, without Lean's prefix.
_COMPARATOR_MESSAGE = re.compile(
    r"Illegal axiom|do not match|does not match|not found in|Constant not found|"
    r"rejected the solution|uncaught exception|kernel accepts")


def _message_blocks(output: str) -> list[str]:
    """Reassemble Lean's messages, which are blocks spanning several lines."""
    blocks: list[str] = []
    current: list[str] = []

    def close():
        if current:
            blocks.append("\n".join(current).rstrip())
            current.clear()

    for line in output.split("\n"):
        if _MESSAGE_START.match(line):
            close()
            current.append(line.rstrip())
        elif _LAKE_STATE.match(line):
            close()
        elif current:
            current.append(line.rstrip())
        elif _COMPARATOR_MESSAGE.search(line):
            blocks.append(line.rstrip())
    close()
    return blocks


def _lean_errors(output: str, max_chars: int = 40_000) -> str:
    """Lean's and comparator's messages, to be sent back to whoever wrote the file.

    It DELIBERATELY includes the `info:` messages too, that is the output of
    `#check`, `#print`, `exact?` and the like: they are the normal way of
    inspecting a definition, and without them whoever writes the proof has to
    infer the definitions by provoking errors on purpose.

    It strips the archive's style linters, which are pure noise for a temporary
    file and repeat the licence with every message.
    """
    useful = [b for b in _message_blocks(output) if not _LINTER_NOISE.search(b)]

    # Remove exact duplicates while keeping the order (Lean repeats the same
    # message once per compilation pass).
    seen, unique = set(), []
    for b in useful:
        if b not in seen:
            seen.add(b)
            unique.append(b)

    text = "\n\n".join(unique)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n... [messages truncated at {max_chars} characters]"
    return text


# ---------------------------------------------------------------------------
# Verifying a single candidate
# ---------------------------------------------------------------------------

def _tool_error(output: str) -> str | None:
    """Recognise failures that concern THE TOOLS, not the candidate.

    Measured on 12 September 2026: verifying A105020 on the `main` snapshot (Lean
    4.33.1) with the `lean4export` built for Lean 4.27, comparator stopped with
    `failed to read file ... incompatible header`, and the report said "the
    compilation failed" with the verdict REJECTED. That was false: the candidate
    had never been judged. A fault in the tools has to come out as ERROR, with the
    cause.
    """
    if "incompatible header" in output:
        return ("THE VERIFICATION DID NOT HAPPEN: comparator found .olean files compiled "
                "with a different version of Lean from its own tools "
                "(`incompatible header`). This says nothing about the candidate.\n\n"
                "For the `main` snapshot (Lean 4.33.1) you need "
                "FCS_LEAN4EXPORT=external/lean4export-433/.lake/build/bin/lean4export.")
    return None


def verify(problem_id: str, candidate: Path | str, *,
           index: Optional[ProblemIndex] = None,
           timeout: Optional[int] = None,
           slot: Optional[int] = None,
           keep_workspace: bool = False,
           run_guard: bool = True,
           mode: str = STRICT) -> Result:
    """Verify `candidate` as a proof of the theorem `problem_id`.

    `mode=REFUTATION` checks the NEGATION of the problem instead of the problem
    itself: this is for the open problems formalised with a propositional
    `answer(sorry)`, for which the archive's statement asserts that the answer is
    "yes" and a refutation would have no other way of being verified. See
    verifier/negation.py.

    `run_guard=False` skips the syntactic pre-scan. It is there ONLY for the
    tests, to show that comparator too — the real judge, not the textual filter —
    rejects sorry, added axioms and native_decide. In normal use it stays on.
    """
    started = time.time()
    candidate = Path(candidate)
    timeout = timeout or config.TIMEOUT_SECONDS
    checks: list[Check] = []

    def done(status: str, message: str = "", errors: str = "", raw: str = "") -> Result:
        return Result(problem=problem_id, status=status, checks=checks,
                      message=message, errors=errors,
                      duration_s=time.time() - started, raw_output=raw)

    # --- 0. is the environment in place?
    problems = config.check_installation()
    if problems:
        return done(ERROR, "Environment not ready:\n  - " + "\n  - ".join(problems))

    if not candidate.is_file():
        return done(ERROR, f"Candidate file not found: {candidate}")

    # --- 1. does the problem exist?
    try:
        index = index or ProblemIndex.load()
        problem: Problem = index.get(problem_id)
    except (KeyError, FileNotFoundError) as e:
        return done(ERROR, str(e))
    checks.append(Check("problem recognised",
                        True, f"{problem.module} — category: {problem.category}"))

    # --- 1b. verification mode
    if mode not in (STRICT, REFUTATION):
        return done(ERROR, f"unknown mode: {mode!r} "
                           f"(they are {STRICT!r} and {REFUTATION!r})")
    negated_challenge = None
    target = problem.theorem      # the theorem comparator has to compare
    allowed_module = None         # one extra import, only for the type_of% route
    if mode == REFUTATION:
        ok, _why_not = negation.can_be_negated(problem)
        try:
            negated_challenge = (negation.generate(problem) if ok
                            else negation.generate_by_kind(problem))
        except negation.NotNegatable as e:
            checks.append(Check("the problem admits a refutation", False, str(e)))
            return done(ERROR, f"The negated challenge cannot be built: {e}")
        target = negated_challenge.target or problem.theorem
        if negated_challenge.route == "answer":
            detail = ("negated challenge generated from the archive's source: "
                      "`answer(sorry)` replaced by `answer(False)`, so the statement "
                      "goes from `True ↔ P` to `False ↔ P`, that is `¬P`")
        else:
            allowed_module = problem.module
            detail = (f"negated challenge generated with `type_of%`: the target is "
                      f"`{target}`, that is `¬ (type_of% @{problem.theorem})`. The "
                      f"candidate is allowed to import `{problem.module}` in order to "
                      f"read the statement; leaning on the archive's proof, which is a "
                      f"`sorry`, is rejected by the axiom check")
        checks.append(Check("the problem admits a refutation", True, detail))

    # --- 2. is the original statement verifiable at all?
    # If the statement itself contains a `sorry` (a non-propositional answer( )
    # hole) then NO honest proof is possible: the type to be proved is incomplete.
    # That has to be said, not hidden.
    if problem.statement_has_sorry:
        checks.append(Check("complete statement", False,
                            "the original statement contains a non-propositional "
                            "`answer( )` hole (an answer to supply, e.g. a number)"))
        return done(UNVERIFIABLE,
                    "This problem asks you to SUPPLY AN ANSWER, not merely to prove "
                    "something: the statement contains `answer(sorry)` with a value that "
                    "is not a proposition.\n"
                    "Until the answer is fixed, the type to be proved contains a hole and "
                    "any proof would depend on the axiom `sorryAx`.\n"
                    "Moreover — as both the archive and comparator warn — filling the hole "
                    "and proving the statement is NOT enough to say the problem is solved: "
                    "a tautological answer would pass the formal check while being "
                    "mathematically empty. Human judgement is required.")
    checks.append(Check("complete statement", True, "no `answer( )` hole to fill"))

    # --- 3. syntactic pre-scan
    report = (guard.check_file(candidate, allowed_module=allowed_module)
              if run_guard else guard.GuardReport())
    if not report.ok:
        details = "\n".join(str(f) for f in report.findings)
        checks.append(Check("syntactic pre-scan", False,
                            f"{len(report.findings)} violations"))
        return done(REJECTED,
                    "The file contains forbidden constructs:\n\n" + details, errors=details)
    checks.append(Check("syntactic pre-scan", run_guard,
                        "no sorry/admit/axiom/native_decide, no dangerous options, "
                        "imports allowed" if run_guard else "SKIPPED (test mode)"))

    # --- 4. prepare the Solution module inside the archive's tree
    pool = get_pool()
    owned_slot = slot is None
    if owned_slot:
        slot = pool.acquire()
    try:
        sandbox_dir = config.ARCHIVE / config.SANDBOX_SUBDIR
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Clean up leftovers from interrupted runs. If a process is killed
        # half-way it leaves the temporary module's source without its artefacts
        # (or the other way round), and on the next round `lake` stops with "no
        # such file or directory". It costs nothing and removes a whole class of
        # mysterious faults.
        _clean_leftovers(sandbox_dir, slot)

        sol_name = f"S{slot}"
        sol_path = sandbox_dir / f"{sol_name}.lean"
        sol_module = f"{config.SANDBOX_MODULE_PREFIX}.{sol_name}"
        sol_path.write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")

        # --- which module acts as the Challenge
        challenge_path = None
        if negated_challenge is None:
            challenge_module = problem.module          # the archive, untouched
        else:
            challenge_name = f"Challenge{slot}"
            challenge_path = sandbox_dir / f"{challenge_name}.lean"
            challenge_path.write_text(negated_challenge.text, encoding="utf-8")
            challenge_module = f"{config.SANDBOX_MODULE_PREFIX}.{challenge_name}"
            checks.append(Check("negated challenge generated", True, challenge_module))

        cfg = {
            "challenge_module": challenge_module,
            "solution_module": sol_module,
            "theorem_names": [target],
            "permitted_axioms": config.PERMITTED_AXIOMS,
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cfg_path = tmp_dir / "config.json"
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

            # --- isolating the compilation
            profile = None
            if config.USE_SANDBOX and sandbox.available():
                # the directories have to exist BEFOREHAND: inside the sandbox one
                # cannot write to the parent directory in order to create them
                for d in sandbox.writable_dirs(
                        config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir):
                    d.mkdir(parents=True, exist_ok=True)
                profile = sandbox.write_profile(
                    tmp_dir / "check.sb",
                    sandbox.writable_dirs(config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir),
                    config.ROOT)
                checks.append(Check("isolated compilation", True,
                                    "sandbox-exec: no network, writes only in the "
                                    "temporary module's directory"))
            elif config.USE_SANDBOX:
                checks.append(Check("isolated compilation", False,
                                    "sandbox-exec is not available on this system: the "
                                    "candidate's compilation is NOT isolated"))

            # --- bring the CHALLENGE module up to date (see prepare_challenge)
            ready, prep_output = prepare_challenge(challenge_module, timeout)
            if not ready:
                checks.append(Check("challenge module ready", False,
                                    "the original statement cannot be compiled"))
                return done(ERROR,
                            "Cannot bring the original statement's module up to date. "
                            "That is a problem with the archive or with its build, not "
                            "with the candidate.",
                            errors=_lean_errors(prep_output), raw=prep_output)

            # --- the archive's fingerprint BEFORE the verification
            fingerprint_before = None
            if config.CHECK_FINGERPRINT:
                fingerprint_before = fingerprint_module.compute(
                    config.ARCHIVE, exclude=Path(config.SANDBOX_SUBDIR).name)

            environment = config.lean_env()
            environment["TMPDIR"] = str(tmp_dir)

            code, output = _run_with_timeout(
                [str(config.ELAN_BIN / "lake"), "env", str(config.COMPARATOR), str(cfg_path)],
                cwd=config.ARCHIVE, env=environment, timeout=timeout,
                sandbox_profile=profile,
            )

            # --- fingerprint AFTER: the archive has to be intact
            if fingerprint_before is not None:
                differences = fingerprint_module.compare(
                    fingerprint_before,
                    fingerprint_module.compute(config.ARCHIVE,
                                            exclude=Path(config.SANDBOX_SUBDIR).name))
                if differences:
                    checks.append(Check("archive intact after the verification", False,
                                        "; ".join(differences)))
                    return done(ERROR,
                                "THIS VERIFICATION IS NOT TRUSTWORTHY: compiling the "
                                "candidate file modified the archive.\n\n"
                                + "\n".join("  - " + d for d in differences) +
                                "\n\ncomparator compares the solution with the statement "
                                "it reads from the archive's compiled files. If those files "
                                "change, the comparison is against an altered problem and "
                                "the result means nothing (assumption 2 of comparator's "
                                "README). Restore the archive with:\n"
                                f"  cd {config.ARCHIVE} && git checkout . && lake build",
                                errors=_lean_errors(output), raw=output)
                checks.append(Check("archive intact after the verification", True,
                                    f"{fingerprint_before.n_content_files} archive files "
                                    f"unchanged (content hash) and "
                                    f"{fingerprint_before.n_metadata_files} dependency files "
                                    f"unchanged (size and timestamp)"))
    finally:
        if not keep_workspace:
            try:
                sol_path.unlink(missing_ok=True)
                if challenge_path is not None:
                    challenge_path.unlink(missing_ok=True)
                # remove the compiled artefact too, so as not to leave rubbish
                built = (config.ARCHIVE / ".lake" / "build" / "lib" / "lean"
                         / config.SANDBOX_SUBDIR / f"{sol_name}")
                for ext in (".olean", ".ilean", ".trace", ".hash", ".c", ".o"):
                    Path(str(built) + ext).unlink(missing_ok=True)
            except Exception:
                pass
        if owned_slot:
            pool.release(slot)

    # --- 5. the verdict
    if code == -signal.SIGKILL:
        checks.append(Check("within the time limit", False, f"exceeded {timeout}s"))
        return done(TIMEOUT, f"The verification exceeded the time limit of {timeout} seconds.",
                    errors=_lean_errors(output), raw=output)

    if code == 0 and "Your solution is okay!" in output:
        for name, detail in [
            ("compiles without errors", "the candidate module was compiled by lake"),
            ("type identical to the original",
             "compared on the syntax tree exported by lean4export, not on the text"),
            ("archive definitions intact",
             "every constant used in the statement matches the archive's"),
            ("permitted axioms", ", ".join(config.PERMITTED_AXIOMS)),
            ("accepted by the kernel", "proof term replayed through Lean's kernel"),
        ]:
            checks.append(Check(name, True, detail))
        if negated_challenge is not None:
            if negated_challenge.route == "answer":
                explanation = (
                    f"`False ↔ P` has been proved, that is `¬P`: the answer to the "
                    f"question {problem.theorem} poses is NO.\n\n"
                    "This CONTRADICTS the archive's statement, which with "
                    "`answer(sorry)` asserts that the answer is yes. If the refutation "
                    "is correct, the archive's formalisation should be updated to "
                    "`answer(False)`.")
            else:
                explanation = (
                    f"`{target}` has been proved, that is "
                    f"`¬ (type_of% @{problem.theorem})`: the archive's statement, as "
                    f"formalised, is FALSE.\n\n"
                    "Two readings are possible, and they have to be told apart before "
                    "anything is announced: either the conjecture is false, or the "
                    "formalisation is not faithful to the original source. The second is "
                    "the commoner case.")
            return done(ACCEPTED,
                        "VALID REFUTATION.\n\n" + explanation + "\n\n"
                        "Apply the protocol in docs/04-finding-protocol.md before "
                        "believing it: re-check with an independent program, compare with "
                        "the original source, and find out the problem's known state in "
                        "the literature.", raw=output)
        note = "The proof is valid."
        if problem.answer_placeholder_in_source:
            note += (
                "\n\nNOTE — this problem is formalised with `answer(sorry)`. Under the "
                "archive's default option that placeholder becomes `True`, so the "
                "statement proved is `True ↔ P`, the assertion that the answer to the "
                "question is YES. The formal check is correct, but the benchmark has "
                "already chosen the direction of the answer for you: if the right answer "
                "were NO, this statement would be false and unprovable.")
        return done(ACCEPTED, note, raw=output)

    fault = _tool_error(output)
    if fault:
        checks.append(Check("tools consistent with the archive", False,
                            ".olean files with an incompatible header"))
        return done(ERROR, fault, errors=_lean_errors(output), raw=output)
    check_name, explanation = _classify(output)
    checks.append(Check(check_name, False, explanation))
    return done(REJECTED, explanation, errors=_lean_errors(output), raw=output)


# ---------------------------------------------------------------------------
# Verifying a NEW theorem, against a hand-written challenge
# ---------------------------------------------------------------------------

_RE_CHALLENGE_AXIOM = re.compile(r"^\s*(?:private\s+|protected\s+)?axiom\b", re.MULTILINE)


def verify_free(challenge_text: str, candidate: Path | str, theorems: list[str], *,
                  allowed_modules: tuple[str, ...] = (),
                  timeout: Optional[int] = None,
                  slot: Optional[int] = None,
                  keep_workspace: bool = False) -> Result:
    """Verify theorems that are NOT in the archive, against a hand-written challenge.

    `verify` compares a candidate with a statement of the archive. Here the
    challenge (comparator's Challenge module) is supplied by whoever asks for the
    verification: the statements of the theorems in `theorems`, with `sorry` as the
    proof. The candidate has to declare the same theorems and prove them. The rest
    is the same chain as `verify`: syntactic pre-scan, isolated compilation,
    comparison of the elaborated statements, permitted axioms, replay through the
    kernel, fingerprint of the archive.

    `allowed_modules` are the archive's modules the candidate may import in order to
    read definitions and statements. Leaning on their proofs, which for open
    problems are `sorry`, is rejected by the axiom check: the same argument as the
    `type_of%` route for refutations.

    THE WARNING THAT MATTERS: comparator guarantees that the candidate proves
    exactly the challenge's statements. If the challenge states the wrong thing, the
    verification certifies the wrong thing. The challenge has to be read by a human
    being, which is why it has to stay short.
    """
    started = time.time()
    candidate = Path(candidate)
    timeout = timeout or config.TIMEOUT_SECONDS
    checks: list[Check] = []
    label = "free challenge: " + ", ".join(theorems)

    def done(status: str, message: str = "", errors: str = "", raw: str = "") -> Result:
        return Result(problem=label, status=status, checks=checks,
                      message=message, errors=errors,
                      duration_s=time.time() - started, raw_output=raw)

    problems = config.check_installation()
    if problems:
        return done(ERROR, "Environment not ready:\n  - " + "\n  - ".join(problems))
    if not candidate.is_file():
        return done(ERROR, f"Candidate file not found: {candidate}")
    if not theorems:
        return done(ERROR, "no theorem to verify")
    if _RE_CHALLENGE_AXIOM.search(challenge_text):
        return done(ERROR, "the challenge declares an axiom: a challenge contains statements only")
    missing = [t for t in theorems
                if not re.search(r"\btheorem\s+(?:\S*\.)?" + re.escape(t.rsplit(".", 1)[-1])
                                 + r"\b", challenge_text)]
    if missing:
        return done(ERROR, "the challenge does not declare: " + ", ".join(missing))
    checks.append(Check("well-formed challenge", True,
                        f"{len(theorems)} statements, no axiom declared"))

    report = guard.check_file(candidate, allowed_module=tuple(allowed_modules) or None)
    if not report.ok:
        details = "\n".join(str(f) for f in report.findings)
        checks.append(Check("syntactic pre-scan", False,
                            f"{len(report.findings)} violations"))
        return done(REJECTED, "The file contains forbidden constructs:\n\n" + details,
                    errors=details)
    checks.append(Check("syntactic pre-scan", True,
                        "no sorry/admit/axiom/native_decide; archive modules that may be "
                        "imported: " + (", ".join(allowed_modules) or "none")))

    pool = get_pool()
    owned_slot = slot is None
    if owned_slot:
        slot = pool.acquire()
    sandbox_dir = config.ARCHIVE / config.SANDBOX_SUBDIR
    sol_name, challenge_name = f"S{slot}", f"Challenge{slot}"
    sol_path = sandbox_dir / f"{sol_name}.lean"
    challenge_path = sandbox_dir / f"{challenge_name}.lean"
    code, output = None, ""
    try:
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        _clean_leftovers(sandbox_dir, slot)
        sol_path.write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")
        challenge_path.write_text(challenge_text, encoding="utf-8")
        sol_module = f"{config.SANDBOX_MODULE_PREFIX}.{sol_name}"
        challenge_module = f"{config.SANDBOX_MODULE_PREFIX}.{challenge_name}"
        cfg = {"challenge_module": challenge_module, "solution_module": sol_module,
               "theorem_names": list(theorems),
               "permitted_axioms": config.PERMITTED_AXIOMS}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cfg_path = tmp_dir / "config.json"
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

            profile = None
            if config.USE_SANDBOX and sandbox.available():
                for d in sandbox.writable_dirs(
                        config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir):
                    d.mkdir(parents=True, exist_ok=True)
                profile = sandbox.write_profile(
                    tmp_dir / "check.sb",
                    sandbox.writable_dirs(config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir),
                    config.ROOT)
                checks.append(Check("isolated compilation", True,
                                    "sandbox-exec: no network, writes only in the "
                                    "temporary module's directory"))
            elif config.USE_SANDBOX:
                checks.append(Check("isolated compilation", False,
                                    "sandbox-exec not available: compilation NOT isolated"))

            ready, prep_output = prepare_challenge(challenge_module, timeout)
            if not ready:
                checks.append(Check("challenge module ready", False,
                                    "the challenge does not compile"))
                return done(ERROR, "The CHALLENGE does not compile: it is the challenge's "
                                   "text that needs fixing, not the candidate.",
                            errors=_lean_errors(prep_output), raw=prep_output)
            checks.append(Check("challenge module ready", True, challenge_module))

            fingerprint_before = None
            if config.CHECK_FINGERPRINT:
                fingerprint_before = fingerprint_module.compute(
                    config.ARCHIVE, exclude=Path(config.SANDBOX_SUBDIR).name)
            environment = config.lean_env()
            environment["TMPDIR"] = str(tmp_dir)
            code, output = _run_with_timeout(
                [str(config.ELAN_BIN / "lake"), "env", str(config.COMPARATOR), str(cfg_path)],
                cwd=config.ARCHIVE, env=environment, timeout=timeout,
                sandbox_profile=profile,
            )
            if fingerprint_before is not None:
                differences = fingerprint_module.compare(
                    fingerprint_before,
                    fingerprint_module.compute(config.ARCHIVE,
                                            exclude=Path(config.SANDBOX_SUBDIR).name))
                if differences:
                    checks.append(Check("archive intact after the verification", False,
                                        "; ".join(differences)))
                    return done(ERROR,
                                "THIS VERIFICATION IS NOT TRUSTWORTHY: the archive changed "
                                "during it.\n"
                                + "\n".join("  - " + d for d in differences),
                                errors=_lean_errors(output), raw=output)
                checks.append(Check("archive intact after the verification", True,
                                    f"{fingerprint_before.n_content_files} archive files and "
                                    f"{fingerprint_before.n_metadata_files} dependency files unchanged"))
    finally:
        if not keep_workspace:
            for name, path in ((sol_name, sol_path), (challenge_name, challenge_path)):
                try:
                    path.unlink(missing_ok=True)
                    built = (config.ARCHIVE / ".lake" / "build" / "lib" / "lean"
                             / config.SANDBOX_SUBDIR / name)
                    for ext in (".olean", ".ilean", ".trace", ".hash", ".c", ".o"):
                        Path(str(built) + ext).unlink(missing_ok=True)
                except Exception:
                    pass
        if owned_slot:
            pool.release(slot)

    if code == -signal.SIGKILL:
        checks.append(Check("within the time limit", False, f"exceeded {timeout}s"))
        return done(TIMEOUT, f"The verification exceeded the time limit of {timeout} seconds.",
                    errors=_lean_errors(output), raw=output)
    if code == 0 and "Your solution is okay!" in output:
        for name, detail in [
            ("compiles without errors", "the candidate module was compiled by lake"),
            ("statements identical to the challenge",
             "compared on the syntax tree exported by lean4export, not on the text"),
            ("definitions used are intact",
             "the constants used in the statements match those of the challenge and of "
             "the archive"),
            ("permitted axioms", ", ".join(config.PERMITTED_AXIOMS)),
            ("accepted by the kernel", "proof terms replayed through Lean's kernel"),
        ]:
            checks.append(Check(name, True, detail))
        return done(ACCEPTED,
                    "Every statement of the challenge is proved.\n\n"
                    "What the verification does NOT say: that the challenge states the "
                    "right thing. It has to be read.", raw=output)
    fault = _tool_error(output)
    if fault:
        checks.append(Check("tools consistent with the archive", False,
                            ".olean files with an incompatible header"))
        return done(ERROR, fault, errors=_lean_errors(output), raw=output)
    check_name, explanation = _classify(output)
    checks.append(Check(check_name, False, explanation))
    return done(REJECTED, explanation, errors=_lean_errors(output), raw=output)


# ---------------------------------------------------------------------------
# Verifying in parallel
# ---------------------------------------------------------------------------

def verify_many(jobs: list[tuple[str, Path]], *, jobs_parallel: Optional[int] = None,
                timeout: Optional[int] = None) -> list[Result]:
    """Verify several candidates, with at most N Lean processes at once."""
    n = jobs_parallel or config.MAX_PARALLEL
    pool = SlotPool(n)
    index = ProblemIndex.load()

    # Every challenge is brought up to date BEFORE starting: it is the only step
    # that modifies the archive, and doing it while verifications run in parallel
    # falsifies the fingerprint check.
    for pid, _ in jobs:
        try:
            prepare_challenge(index.get(pid).module, timeout or config.TIMEOUT_SECONDS)
        except KeyError:
            pass
    results: list[Optional[Result]] = [None] * len(jobs)

    def worker(i: int, problem_id: str, path: Path) -> None:
        s = pool.acquire()
        try:
            results[i] = verify(problem_id, path, index=index, timeout=timeout, slot=s)
        except Exception as e:              # never let a thread die in silence
            results[i] = Result(problem=problem_id, status=ERROR, message=f"exception: {e!r}")
        finally:
            pool.release(s)

    threads = [threading.Thread(target=worker, args=(i, p, f), daemon=True)
               for i, (p, f) in enumerate(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return [r for r in results if r is not None]


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Verify a Lean proof against the archive's original statement.")
    ap.add_argument("problem", nargs="?", help="the theorem's full name, e.g. Erdos10.erdos_10")
    ap.add_argument("file", nargs="?", help="the candidate Lean file")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    ap.add_argument("--timeout", type=int, default=None, help="seconds (default: %d)" % config.TIMEOUT_SECONDS)
    ap.add_argument("--jobs", type=int, default=None, help="Lean processes in parallel (default: %d)" % config.MAX_PARALLEL)
    ap.add_argument("--batch", help="a JSONL file with lines {\"problem\":..., \"file\":...}")
    ap.add_argument("--refute", action="store_true",
                    help="verify the NEGATION of the problem (only for problems with a "
                         "propositional answer(sorry)): the statement becomes `False ↔ P`")
    ap.add_argument("--keep-workspace", action="store_true",
                    help="do not delete the generated Lean module (to see what happened)")
    args = ap.parse_args()

    if args.batch:
        jobs = []
        for line in Path(args.batch).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                d = json.loads(line)
                jobs.append((d["problem"], Path(d["file"])))
        results = verify_many(jobs, jobs_parallel=args.jobs, timeout=args.timeout)
        if args.json:
            print(json.dumps([json.loads(r.to_json()) for r in results], ensure_ascii=False, indent=2))
        else:
            for r in results:
                print(r.render()); print()
            ok = sum(1 for r in results if r.accepted)
            print(f"=== {ok}/{len(results)} accepted ===")
        return 0 if all(r.accepted for r in results) else 1

    if not args.problem or not args.file:
        ap.print_help()
        return 2

    r = verify(args.problem, args.file, timeout=args.timeout,
               keep_workspace=args.keep_workspace,
               mode=REFUTATION if args.refute else STRICT)
    print(r.to_json() if args.json else r.render())
    return 0 if r.accepted else 1


if __name__ == "__main__":
    sys.exit(main())
