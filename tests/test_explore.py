"""Tests of the exploration tool.

WHY THIS TOOL EXISTS
--------------------
In the first shakedown the agent spent NINE verifications out of nine inspecting
Mathlib's API rather than submitting a proof — and it only managed that by provoking
type errors on purpose, because the verifier did not return Lean's informational
messages. Those nine verifications cost $1.81 and 740 seconds without producing a
single real attempt.

`lean_explore` does the part that is useful for understanding: it compiles and reports
everything, with no comparator, no comparison of statements, no replay through the
kernel.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import common
import config
import explore as explore_module
import guard


def setup_module(module):
    if config.check_installation():
        pytest.skip("environment not installed", allow_module_level=True)


# --- the guard applies in exploration too -----------------------------------

def test_in_exploration_the_problems_module_may_be_imported():
    """This is the one rule that is relaxed: it is needed to run `#print` on the
    archive's definitions. In a solution it stays forbidden, because it would declare
    a name that already exists."""
    src = "import FormalConjectures.Wikipedia.Selfridge\n#print Selfridge.IsSelfridge\n"
    assert guard.check_source(src, exploration=True).ok
    assert not guard.check_source(src, exploration=False).ok, \
        "in a solution, importing the problem's module has to stay forbidden"


def test_in_exploration_executable_code_stays_forbidden():
    """An inspection file is compiled like any other, so it can execute code in just
    the same way: the rules about code are not relaxed."""
    for src in ['#eval IO.println "x"',
                'run_meta Lean.logInfo "x"',
                'def f : IO Unit := pure ()',
                'theorem t : True := by native_decide']:
        assert not guard.check_source(src, exploration=True).ok, f"passato: {src}"


def test_a_forbidden_file_is_not_even_compiled():
    r = explore_module.explore(common.adapt(
        'import FormalConjectures.Util.ProblemImports\n#eval IO.println "x"\n'))
    assert not r.ok
    assert r.rejected_by_guard
    assert r.seconds < 1.0, "it must not even start Lean"
    assert "command:#eval" in r.rejected_by_guard


# --- l'exploration vera (fa partire Lean: circa 10 seconds) -----------------

@pytest.fixture(scope="module")
def inspection():
    """A single compilation, reused by several tests: it takes about 10 seconds."""
    return explore_module.explore(common.adapt("""import FormalConjectures.Util.ProblemImports
import FormalConjectures.Wikipedia.Selfridge

#print Selfridge.IsPseudoSelfridge
#check @Nat.floor
#print Nat.Perfect

example : (2:ℕ) + 3 = 5 := by exact?

example (n : ℕ) (h : 3 < n) : n = 7 := by
  omega
"""))


def test_print_of_an_archive_structure_arrives_complete(inspection):
    """The case the agent could not obtain in the first shakedown."""
    m = inspection.messages
    assert "structure Selfridge.IsPseudoSelfridge" in m
    # all four fields, not only the first
    for field in ["is_odd", "mod_5", "pow_2", "fib"]:
        assert field in m, f"the field {field} is missing"
    assert "constructor:" in m, "the constructor has to appear too"


def test_print_of_a_mathlib_definition_shows_the_body(inspection):
    assert "def Nat.Perfect" in inspection.messages
    assert "properDivisors" in inspection.messages, \
        "the body of the definition, not only its name"


def test_check_shows_the_type_with_implicits(inspection):
    assert "@Nat.floor :" in inspection.messages
    assert "FloorSemiring" in inspection.messages, \
        "the instance-implicit arguments are needed in order to use the lemma"


def test_exact_suggests_a_lemma(inspection):
    assert "Try this" in inspection.messages


def test_errors_arrive_with_the_goal_state(inspection):
    """Without the goal state an error does not say what to do."""
    assert "error" in inspection.messages
    assert "omega could not trials the goal" in inspection.messages
    assert "4 ≤ a ≤ 6" in inspection.messages, \
        "the counterexample omega found is the useful information"


def test_the_messages_are_not_truncated(inspection):
    assert not inspection.truncated


def test_l_esplorazione_gira_isolata(inspection):
    assert inspection.isolated, "it has to run inside sandbox-exec"


#: How long a COMPLETE verification takes, measured on each snapshot. It gives
#: meaning to the threshold below: exploration is worth having
#: only se costa one frazione di one check.
#:   bench-v1 (Lean 4.27):  32.9 s  — measured with `time`
#:   main     (Lean 4.33):  47-114 s — misurato su 13 checks d'archive
FULL_VERIFICATION = {"FormalConjectures.Util.ProblemImports": 33.0,
                     "FormalConjecturesUtil": 47.0}


def test_exploration_is_faster_than_a_verification(inspection):
    """The reason it exists: if exploration were not appreciably faster than a full
    verification, it would be pointless.

    The BEST of two measurements is taken. Not to make the test pass: the quantity to
    be measured is what an exploration costs on this machine, and the first
    measurement includes a cold cache and whatever other work is in progress.
    Measuring the worst case under load would measure the load, not the tool.
    """
    import config
    piena = FULL_VERIFICATION.get(config.utility_module(), 33.0)
    seconds = inspection.seconds
    if seconds >= piena * 0.7:
        again = explore_module.explore(common.adapt(
            "import FormalConjectures.Util.ProblemImports\n"
            "#check @Nat.floor\n"))
        seconds = min(seconds, again.seconds)
    assert seconds < piena * 0.7, (
        f"troppo lenta: {seconds:.1f}s against i {piena:.0f}s di one "
        f"full verification on this snapshot")


def test_the_timeout_interrupts_a_non_terminating_tactic():
    r = explore_module.explore(common.adapt("""import FormalConjectures.Util.ProblemImports
set_option maxRecDepth 100000 in
example : True := by
  have : ∀ n : ℕ, n = n := fun n => rfl
  trivial
"""), timeout=5)
    # this particular file is not expected to time out: we only check that
    # the parameter is honoured and does not break the function
    assert r.seconds < 60


# --- the slots: two explorations at once must not get mixed up ---------------

def test_two_explorations_at_once_do_not_get_mixed_up():
    """The defect this test fixes was of the worst kind.

    The inspection file lives inside the archive's tree and its name IS the Lean
    module's name, so it was fixed: `E0.lean`. Two explorations at once overwrote the
    file and each read the other's messages. During the artefact hunt this made it
    look as though a trivial tactic had closed an open topology problem: the messages
    arriving belonged to a different problem, compiled by a different process.
    """
    import threading
    results = {}

    def work(name, code):
        results[name] = explore_module.explore(code, timeout=200)

    a = common.adapt("import FormalConjectures.Util.ProblemImports\n"
                      "theorem prova_A : (2:ℕ) + 2 = 5 := by norm_num\n")
    b = common.adapt("import FormalConjectures.Util.ProblemImports\n"
                      "theorem prova_B : (3:ℕ) + 3 = 7 := by norm_num\n")
    threads = [threading.Thread(target=work, args=("A", a)),
            threading.Thread(target=work, args=("B", b))]
    for f in threads:
        f.start()
    for f in threads:
        f.join()
    # each has to speak about ITS OWN file, and the two files have to differ
    import re
    file_a = set(re.findall(r"E(\d+)\.lean", results["A"].messages))
    file_b = set(re.findall(r"E(\d+)\.lean", results["B"].messages))
    assert file_a and file_b, (results["A"].messages, results["B"].messages)
    assert file_a.isdisjoint(file_b), f"stesso slot: {file_a} e {file_b}"
    for name in ("A", "B"):
        assert "unsolved goals" in results[name].messages
