"""The probe's five false positives, one test each.

Five "findings" announced and all five false, by five different mechanisms. The
common cause is a single one, and it is worth writing down: **the probe was judging
its own output.** Every layer of judgement I had added to it — "the file compiles",
"which lines carry errors", "which axioms come out" — was a poorer imitation of what
`verify.py` really does, and each had a different hole.

The structural fix is that the probe **proposes** and `verify.py` **judges**. These
tests protect the five holes in such a way that, if anyone puts a verdict back inside
the probe, they break.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "verifier"))

import pytest
import probe_artefacts as probe
import probe_lean


class FakeProblem:
    theorem = "Foo.bar"
    module = "FormalConjectures.Foo"


# --- 1. `plausible` leaves a `sorry` and the file compiles -------------------

def test_1_plausible_without_a_counterexample_proved_nothing():
    """First false positive. When `plausible` finds no counterexample it writes
    "Unable to find a counter-example" and leaves a `sorry`: the file compiles with a
    warning. The verdict only looked at whether it compiled."""
    result, _ = probe_lean.classify(
        "Unable to find a counter-example\n"
        "E0.lean:5:0: warning: declaration uses 'sorry'", ok=True)
    assert result == "open"
    # and under the axiom criterion, the same thing
    r = probe.read("'sonda_plausible' depends on axioms: [sorryAx]",
                    {"sonda_plausible": ("plausible", False)})
    assert r["trials"][0]["result"] == "open"


# --- 2. two explorations swapping each other's messages ---------------------

def test_2_exploration_slots_are_exclusive():
    """Second false positive. The inspection file had a fixed name (`E0.lean`), so two
    concurrent explorations overwrote it and each read the other's messages: a trivial
    tactic appeared to have closed a topology problem, and the messages belonged to a
    graph problem."""
    import explore
    assert hasattr(explore, "_exclusive_slot"), (
        "the locking mechanism has been removed: two explorations "
        "concorrenti tornerebbero a mescolarsi")
    assert explore.AVAILABLE_SLOTS >= 2
    import inspect
    assert "flock" in inspect.getsource(explore._exclusive_slot), (
        "the lock has to hold BETWEEN PROCESSES, not only between threads")


# --- 3. the verdict read off the error lines --------------------------------

def test_3_the_verdict_is_read_by_name_not_by_line():
    """Third false positive. The reader attributed Lean's errors to the wrong
    declaration, and went as far as saying that a statement AND its negation were both
    proved — a logical impossibility."""
    output = ("E0.lean:9:2: error: something is wrong here\n"
              "'sonda_decide' depends on axioms: [sorryAx]\n"
              "'sonda_decide_neg' does not depend on any axioms")
    mapping = {"sonda_decide": ("decide", False), "sonda_decide_neg": ("decide", True)}
    results = {(p["tactic"], p["negated"]): p["result"]
             for p in probe.read(output, mapping)["trials"]}
    # the error line must not move any verdict: the names are what count
    assert results[("decide", False)] == "open"
    assert results[("decide", True)] == "refuted"


# --- 4. `type_of%` without `@` tries a different statement -------------------

def test_4_type_of_has_to_be_written_with_the_at_sign():
    """Fourth false positive. `type_of% Foo` without `@` makes Lean instantiate the
    implicit arguments as metavariables: the probe was trying a DIFFERENT statement
    from the archive's, and `aesop` "refuted" Agrawal's conjecture while the real
    verifier rejected the same proof."""
    code, _ = probe.build(FakeProblem(), 200000)
    assert "type_of% @Foo.bar" in code
    assert "type_of% Foo.bar" not in code.replace("type_of% @Foo.bar", "")


# --- 5. l'environment sbagliato -----------------------------------------------

def test_5_it_refuses_to_run_against_the_wrong_archive(tmp_path):
    """Fifth false positive. The probe was running with the default index (bench-v1)
    while the targets had been chosen on `main`: the imports failed, the messages were
    rubbish, and the reader read successes into them."""
    import json
    import config
    targets = tmp_path / "targets.json"
    targets.write_text(json.dumps(
        {"snapshot": "external/fc-main 0a8b856c", "candidates": []}), encoding="utf-8")
    if "fc-main" in str(config.ARCHIVE):
        pytest.skip("this test applies when the archive in use is NOT fc-main")
    with pytest.raises(SystemExit) as e:
        probe.check_environment(targets)
    assert "AMBIENTE SBAGLIATO" in str(e.value)


# --- the structural fix -----------------------------------------------------

def test_the_probe_does_not_flag_without_the_verifier():
    """The constraint that makes a sixth false positive of the same family
    impossible: the flag is raised ONLY after an ACCEPTED that
    arriva da `verify.py`."""
    import inspect
    src = inspect.getsource(probe.main)
    assert "confirm_with_verifier" in src, (
        "the probe has to pass its candidates to the verifier")
    # every assignment of the flag has to sit in a branch that checks ACCEPTED
    pieces = src.split('entry["ATTENTION"]')
    for before in pieces[:-1]:
        assert "ACCEPTED" in before[-400:], (
            "an ATTENTION is raised without going through the verifier")


def test_confirming_with_the_verifier_builds_the_right_candidate():
    """In the negated form it has to use refutation mode and the `@`."""
    import inspect
    src = inspect.getsource(probe.confirm_with_verifier)
    assert "type_of% @{problem.theorem}" in src
    assert "REFUTATION" in src and "STRICT" in src
    assert "run_guard=False" in src   # the candidate imports the module on purpose
