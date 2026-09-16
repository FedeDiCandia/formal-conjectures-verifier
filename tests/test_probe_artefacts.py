"""The probe's verdict: it is read from the AXIOMS, not from the error messages.

An error here has two faces, both serious: losing a real finding, or
declaring one that is not there. The first version of this reader counted the
error messages by line and got it wrong: it reported as "closed" tactics that
had failed, and went as far as saying that a statement AND its negation were
both proved. The criterion now is the verifier's — a proof counts
only if the declaration does not depend on `sorryAx`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "verifier"))

import probe_artefacts as probe


def _map():
    return {"probedecide": ("decide", False),
            "probedecide_neg": ("decide", True),
            "probeplausible": ("plausible", False)}


def _outcomes(output):
    return {(p["tactic"], p["negated"]): p["result"]
            for p in probe.read(output, _map())["trials"]}


def test_a_proof_without_sorryAx_has_closed():
    output = ("E0.lean:5:0: info: 'probedecide' depends on axioms: "
              "[propext, Classical.choice, Quot.sound]")
    assert _outcomes(output)[("decide", False)] == "closed"


def test_a_proof_with_no_axioms_has_closed():
    output = "E0.lean:5:0: info: 'probedecide' does not depend on any axioms"
    assert _outcomes(output)[("decide", False)] == "closed"


def test_a_proof_that_depends_on_sorryAx_has_not_closed():
    """This is `plausible`'s case: it finds no counterexample, leaves a `sorry`,
    the file compiles and the declaration exists. It has proved nothing."""
    output = "E0.lean:5:0: info: 'probeplausible' depends on axioms: [sorryAx]"
    assert _outcomes(output)[("plausible", False)] == "open"


def test_a_declaration_that_does_not_exist_is_a_failure():
    assert _outcomes("")[("decide", False)] == "open"


def test_a_proved_negation_is_called_a_refutation():
    output = "E0.lean:9:0: info: 'probedecide_neg' does not depend on any axioms"
    assert _outcomes(output)[("decide", True)] == "refuted"


def test_a_plausible_counterexample_is_reported():
    output = ("E0.lean:5:2: error: Found a counter-example!\nn := 17\n"
              "E0.lean:5:0: info: 'probeplausible' depends on axioms: [sorryAx]")
    trials = probe.read(output, _map())["trials"]
    assert any(p["result"] == "counterexample" for p in trials)
    # and the attempt itself stays failed: a counterexample is not a proof
    assert _outcomes(output)[("plausible", False)] == "open"


def test_the_generated_file_asks_for_each_proofs_axioms():
    class FakeProblem:
        theorem = "Foo.bar"
        module = "FormalConjectures.Foo"
    code, mapping = probe.build(FakeProblem(), 200000)
    for theorem in mapping:
        assert f"theorem {theorem} :" in code
        assert f"#print axioms {theorem}" in code
    expected = sum(2 if also else 1 for _, _, also in probe.TACTICS)
    assert len(mapping) == expected


def test_a_file_that_does_not_compile_gives_no_clean_verdict():
    """The sixth false positive, 12 September 2026.

    On `Erdos628.erdos_628` the probe read "aesop: closed, axioms: none"
    while the file had a notation error `⟨...⟩`, and the verifier then
    answered REJECTED: the file does not compile. The candidate still went through
    verify.py -- which is why no false finding came out of
    1188 statements -- but the line shown to the reader was misleading.
    """
    output = (
        "FormalConjectures/_Judge/E0.lean:6:8: error: Invalid `<...>` notation: "
        "The expected type is not an inductive type\n"
        "'probeaesop' does not depend on any axioms\n")
    results = probe.read(output, {"probeaesop": ("aesop", False)})["trials"]
    assert results[0]["result"] == "closed"          # still a candidate, not a verdict
    assert "ATTENTION" in results[0]["detail"]
    assert "does not compile" in results[0]["detail"] or "compilation errors" in results[0]["detail"]
    assert "verifier" in results[0]["detail"]


def test_with_no_errors_the_detail_stays_terse():
    results = probe.read("'probeaesop' does not depend on any axioms\n",
                        {"probeaesop": ("aesop", False)})["trials"]
    assert results[0]["detail"] == "axioms: none"
