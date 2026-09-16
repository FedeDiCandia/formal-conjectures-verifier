"""Il verdict della probe automatica non deve scambiare un `sorry` per one trial."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "verifier"))

import probe_lean


def test_plausible_senza_controesempio_non_chiude():
    messages = ("Unable to find a counter-example\n"
                "FormalConjectures/_Judge/E0.lean:5:0: warning: "
                "declaration uses 'sorry'")
    result, against = probe_lean.classify(messages, ok=True)
    assert result == "aperta"
    assert against is None


def test_controesempio_riconosciuto():
    result, against = probe_lean.classify(
        "Found a counter-example!\nn := 4\nissue: 2 ∈ digits failed", ok=False)
    assert result == "counterexample"
    assert "counter-example" in against


def test_chiusura_vera():
    result, _ = probe_lean.classify("", ok=True)
    assert result == "chiusa"


def test_tempo_scaduto_e_heartbeat():
    assert probe_lean.classify("TEMPO SCADUTO after 60s", ok=False)[0] == "tempo scaduto"
    assert probe_lean.classify(
        "(deterministic) timeout at `whnf`, maximum number of heartbeats (400000)",
        ok=False)[0] == "heartbeat esauriti"


def test_riclassifica_declassa_e_toglie_attenzione(tmp_path):
    f = tmp_path / "probe.json"
    f.write_text(json.dumps([{
        "problem": "X", "module": "M", "statement": "vero", "trials": [{
            "tactic": "plausible", "negated": False, "result": "chiusa",
            "seconds": 5.7, "counterexample": None,
            "messages": "Unable to find a counter-example\ndeclaration uses 'sorry'",
        }],
        "ATTENZIONE": "la tactic plausible ha chiusa la forma diritta",
    }]), encoding="utf-8")
    assert probe_lean.reclassify(f) == 1
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data[0]["trials"][0]["result"] == "aperta"
    assert "ATTENZIONE" not in data[0]
