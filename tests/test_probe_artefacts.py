"""Il verdict della probe: si legge dagli ASSIOMI, non dai messages di error.

Un error qui ha two facce, entrambe gravi: perdere un ritrovamento vero, o
dichiararne one che non c'è. La before versione di questo lettore contava i
messages di error per line e sbagliava: segnalava come «chiuse» tattiche che
avevano failed, e arrivava a dire che un statement E la sua negation erano
entrambi dimostrati. Ora il criterio è quello del verifier — one trial vale
only se la declaration non dipende da `sorryAx`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "verifier"))

import probe_artefacts as probe


def _map():
    return {"sonda_decide": ("decide", False),
            "sonda_decide_neg": ("decide", True),
            "sonda_plausible": ("plausible", False)}


def _esiti(output):
    return {(p["tactic"], p["negated"]): p["result"]
            for p in probe.read(output, _map())["trials"]}


def test_una_prova_senza_sorryAx_ha_chiuso():
    output = ("E0.lean:5:0: info: 'sonda_decide' depends on axioms: "
              "[propext, Classical.choice, Quot.sound]")
    assert _esiti(output)[("decide", False)] == "chiusa"


def test_una_prova_senza_assiomi_ha_chiuso():
    output = "E0.lean:5:0: info: 'sonda_decide' does not depend on any axioms"
    assert _esiti(output)[("decide", False)] == "chiusa"


def test_una_prova_che_dipende_da_sorryAx_non_ha_chiuso():
    """È il caso di `plausible`: non trova controesempi, lascia un `sorry`,
    il file compila e la declaration esiste. Non ha dimostrato niente."""
    output = "E0.lean:5:0: info: 'sonda_plausible' depends on axioms: [sorryAx]"
    assert _esiti(output)[("plausible", False)] == "aperta"


def test_una_dichiarazione_che_non_esiste_e_un_fallimento():
    assert _esiti("")[("decide", False)] == "aperta"


def test_la_negazione_dimostrata_si_chiama_confutata():
    output = "E0.lean:9:0: info: 'sonda_decide_neg' does not depend on any axioms"
    assert _esiti(output)[("decide", True)] == "confutata"


def test_un_controesempio_di_plausible_viene_riportato():
    output = ("E0.lean:5:2: error: Found a counter-example!\nn := 17\n"
              "E0.lean:5:0: info: 'sonda_plausible' depends on axioms: [sorryAx]")
    trials = probe.read(output, _map())["trials"]
    assert any(p["result"] == "counterexample" for p in trials)
    # e la trial in sé resta fallita: un counterexample non è one dimostrazione
    assert _esiti(output)[("plausible", False)] == "aperta"


def test_il_file_generato_chiede_gli_assiomi_di_ogni_prova():
    class FakeProblem:
        theorem = "Foo.bar"
        module = "FormalConjectures.Foo"
    code, mapping = probe.build(FakeProblem(), 200000)
    for theorem in mapping:
        assert f"theorem {theorem} :" in code
        assert f"#print axioms {theorem}" in code
    expected = sum(2 if also else 1 for _, _, also in probe.TACTICS)
    assert len(mapping) == expected


def test_un_file_che_non_compila_non_da_un_esito_pulito():
    """Il sesto falso positivo, del 12 settembre 2026.

    Su `Erdos628.erdos_628` la probe leggeva «aesop: chiusa, axioms: nessuno»
    mentre il file aveva un error di notazione `⟨...⟩`, e il verifier ha poi
    risposto REJECTED: il file non compila. Il candidato passava comunque da
    verify.py -- che e' il reason per cui nessun falso ritrovamento e' uscito da
    1188 enunciati -- ma la line mostrata a chi legge era ingannevole.
    """
    output = (
        "FormalConjectures/_Judge/E0.lean:6:8: error: Invalid `<...>` notation: "
        "The expected type is not an inductive type\n"
        "'sonda_aesop' does not depend on any axioms\n")
    results = probe.read(output, {"sonda_aesop": ("aesop", False)})["trials"]
    assert results[0]["result"] == "chiusa"          # resta un candidato, non un verdict
    assert "ATTENZIONE" in results[0]["detail"]
    assert "non compila" in results[0]["detail"] or "errors di compilazione" in results[0]["detail"]
    assert "verifier" in results[0]["detail"]


def test_senza_errori_il_dettaglio_resta_asciutto():
    results = probe.read("'sonda_aesop' does not depend on any axioms\n",
                        {"sonda_aesop": ("aesop", False)})["trials"]
    assert results[0]["detail"] == "axioms: nessuno"
