"""Tests of the verifier, end to end.

These tests really start Lean, so they are SLOW (about 20-30 seconds each). They
require the environment to be installed and the archive compiled.

The problem used as a test bench is `JugglerConjecture.jugglerStep_36`:

  * the archive already contains a complete proof of it (so we can check that the
    verifier ACCEPTS something, not only that it rejects);
  * its statement uses a definition from the problem's own file, which is what the
    test "it rejects anyone who redefines an archive definition" needs;
  * it is small, so the tests do not take forever.

WHY SOME THINGS ARE TESTED TWICE
--------------------------------
The verifier rejects `sorry`, added axioms and `native_decide` at two independent
points: the syntactic pre-scan (fast, textual) and comparator (slow, but the real
guarantee). Whenever both apply, they are exercised SEPARATELY here: with
`run_guard=False` the textual filter is switched off and only comparator's judgement
remains. If someone one day got round the textual filter, these tests show that the
system still holds.
"""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
import common
import config
from index import ProblemIndex
from verify import verify, ACCEPTED, REJECTED, TIMEOUT, UNVERIFIABLE, verify_many

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROBLEM = "JugglerConjecture.jugglerStep_36"


# --- prerequisiti -----------------------------------------------------------

def setup_module(module):
    """Skip every test (with an explanation) if the environment is not ready."""
    problems = config.check_installation()
    if problems:
        pytest.skip("Environment not installed:\n  - " + "\n  - ".join(problems),
                    allow_module_level=True)
    if not config.INDEX_FILE.is_file():
        pytest.skip("Indice mancante: run `python verifier/index.py --build`",
                    allow_module_level=True)


#: The fixtures adapted to the snapshot in use, once per session.
_ADAPTED: dict[str, Path] = {}


def fixture(name: str) -> Path:
    """Path of the fixture, adapted to the snapshot in use.

    The fixtures import the archive's utility module: on `bench-v1` it is called
    `FormalConjectures.Util.ProblemImports`, on the `main` branch
    `FormalConjecturesUtil`. Rather than keeping two copies of every file, the
    import line is rewritten on the fly, so the same suite runs against both
    snapshots.
    """
    if name in _ADAPTED:
        return _ADAPTED[name]
    utility = config.utility_module()
    source_path = FIXTURES / name
    if utility == "FormalConjectures.Util.ProblemImports":
        _ADAPTED[name] = source_path
        return source_path
    text = common.adapt(source_path.read_text(encoding="utf-8"))
    dest = Path(tempfile.mkdtemp(prefix="fixture_adattata_")) / name
    dest.write_text(text, encoding="utf-8")
    _ADAPTED[name] = dest
    return dest


def _check(name: str, **kw):
    return verify(PROBLEM, fixture(name), **kw)


def _failed_rule(result) -> set[str]:
    return {c.name for c in result.checks if not c.passed}


# --- 1. It ACCEPTS a correct proof ----------------------------------

def test_1_accetta_dimostrazione_corretta():
    """The most important requirement: if the verifier NEVER accepted
    nothing, it would be useless even while being perfectly safe."""
    r = _check("1_correct.lean")
    assert r.status == ACCEPTED, f"expected ACCEPTED, ottenuto {r.status}:\n{r.render()}"
    passed = {c.name for c in r.checks if c.passed}
    for expected in ["compiles without errors", "type identical to the original",
                     "archive definitions intact", "permitted axioms",
                   "accepted dal kernel"]:
        assert expected in passed, f"controllo mancante: {expected}"


# --- 2. It REJECTS a proof containing `sorry` --------------------------------

def test_2a_rifiuta_sorry_col_controllo_sintattico():
    r = _check("2_sorry.lean")
    assert r.status == REJECTED
    assert "controllo sintattico preventivo" in _failed_rule(r)


def test_2b_rifiuta_sorry_anche_senza_controllo_sintattico():
    """The real judgement: comparator sees the axiom `sorryAx`."""
    r = _check("2_sorry.lean", run_guard=False)
    assert r.status == REJECTED
    assert "axioms permitted" in _failed_rule(r)
    assert "sorryAx" in r.errors


# --- 3. It REJECTS a proof that adds an axiom -------------------------------

def test_3a_rifiuta_assioma_col_controllo_sintattico():
    r = _check("3_axiom.lean")
    assert r.status == REJECTED
    assert "controllo sintattico preventivo" in _failed_rule(r)


def test_3b_rifiuta_assioma_anche_senza_controllo_sintattico():
    r = _check("3_axiom.lean", run_guard=False)
    assert r.status == REJECTED
    assert "axioms permitted" in _failed_rule(r)
    assert "Illegal axiom" in r.raw_output, "comparator has to name the added axiom"


# --- 4. It REJECTS a proof that uses `native_decide` ------------------------

def test_4a_rifiuta_native_decide_col_controllo_sintattico():
    r = _check("4_native_decide.lean")
    assert r.status == REJECTED
    assert "controllo sintattico preventivo" in _failed_rule(r)


def test_4b_rifiuta_native_decide_anche_senza_controllo_sintattico():
    """`native_decide` makes the compiler do the computation instead of the kernel: it
    leaves the axiom `Lean.ofReduceBool` in the proof term."""
    r = _check("4_native_decide.lean", run_guard=False)
    assert r.status == REJECTED
    assert "axioms permitted" in _failed_rule(r)
    # On Lean 4.27 the axiom left behind is `Lean.ofReduceBool`; on Lean 4.33 it is a
    # PER-DECLARATION axiom, of the form
    # `JugglerConjecture.jugglerStep_36._native.native_decide.ax_1_1`. This is why the
    # verifier works from a list of PERMITTED axioms and not from a list of forbidden
    # ones: a list of names to forbid would have missed the new form silently.
    assert ("ofReduceBool" in r.errors
            or "native_decide" in r.errors), r.errors[:300]


# --- 5. It REJECTS a weakened statement -------------------------------------

def test_5_rifiuta_enunciato_piu_debole():
    """The candidate proves `jugglerStep 36 = 6 ∨ jugglerStep 36 = 7`, which is
    strictly weaker than the original `jugglerStep 36 = 6`. The syntactic pre-scan
    cannot notice: that is a job for Lean."""
    r = _check("5_weaker.lean")
    assert r.status == REJECTED
    assert "kind identico all'original" in _failed_rule(r)


# --- 6. It REJECTS anyone who redefines an archive definition ---------------

def test_6_it_rejects_the_redefinition_of_a_definition():
    """The candidate redefines `jugglerStep` as the constant function 6. The statement
    is written IDENTICALLY to the original, and the proof is `rfl`: if
    confronto fosse testuale, passerebbe."""
    r = _check("6_redefinition.lean")
    assert r.status == REJECTED
    assert "archive definitions intact" in _failed_rule(r)
    assert "jugglerStep" in r.errors


# --- Extra: the problems with an answer( ) hole -----------------------------

def test_7_it_flags_the_problems_with_an_answer_hole():
    """A statement that still contains a non-propositional `answer(sorry)` cannot be
    proved honestly. The verifier has to say so, not simply reject: that is different
    information."""
    idx = ProblemIndex.load()
    with_hole = idx.find(has_answer_hole=True)
    assert with_hole, "the index should contain problems with answer( ) holes"
    r = verify(with_hole[0].theorem, fixture("1_correct.lean"), index=idx)
    assert r.status == UNVERIFIABLE, f"expected UNVERIFIABLE, ottenuto {r.status}"
    assert "answer" in r.message.lower()


# --- Extra: the timeout -----------------------------------------------------

def test_8_the_timeout_works():
    """With one second available no verification can finish."""
    r = _check("1_correct.lean", timeout=1)
    assert r.status == TIMEOUT, f"expected TIMEOUT, ottenuto {r.status}"
    assert "within the time limit" in _failed_rule(r)


# --- Extra: the parallel queue ----------------------------------------------

def test_9_verifications_in_parallel():
    """Two verifications at once have to give the same results as two separate ones,
    without treading on each other's temporary files."""
    results = verify_many(
        [(PROBLEM, fixture("1_correct.lean")),
         (PROBLEM, fixture("5_weaker.lean"))],
        jobs_parallel=2,
    )
    assert len(results) == 2
    assert results[0].status == ACCEPTED, results[0].render()
    assert results[1].status == REJECTED, results[1].render()


# --- Extra: the messages returned to whoever wrote the file -----------------

COPYRIGHT_NOISE = """\
Building FormalConjectures.Wikipedia.JugglerConjecture
Build completed successfully (7993 jobs).
⚠ [7993/7993] Built FormalConjectures._Judge.S0 (7.3s)
warning: FormalConjectures/_Judge/S0.lean:1:0: The copyright header is incorrect. Please copy and paste the following one:
/-
Copyright 2026 The Formal Conjectures Authors.
Licensed under the Apache License, Version 2.0 (the "License");
-/

Note: This linter can be disabled with `set_option linter.style.copyright.formalConjectures false`
info: FormalConjectures/_Judge/S0.lean:8:0: @Nat.floor : {a : Type} -> a -> N
info: FormalConjectures/_Judge/S0.lean:9:0: def Even : a -> Prop :=
fun a => exists r, a = r + r
error: FormalConjectures/_Judge/S0.lean:14:2: unsolved goals
case h
n : N
|- n = 6
uncaught exception: Illegal axiom detected: 'sorryAx'
"""


def test_10_leans_info_messages_reach_the_author():
    """`#check` e `#print` producono messages `info:`. Se li buttassimo away,
    whoever writes the proof would have no way of inspecting the definitions and would
    have to infer them by provoking errors on purpose — which is exactly what happened
    during the first shakedown with the agent."""
    from verify import _lean_errors
    out = _lean_errors(COPYRIGHT_NOISE)
    assert "@Nat.floor" in out, "#check's output has to arrive"
    assert "def Even" in out, "#print's output has to arrive"
    assert "fun a => exists r, a = r + r" in out, \
        "the message's continuation lines have to stay attached"


def test_11_real_errors_arrive_with_their_context():
    from verify import _lean_errors
    out = _lean_errors(COPYRIGHT_NOISE)
    assert "unsolved goals" in out
    assert "|- n = 6" in out, "the unproved goal's context is what explains the error"
    assert "Illegal axiom detected: 'sorryAx'" in out


def test_12_the_style_linter_noise_is_stripped():
    """The archive's copyright linter repeats fifteen lines of licence with every
    message: irrelevant for a temporary file, and it would flood the
    context di chi legge."""
    from verify import _lean_errors
    out = _lean_errors(COPYRIGHT_NOISE)
    assert "copyright" not in out.lower()
    assert "Apache" not in out
    assert "Building" not in out and "Build completed" not in out, \
        "lake's state lines are not Lean messages"


def test_13_repeated_messages_appear_only_once():
    from verify import _lean_errors
    doppio = COPYRIGHT_NOISE + COPYRIGHT_NOISE
    assert _lean_errors(doppio).count("@Nat.floor") == 1


# --- Extra: a candidate that tries to sabotage the archive ------------------

def test_14_a_candidate_cannot_rewrite_a_file_of_the_archive(tmp_path):
    """The most important safety test.

    comparator exports the Challenge BEFORE compiling the Solution, so sabotage of the
    archive's compiled files does not alter the verification in progress: it alters
    every SUBSEQUENT one, making them compare the solution with an
    statement diverso da quello vero. E' l'assunto 2 del README di comparator,
    and for us, running verifications one after another, it is not an assumption but a
    risk concreto.

    The candidate here uses `#eval` to rewrite `JugglerConjecture.olean`. Three things
    are checked: the guard rejects it; with the guard switched off the sandbox blocks
    it anyway; and the file stays byte-for-byte identical.
    """
    import hashlib
    import guard

    target = (config.ARCHIVE / ".lake" / "build" / "lib" / "lean"
                 / "FormalConjectures" / "Wikipedia" / "JugglerConjecture.olean")
    if not target.is_file():
        pytest.skip("archive not compiled")

    def target_hash() -> str:
        return hashlib.sha256(target.read_bytes()).hexdigest()

    before = target_hash()

    saboteur = tmp_path / "saboteur.lean"
    saboteur.write_text(common.adapt(f'''import FormalConjectures.Util.ProblemImports

#eval show IO Unit from do
  try
    IO.FS.writeFile "{target}" "ARCHIVE RUINED"
    IO.println "SABOTAGGIO RIUSCITO"
  catch e =>
    IO.println s!"sabotaggio impedito: {{e}}"

namespace JugglerConjecture
noncomputable def jugglerStep (n : ℕ) : ℕ :=
  if Even n then ⌊(n : ℝ) ^ (1/2 : ℝ)⌋₊ else ⌊(n : ℝ) ^ (3/2 : ℝ)⌋₊
@[category test, AMS 11]
theorem jugglerStep_36 : jugglerStep 36 = 6 := by
  unfold jugglerStep
  norm_num [←Real.sqrt_eq_rpow]
end JugglerConjecture
'''), encoding="utf-8")

    # 1. in normal use the guard stops it before compiling
    report = guard.check_file(saboteur)
    assert not report.ok, "the guard has to reject a file that uses #eval and IO"
    rules = {f.rule for f in report.findings}
    assert "command:#eval" in rules
    assert "metaprogramming:IO" in rules

    # 2. with the guard switched off, the sandbox has to block it anyway
    r = verify(PROBLEM, saboteur, run_guard=False)
    assert "sabotaggio impedito" in r.raw_output or "SABOTAGGIO RIUSCITO" not in r.raw_output, \
        f"the sabotage was not prevented:\n{r.raw_output[:2000]}"

    # 3. the archive's file has to be byte-for-byte identical
    assert target_hash() == before, \
        "the archive's compiled file WAS MODIFIED: every subsequent verification " \
        "would compare solutions against an altered statement"


def test_the_oeis_problems_can_be_read_from_source():
    """The OEIS entries have a module name in guillemets and a file without them.

    A Lean identifier cannot begin with a digit, so entry A109074's module is called
    `FormalConjectures.OEIS.«109074»` while the file on disk is `109074.lean`. Until
    the conversion stripped the guillemets, NONE of the 209 OEIS problems could be
    read: the agent could not receive them, the extractor could not extract them, the
    negated challenge could not be generated — and those 209 are the family the
    spending plan rests on.
    """
    idx = ProblemIndex.load()
    oeis = [p for p in idx.problems if "OEIS" in p.module]
    if not oeis:
        pytest.skip("this snapshot contains no OEIS entries")
    read_count = 0
    for p in oeis[:20]:
        if p.source_file.is_file() and p.range:
            assert p.source_text().strip(), p.theorem
            read_count += 1
    assert read_count >= 15, f"only {read_count} entries OEIS su 20 leggibili dal source_text"
