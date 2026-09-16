"""Tests of the "negated" challenges.

THE PROBLEM THEY SOLVE
----------------------
107 still-OPEN problems of the archive are formalised like this:

    theorem conjecture : answer(sorry) ↔ P := by sorry

and the archive's default option turns `answer(sorry)` into `True`. The statement
Lean sees is therefore `True ↔ P`: the assertion that the answer is YES.

If for one of those problems the right answer were NO, the theorem as written would
be FALSE and unprovable, and whoever found the refutation would have no way to have
it verified. The negated challenge gives them that way.

HOW THIS IS TESTED WITHOUT SOLVING AN OPEN PROBLEM
--------------------------------------------------
None of those 107 problems is provable in either direction: they are open. But
comparator compares the STATEMENTS before checking the axioms, and that is enough.

Take a candidate whose proof is left as `sorry`:
  * if the statement MATCHES the challenge, comparator reaches the axiom check and
    rejects it for `sorryAx`;
  * if the statement DIFFERS, comparator stops earlier and rejects it for
    "statements do not match".

The reason for the rejection therefore says whether the statements match. Four
combinations suffice to show that the two challenges are distinct statements and
that both work, without proving anything mathematical.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import common
import config
import negation
from index import ProblemIndex
from verify import verify, REFUTATION, STRICT, REJECTED, ERROR

#: Chosen because the statement uses only Mathlib's `Nat.Perfect` (no local
#: definition to copy) and because its file contains THREE problems
#: with `answer(sorry)`: it checks that the substitution touches only
#: quello target.
PROBLEM = "PerfectNumbers.infinitely_many_perfect"

_CANDIDATE = """import FormalConjectures.Util.ProblemImports

namespace PerfectNumbers

open Nat

@[category research open, AMS 11]
theorem infinitely_many_perfect :
    answer({answer}) ↔ {{n : ℕ | Perfect n}}.Infinite := by
  sorry

end PerfectNumbers
"""


def setup_module(module):
    if config.check_installation():
        pytest.skip("environment not installed", allow_module_level=True)
    if not config.INDEX_FILE.is_file():
        pytest.skip("index missing", allow_module_level=True)


@pytest.fixture(scope="module")
def index():
    return ProblemIndex.load()


def _candidate(tmp_path, answer: str) -> Path:
    f = tmp_path / f"candidate{answer}.lean"
    f.write_text(common.adapt(_CANDIDATE.format(answer=answer)),
                 encoding="utf-8")
    return f


# --- generation (fast, no Lean) ---------------------------------------------

def test_the_substitution_happens_only_in_the_target_theorem(index):
    """PerfectNumbers' file contains three problems with `answer(sorry)`.
    Invertirli all_items darebbe one challenge diversa da quella richiesta."""
    challenge = negation.generate(index.get(PROBLEM))
    body = challenge.text.split("-/\n", 1)[1]     # drop the generated header
    assert challenge.substitutions == 1
    assert body.count("answer(False)") == 1
    assert body.count("answer(sorry)") >= 1, \
        "the other problems in the file have to stay as they were"


def test_the_challenge_declares_that_it_was_generated(index):
    """Whoever opens the file has to see at once that it is not an archive file."""
    challenge = negation.generate(index.get(PROBLEM))
    assert "NEGATED CHALLENGE" in challenge.text
    assert "generato automaticamente" in challenge.text
    assert PROBLEM in challenge.text


def test_a_problem_without_answer_cannot_be_negated(index):
    """A statement without `answer( )` asserts a proposition directly: its negation
    is not a problem of the archive, it is something else."""
    with pytest.raises(negation.NotNegatable, match="contains no"):
        negation.generate(index.get("JugglerConjecture.jugglerStep_36"))


def test_a_non_propositional_answer_hole_cannot_be_negated(index):
    """If the answer is a number or a set there is no direction to invert: there is a
    value to supply."""
    with_hole = index.find(has_answer_hole=True)
    assert with_hole, "l'index dovrebbe contenerne"
    for p in with_hole:
        if p.answer_placeholder_in_source:
            with pytest.raises(negation.NotNegatable, match="proposizionale"):
                negation.generate(p)
            return
    pytest.skip("no problem with a non-propositional hole and answer(sorry) in the source")


def test_refuting_a_statement_without_answer_is_possible(tmp_path):
    """This combination used to give ERROR, and it was wrong.

    The refutation mode only served problems with `answer(sorry)`, a minority. The
    `type_of%` route now exists and applies to any complete statement: here the
    challenge is generated, and the candidate is REJECTED because it does not prove
    the negation — not because the mode does not apply.
    """
    r = verify("JugglerConjecture.jugglerStep_36", _candidate(tmp_path, "False"),
               mode=REFUTATION, run_guard=False, timeout=900)
    assert r.status == REJECTED, r.render()
    passed = {c.name for c in r.checks if c.passed}
    assert "the problem admits a refutation" in passed
    details = " ".join(c.detail or "" for c in r.checks)
    assert "type_of%" in details


def test_a_statement_with_a_hole_cannot_be_refuted(tmp_path):
    """If the statement itself contains a `sorry`, its negation is not a well-posed
    assertion: neither of the two routes applies."""
    idx = ProblemIndex.load()
    with_hole = [q for q in idx.find(category="research open") if q.statement_has_sorry]
    if not with_hole:
        pytest.skip("no problem with a non-propositional hole in the index")
    r = verify(with_hole[0].theorem, _candidate(tmp_path, "False"),
               mode=REFUTATION, run_guard=False)
    assert r.status == ERROR
    assert "challenge negata" in r.message.lower()


def test_modalita_sconosciuta_viene_rifiutata(tmp_path):
    r = verify(PROBLEM, _candidate(tmp_path, "False"), mode="fantasia")
    assert r.status == ERROR
    assert "mode" in r.message.lower()


# --- integration: the two challenges are DIFFERENT statements ---------------
# These four tests start Lean: they are slow (about 30 seconds each).

def _reason(result) -> set[str]:
    return {c.name for c in result.checks
            if not c.passed and c.name != "syntactic pre-scan"}


def test_in_strict_mode_a_candidate_with_True_matches(tmp_path):
    """`answer(sorry)` becomes `True`, as in the archive: the statements match, so
    comparator reaches the axiom check."""
    r = verify(PROBLEM, _candidate(tmp_path, "sorry"), mode=STRICT,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "permitted axioms" in _reason(r), \
        f"expected rejection on the axioms (matching statements), got {_reason(r)}"
    assert "sorryAx" in r.errors


def test_in_strict_mode_a_candidate_with_False_does_not_match(tmp_path):
    """`answer(False)` gives `False ↔ P`: a different statement from the archive's,
    and comparator stops before the axioms."""
    r = verify(PROBLEM, _candidate(tmp_path, "False"), mode=STRICT,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "type identical to the original" in _reason(r)


def test_in_refutation_mode_a_candidate_with_False_matches(tmp_path):
    """This is the direction that counts: the negated challenge accepts the statement
    `False ↔ P`. With a real proof (not `sorry`) this would be a refutation
    verificata del problem aperto."""
    r = verify(PROBLEM, _candidate(tmp_path, "False"), mode=REFUTATION,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "permitted axioms" in _reason(r), \
        f"expected rejection on the axioms (matching statements), got {_reason(r)}"
    assert "sorryAx" in r.errors
    # the negated challenge has to have been generated, and to have compiled
    passed = {c.name for c in r.checks if c.passed}
    failed = {c.name for c in r.checks if not c.passed}
    assert "the problem admits a refutation" in passed
    assert "negated challenge generated" in passed
    # Compiling the challenge is not a check of its own: `prepare_challenge` does it
    # and leaves a FAILED check if it cannot. And had the challenge not compiled,
    # comparator could not have compared the types, so the rejection would be on a
    # different check, not on the axioms.
    assert "challenge module ready" not in failed


def test_in_refutation_mode_a_candidate_with_True_does_not_match(tmp_path):
    """The control: the negated challenge does not pass for the original one. If this
    test failed, the two modes would be verifying the same thing and the whole
    feature would be pointless."""
    r = verify(PROBLEM, _candidate(tmp_path, "sorry"), mode=REFUTATION,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "type identical to the original" in _reason(r)


# --- the general route: `type_of%`, for statements without `answer( )` --------
#
# This is the route that really matters: in Epoch AI's OEIS Open benchmark 43% of
# the accepted solutions are refutations, and most open problems
# have no `answer(sorry)` to invert. Without this route half the possible results
# would not even be verifiable.

PROBLEMA_SENZA_ANSWER = "PerfectNumbers.infinitely_many_even_perfect"


def test_the_type_of_route_generates_a_derived_target():
    idx = ProblemIndex.load()
    p = idx.get(PROBLEM)          # this one has `answer( )`
    s = negation.generate_by_kind(p)
    assert s.route == "type_of%"
    assert s.target == PROBLEM + negation.SUFFIX
    assert f"import {p.module}" in s.text
    assert f"¬ (type_of% @{PROBLEM})" in s.text
    assert "sorry" in s.text      # the challenge is a target, not a proof


def test_the_type_of_route_rejects_a_statement_with_a_hole():
    idx = ProblemIndex.load()
    with_hole = [q for q in idx.find(category="research open") if q.statement_has_sorry]
    if not with_hole:
        pytest.skip("no problem with a non-propositional hole in the index")
    with pytest.raises(negation.NotNegatable):
        negation.generate_by_kind(with_hole[0])


def test_the_guard_permits_exactly_one_extra_module():
    import guard
    src = "import FormalConjectures.Wikipedia.PerfectNumbers\ntheorem t : True := trivial\n"
    assert not guard.check_source(src).ok          # vietato di norma
    ok = guard.check_source(src, allowed_module="FormalConjectures.Wikipedia.PerfectNumbers")
    assert ok.ok                                   # permesso se dichiarato
    other = "import FormalConjectures.Wikipedia.JugglerConjecture\ntheorem t : True := trivial\n"
    assert not guard.check_source(
        other, allowed_module="FormalConjectures.Wikipedia.PerfectNumbers").ok
