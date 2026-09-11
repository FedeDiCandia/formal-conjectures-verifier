"""Il lettore dei messaggi della sonda: è la parte che può sbagliare in silenzio.

Un errore qui ha due facce, entrambe gravi: perdere un ritrovamento vero, o
dichiararne uno che non c'è. I test sono di solo testo, senza Lean.
"""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "scripts"))
sys.path.insert(0, str(RADICE / "verifier"))

import sonda_artefatti as sonda


def _mappa():
    """Tre tattiche a righe note, come le costruisce `costruisci`."""
    return {10: ("decide", False), 20: ("decide", True), 30: ("plausible", False)}


def test_una_tattica_senza_messaggi_ha_chiuso():
    r = sonda.leggi("", _mappa())
    esiti = {(p["tattica"], p["negato"]): p["esito"] for p in r["prove"]}
    assert esiti[("decide", False)] == "chiusa"
    assert esiti[("decide", True)] == "confutata"


def test_un_errore_marca_solo_la_sua_tattica():
    uscita = "prova.lean:11:2: error: failed to synthesize Decidable"
    esiti = {(p["tattica"], p["negato"]): p["esito"]
             for p in sonda.leggi(uscita, _mappa())["prove"]}
    assert esiti[("decide", False)] == "aperta"      # riga 11 -> tattica a riga 10
    assert esiti[("decide", True)] == "confutata"    # l'altra non è toccata


def test_plausible_che_lascia_un_sorry_non_ha_chiuso():
    uscita = ("prova.lean:31:0: warning: declaration uses 'sorry'\n"
              "Unable to find a counter-example")
    esiti = {(p["tattica"], p["negato"]): p["esito"]
             for p in sonda.leggi(uscita, _mappa())["prove"]}
    assert esiti[("plausible", False)] == "aperta"


def test_un_controesempio_viene_riconosciuto_e_riportato():
    uscita = "prova.lean:31:2: error: Found a counter-example!\nn := 17"
    prove = sonda.leggi(uscita, _mappa())["prove"]
    p = [x for x in prove if x["tattica"] == "plausible"][0]
    assert p["esito"] == "controesempio"
    assert "counter-example" in p["dettaglio"]


def test_il_file_generato_ha_una_riga_per_tattica():
    class FintoProblema:
        theorem = "Foo.bar"
        module = "FormalConjectures.Foo"
    codice, mappa = sonda.costruisci(FintoProblema(), 200000)
    righe = codice.split("\n")
    assert righe[1] == "import FormalConjectures.Foo"
    for riga, (nome, negato) in mappa.items():
        # la riga mappata contiene la tattica, quella sopra la dichiara
        assert "theorem sonda_" in righe[riga - 1], righe[riga - 1]
        assert ("_neg" in righe[riga - 1]) == negato
    attese = sum(2 if anche else 1 for _, _, anche in sonda.TATTICHE)
    assert len(mappa) == attese
