"""Il verdetto della sonda: si legge dagli ASSIOMI, non dai messaggi di errore.

Un errore qui ha due facce, entrambe gravi: perdere un ritrovamento vero, o
dichiararne uno che non c'è. La prima versione di questo lettore contava i
messaggi di errore per riga e sbagliava: segnalava come «chiuse» tattiche che
avevano fallito, e arrivava a dire che un enunciato E la sua negation erano
entrambi dimostrati. Ora il criterio è quello del verificatore — una prova vale
solo se la dichiarazione non dipende da `sorryAx`.
"""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "scripts"))
sys.path.insert(0, str(RADICE / "verifier"))

import probe_artefacts as sonda


def _mappa():
    return {"sonda_decide": ("decide", False),
            "sonda_decide_neg": ("decide", True),
            "sonda_plausible": ("plausible", False)}


def _esiti(uscita):
    return {(p["tattica"], p["negato"]): p["esito"]
            for p in sonda.leggi(uscita, _mappa())["prove"]}


def test_una_prova_senza_sorryAx_ha_chiuso():
    uscita = ("E0.lean:5:0: info: 'sonda_decide' depends on axioms: "
              "[propext, Classical.choice, Quot.sound]")
    assert _esiti(uscita)[("decide", False)] == "chiusa"


def test_una_prova_senza_assiomi_ha_chiuso():
    uscita = "E0.lean:5:0: info: 'sonda_decide' does not depend on any axioms"
    assert _esiti(uscita)[("decide", False)] == "chiusa"


def test_una_prova_che_dipende_da_sorryAx_non_ha_chiuso():
    """È il caso di `plausible`: non trova controesempi, lascia un `sorry`,
    il file compila e la dichiarazione esiste. Non ha dimostrato niente."""
    uscita = "E0.lean:5:0: info: 'sonda_plausible' depends on axioms: [sorryAx]"
    assert _esiti(uscita)[("plausible", False)] == "aperta"


def test_una_dichiarazione_che_non_esiste_e_un_fallimento():
    assert _esiti("")[("decide", False)] == "aperta"


def test_la_negazione_dimostrata_si_chiama_confutata():
    uscita = "E0.lean:9:0: info: 'sonda_decide_neg' does not depend on any axioms"
    assert _esiti(uscita)[("decide", True)] == "confutata"


def test_un_controesempio_di_plausible_viene_riportato():
    uscita = ("E0.lean:5:2: error: Found a counter-example!\nn := 17\n"
              "E0.lean:5:0: info: 'sonda_plausible' depends on axioms: [sorryAx]")
    prove = sonda.leggi(uscita, _mappa())["prove"]
    assert any(p["esito"] == "controesempio" for p in prove)
    # e la prova in sé resta fallita: un controesempio non è una dimostrazione
    assert _esiti(uscita)[("plausible", False)] == "aperta"


def test_il_file_generato_chiede_gli_assiomi_di_ogni_prova():
    class FintoProblema:
        theorem = "Foo.bar"
        module = "FormalConjectures.Foo"
    codice, mappa = sonda.costruisci(FintoProblema(), 200000)
    for teorema in mappa:
        assert f"theorem {teorema} :" in codice
        assert f"#print axioms {teorema}" in codice
    attese = sum(2 if anche else 1 for _, _, anche in sonda.TATTICHE)
    assert len(mappa) == attese


def test_un_file_che_non_compila_non_da_un_esito_pulito():
    """Il sesto falso positivo, del 12 settembre 2026.

    Su `Erdos628.erdos_628` la sonda leggeva «aesop: chiusa, assiomi: nessuno»
    mentre il file aveva un errore di notazione `⟨...⟩`, e il verificatore ha poi
    risposto RIFIUTATO: il file non compila. Il candidato passava comunque da
    verify.py -- che e' il motivo per cui nessun falso ritrovamento e' uscito da
    1188 enunciati -- ma la riga mostrata a chi legge era ingannevole.
    """
    uscita = (
        "FormalConjectures/_Judge/E0.lean:6:8: error: Invalid `<...>` notation: "
        "The expected type is not an inductive type\n"
        "'sonda_aesop' does not depend on any axioms\n")
    esiti = sonda.leggi(uscita, {"sonda_aesop": ("aesop", False)})["prove"]
    assert esiti[0]["esito"] == "chiusa"          # resta un candidato, non un verdetto
    assert "ATTENZIONE" in esiti[0]["dettaglio"]
    assert "non compila" in esiti[0]["dettaglio"] or "errori di compilazione" in esiti[0]["dettaglio"]
    assert "verificatore" in esiti[0]["dettaglio"]


def test_senza_errori_il_dettaglio_resta_asciutto():
    esiti = sonda.leggi("'sonda_aesop' does not depend on any axioms\n",
                        {"sonda_aesop": ("aesop", False)})["prove"]
    assert esiti[0]["dettaglio"] == "assiomi: nessuno"
