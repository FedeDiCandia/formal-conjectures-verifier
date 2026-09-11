"""Il verdetto della sonda automatica non deve scambiare un `sorry` per una prova."""
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "scripts"))
sys.path.insert(0, str(RADICE / "verifier"))

import sonda_lean


def test_plausible_senza_controesempio_non_chiude():
    messaggi = ("Unable to find a counter-example\n"
                "FormalConjectures/_Judge/E0.lean:5:0: warning: "
                "declaration uses 'sorry'")
    esito, contro = sonda_lean.classifica(messaggi, ok=True)
    assert esito == "aperta"
    assert contro is None


def test_controesempio_riconosciuto():
    esito, contro = sonda_lean.classifica(
        "Found a counter-example!\nn := 4\nissue: 2 ∈ digits failed", ok=False)
    assert esito == "controesempio"
    assert "counter-example" in contro


def test_chiusura_vera():
    esito, _ = sonda_lean.classifica("", ok=True)
    assert esito == "chiusa"


def test_tempo_scaduto_e_heartbeat():
    assert sonda_lean.classifica("TEMPO SCADUTO dopo 60s", ok=False)[0] == "tempo scaduto"
    assert sonda_lean.classifica(
        "(deterministic) timeout at `whnf`, maximum number of heartbeats (400000)",
        ok=False)[0] == "heartbeat esauriti"


def test_riclassifica_declassa_e_toglie_attenzione(tmp_path):
    f = tmp_path / "sonda.json"
    f.write_text(json.dumps([{
        "problema": "X", "modulo": "M", "enunciato": "vero", "prove": [{
            "tattica": "plausible", "negato": False, "esito": "chiusa",
            "secondi": 5.7, "controesempio": None,
            "messaggi": "Unable to find a counter-example\ndeclaration uses 'sorry'",
        }],
        "ATTENZIONE": "la tattica plausible ha chiusa la forma diritta",
    }]), encoding="utf-8")
    assert sonda_lean.riclassifica(f) == 1
    dati = json.loads(f.read_text(encoding="utf-8"))
    assert dati[0]["prove"][0]["esito"] == "aperta"
    assert "ATTENZIONE" not in dati[0]
