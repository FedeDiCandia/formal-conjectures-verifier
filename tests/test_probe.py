"""The automatic probe's verdict must not mistake a `sorry` for a proof."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "verifier"))

import probe_lean


def test_plausible_without_a_counterexample_does_not_close():
    messages = ("Unable to find a counter-example\n"
                "FormalConjectures/_Judge/E0.lean:5:0: warning: "
                "declaration uses 'sorry'")
    result, against = probe_lean.classify(messages, ok=True)
    assert result == "open"
    assert against is None


def test_a_counterexample_is_recognised():
    result, against = probe_lean.classify(
        "Found a counter-example!\nn := 4\nissue: 2 ∈ digits failed", ok=False)
    assert result == "counterexample"
    assert "counter-example" in against


def test_a_real_closure():
    result, _ = probe_lean.classify("", ok=True)
    assert result == "closed"


def test_timeout_and_heartbeats():
    assert probe_lean.classify("TIMED OUT after 60s", ok=False)[0] == "timed out"
    assert probe_lean.classify(
        "(deterministic) timeout at `whnf`, maximum number of heartbeats (400000)",
        ok=False)[0] == "heartbeats exhausted"


def test_reclassifying_downgrades_and_removes_the_flag(tmp_path):
    f = tmp_path / "probe.json"
    f.write_text(json.dumps([{
        "problem": "X", "module": "M", "statement": "true", "trials": [{
            "tactic": "plausible", "negated": False, "result": "closed",
            "seconds": 5.7, "counterexample": None,
            "messages": "Unable to find a counter-example\ndeclaration uses 'sorry'",
        }],
        "ATTENTION": "the tactic plausible returned closed on the direct form",
    }]), encoding="utf-8")
    assert probe_lean.reclassify(f) == 1
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data[0]["trials"][0]["result"] == "open"
    assert "ATTENTION" not in data[0]
