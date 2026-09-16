"""verify_free: verifying theorems that are NOT in the archive.

The use case that gave rise to it is A105020 ⟺ Goldbach (search/lean/). Here we
check that the verifier's new entry point has the same teeth as `verify`:

  * it accepts a correct proof of a statement in the challenge;
  * it rejects a DIFFERENT statement declared under the same name;
  * it rejects anyone leaning on the `sorry` proof of an imported open problem
    of the archive — this is why importing the archive's modules
    is not a loophole;
  * it rejects `sorry` in the candidate, axioms in the challenge, and theorems missing from it.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import config                                                    # noqa: E402
import guard                                                     # noqa: E402
from verify import ACCEPTED, ERROR, REJECTED, verify_free      # noqa: E402

MODULE = "FormalConjectures.Wikipedia.PerfectNumbers"

GOOD_CHALLENGE = f"""import {MODULE}

namespace ProvaLibera

theorem total_sum (n : ℕ) : n + 0 = n := by
  sorry

end ProvaLibera
"""

OPEN_CHALLENGE = f"""import {MODULE}

namespace ProvaLibera

theorem dispari_perfetto (n : ℕ) (hn : Nat.Perfect n) : Even n := by
  sorry

end ProvaLibera
"""


def setup_module(module):
    if config.check_installation():
        pytest.skip("environment not installed", allow_module_level=True)


def _file(tmp_path, name, text):
    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    return f


# --- without Lean -------------------------------------------------------------

def test_the_guard_allows_the_listed_modules_and_no_others():
    one = "import FormalConjectures.Wikipedia.PerfectNumbers\ntheorem t : True := trivial\n"
    two = "import FormalConjectures.Wikipedia.JugglerConjecture\ntheorem t : True := trivial\n"
    three = "import FormalConjectures.Wikipedia.Lemoine\ntheorem t : True := trivial\n"
    permissions = ("FormalConjectures.Wikipedia.PerfectNumbers",
                "FormalConjectures.Wikipedia.JugglerConjecture")
    assert guard.check_source(one, allowed_module=permissions).ok
    assert guard.check_source(two, allowed_module=permissions).ok
    assert not guard.check_source(three, allowed_module=permissions).ok
    # the single-string form stays valid
    assert guard.check_source(one, allowed_module=permissions[0]).ok
    assert not guard.check_source(two, allowed_module=permissions[0]).ok


def test_a_challenge_declaring_an_axiom_is_an_error(tmp_path):
    cand = _file(tmp_path, "c.lean", "theorem ProvaLibera.total_sum (n : ℕ) : n + 0 = n := rfl\n")
    challenge = "axiom trucco : False\ntheorem ProvaLibera.total_sum (n : ℕ) : n + 0 = n := by\n  sorry\n"
    r = verify_free(challenge, cand, ["ProvaLibera.total_sum"])
    assert r.status == ERROR and "assioma" in r.message


def test_a_theorem_not_declared_in_the_challenge_is_an_error(tmp_path):
    cand = _file(tmp_path, "c.lean", "theorem ProvaLibera.total_sum (n : ℕ) : n + 0 = n := rfl\n")
    r = verify_free(GOOD_CHALLENGE, cand, ["ProvaLibera.total_sum", "ProvaLibera.inesistente"])
    assert r.status == ERROR and "inesistente" in r.message


def test_a_candidate_with_sorry_is_rejected(tmp_path):
    cand = _file(tmp_path, "c.lean",
                 f"import {MODULE}\nnamespace ProvaLibera\n"
                 "theorem total_sum (n : ℕ) : n + 0 = n := by\n  sorry\nend ProvaLibera\n")
    r = verify_free(GOOD_CHALLENGE, cand, ["ProvaLibera.total_sum"], allowed_modules=(MODULE,))
    assert r.status == REJECTED


# --- with Lean and comparator -------------------------------------------------

def test_a_correct_proof_is_accepted(tmp_path):
    cand = _file(tmp_path, "c.lean",
                 f"import {MODULE}\nnamespace ProvaLibera\n"
                 "theorem total_sum (n : ℕ) : n + 0 = n := rfl\nend ProvaLibera\n")
    r = verify_free(GOOD_CHALLENGE, cand, ["ProvaLibera.total_sum"], allowed_modules=(MODULE,),
                      timeout=1500)
    assert r.status == ACCEPTED, (r.message, r.errors[-2000:])


def test_same_name_but_different_statement_is_rejected(tmp_path):
    cand = _file(tmp_path, "c.lean",
                 f"import {MODULE}\nnamespace ProvaLibera\n"
                 "theorem total_sum (n : ℕ) : 0 + n = n := Nat.zero_add n\nend ProvaLibera\n")
    r = verify_free(GOOD_CHALLENGE, cand, ["ProvaLibera.total_sum"], allowed_modules=(MODULE,),
                      timeout=1500)
    assert r.status == REJECTED, (r.message, r.errors[-2000:])


def test_leaning_on_an_open_problems_sorry_is_rejected(tmp_path):
    cand = _file(tmp_path, "c.lean",
                 f"import {MODULE}\nnamespace ProvaLibera\n"
                 "theorem dispari_perfetto (n : ℕ) (hn : Nat.Perfect n) : Even n :=\n"
                 "  PerfectNumbers.odd_perfect_number_conjecture n hn\nend ProvaLibera\n")
    r = verify_free(OPEN_CHALLENGE, cand, ["ProvaLibera.dispari_perfetto"],
                      allowed_modules=(MODULE,), timeout=1500)
    assert r.status == REJECTED, (r.message, r.errors[-2000:])
    text = r.raw_output + r.errors + r.message
    assert "sorryAx" in text or "xiom" in text, text[-2000:]


def test_an_incompatible_olean_is_a_tool_error_not_a_rejection():
    """The fault of 12 September 2026: REJECTED instead of ERROR."""
    from verify import _tool_error
    output = ("uncaught exception: failed to read file '/x/Sfida0.olean', "
              "incompatible header")
    assert _tool_error(output) is not None
    assert "lean4export-433" in _tool_error(output)
    assert _tool_error("error: unknown identifier 'foo'") is None
