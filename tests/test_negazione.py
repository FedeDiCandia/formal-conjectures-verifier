"""
Test delle sfide "negate".

IL PROBLEMA CHE RISOLVONO
-------------------------
107 problemi ancora APERTI dell'archivio sono formalizzati cosi':

    theorem congettura : answer(sorry) ↔ P := by sorry

e l'opzione predefinita dell'archivio trasforma `answer(sorry)` in `True`.
L'enunciato che Lean vede e' quindi `True ↔ P`: l'affermazione che la risposta
alla domanda e' SI'.

Se per uno di quei problemi la risposta giusta fosse NO, il teorema com'e'
scritto sarebbe FALSO e indimostrabile, e chi trovasse la confutazione non
avrebbe modo di farla verificare. La sfida negata gli da' quel modo:
`answer(False) ↔ P`, cioe' `¬P`.

COME SI COLLAUDA SENZA RISOLVERE UN PROBLEMA APERTO
---------------------------------------------------
Nessuno di quei 107 problemi e' dimostrabile in alcuna direzione: sono aperti.
Ma comparator confronta gli ENUNCIATI prima di controllare gli assiomi, e questo
basta.

Si prende un candidato con la dimostrazione lasciata a `sorry`:
  * se l'enunciato COMBACIA con la sfida, comparator arriva al controllo degli
    assiomi e rifiuta per `sorryAx`;
  * se l'enunciato DIFFERISCE, comparator si ferma prima e rifiuta per
    "statement do not match".

Il motivo del rifiuto dice quindi se gli enunciati combaciano. Quattro
combinazioni bastano a dimostrare che le due sfide sono enunciati distinti e che
funzionano entrambe, senza dimostrare nulla di matematico.
"""
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))

import comune
import config
import negazione
from index import ProblemIndex
from verify import verify, CONFUTAZIONE, STRETTA, REJECTED, ERROR

#: Scelto perche' l'enunciato usa solo `Nat.Perfect` di Mathlib (nessuna
#: definizione locale da ricopiare) e perche' il suo file contiene TRE problemi
#: con `answer(sorry)`: serve a verificare che la sostituzione tocchi solo
#: quello bersaglio.
PROBLEMA = "PerfectNumbers.infinitely_many_perfect"

_CANDIDATO = """import FormalConjectures.Util.ProblemImports

namespace PerfectNumbers

open Nat

@[category research open, AMS 11]
theorem infinitely_many_perfect :
    answer({risposta}) ↔ {{n : ℕ | Perfect n}}.Infinite := by
  sorry

end PerfectNumbers
"""


def setup_module(module):
    if config.check_installation():
        pytest.skip("ambiente non installato", allow_module_level=True)
    if not config.INDEX_FILE.is_file():
        pytest.skip("indice mancante", allow_module_level=True)


@pytest.fixture(scope="module")
def indice():
    return ProblemIndex.load()


def _candidato(tmp_path, risposta: str) -> Path:
    f = tmp_path / f"candidato_{risposta}.lean"
    f.write_text(comune.adatta(_CANDIDATO.format(risposta=risposta)),
                 encoding="utf-8")
    return f


# --- generazione (veloce, senza Lean) ---------------------------------------

def test_la_sostituzione_avviene_solo_nel_teorema_bersaglio(indice):
    """Il file di PerfectNumbers contiene tre problemi con `answer(sorry)`.
    Invertirli tutti darebbe una sfida diversa da quella richiesta."""
    sfida = negazione.genera(indice.get(PROBLEMA))
    corpo = sfida.testo.split("-/\n", 1)[1]     # via l'intestazione generata
    assert sfida.sostituzioni == 1
    assert corpo.count("answer(False)") == 1
    assert corpo.count("answer(sorry)") >= 1, \
        "gli altri problemi del file devono restare come erano"


def test_la_sfida_dichiara_di_essere_generata(indice):
    """Chi apre il file deve capire subito che non e' un file dell'archivio."""
    sfida = negazione.genera(indice.get(PROBLEMA))
    assert "SFIDA NEGATA" in sfida.testo
    assert "generato automaticamente" in sfida.testo
    assert PROBLEMA in sfida.testo


def test_un_problema_senza_answer_non_si_puo_negare(indice):
    """Un enunciato senza `answer( )` afferma direttamente una proposizione:
    la sua negazione non e' un problema dell'archivio, e' un'altra cosa."""
    with pytest.raises(negazione.NonNegabile, match="non contiene"):
        negazione.genera(indice.get("JugglerConjecture.jugglerStep_36"))


def test_un_buco_answer_non_proposizionale_non_si_puo_negare(indice):
    """Se la risposta e' un numero o un insieme non c'e' un verso da invertire:
    c'e' un valore da fornire."""
    con_buco = indice.find(has_answer_hole=True)
    assert con_buco, "l'indice dovrebbe contenerne"
    for p in con_buco:
        if p.answer_placeholder_in_source:
            with pytest.raises(negazione.NonNegabile, match="proposizionale"):
                negazione.genera(p)
            return
    pytest.skip("nessun problema con buco non proposizionale e answer(sorry) nel sorgente")


def test_verify_rifiuta_la_modalita_confutazione_dove_non_ha_senso(tmp_path):
    r = verify("JugglerConjecture.jugglerStep_36", _candidato(tmp_path, "False"),
               modalita=CONFUTAZIONE, run_guard=False)
    assert r.status == ERROR
    assert "sfida negata" in r.message.lower()


def test_modalita_sconosciuta_viene_rifiutata(tmp_path):
    r = verify(PROBLEMA, _candidato(tmp_path, "False"), modalita="fantasia")
    assert r.status == ERROR
    assert "modalita" in r.message.lower()


# --- integrazione: le due sfide sono enunciati DIVERSI ----------------------
# Questi quattro test fanno partire Lean: sono lenti (circa 30 secondi ciascuno).

def _motivo(risultato) -> set[str]:
    return {c.name for c in risultato.checks
            if not c.passed and c.name != "controllo sintattico preventivo"}


def test_in_modalita_stretta_il_candidato_con_True_combacia(tmp_path):
    """`answer(sorry)` diventa `True`, come nell'archivio: gli enunciati
    combaciano, quindi comparator arriva al controllo degli assiomi."""
    r = verify(PROBLEMA, _candidato(tmp_path, "sorry"), modalita=STRETTA,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "assiomi ammessi" in _motivo(r), \
        f"atteso rifiuto per gli assiomi (enunciati combacianti), ottenuto {_motivo(r)}"
    assert "sorryAx" in r.errors


def test_in_modalita_stretta_il_candidato_con_False_non_combacia(tmp_path):
    """`answer(False)` da' `False ↔ P`: un enunciato diverso da quello
    dell'archivio, e comparator si ferma prima degli assiomi."""
    r = verify(PROBLEMA, _candidato(tmp_path, "False"), modalita=STRETTA,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "tipo identico all'originale" in _motivo(r)


def test_in_modalita_confutazione_il_candidato_con_False_combacia(tmp_path):
    """E' il verso che conta: la sfida negata accetta l'enunciato `False ↔ P`.
    Con una dimostrazione vera (non `sorry`) questo sarebbe una confutazione
    verificata del problema aperto."""
    r = verify(PROBLEMA, _candidato(tmp_path, "False"), modalita=CONFUTAZIONE,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "assiomi ammessi" in _motivo(r), \
        f"atteso rifiuto per gli assiomi (enunciati combacianti), ottenuto {_motivo(r)}"
    assert "sorryAx" in r.errors
    # la sfida negata deve essere stata generata, e deve aver compilato
    superati = {c.name for c in r.checks if c.passed}
    falliti = {c.name for c in r.checks if not c.passed}
    assert "il problema ammette una confutazione" in superati
    assert "la sfida negata e' stata generata" in superati
    # La compilazione della sfida non e' un controllo a se': la fa
    # `prepara_sfida`, che lascia un controllo FALLITO se non ce la fa. E se la
    # sfida non avesse compilato, comparator non avrebbe potuto confrontare i
    # tipi, quindi il rifiuto sarebbe su un altro controllo, non sugli assiomi.
    assert "modulo della sfida pronto" not in falliti


def test_in_modalita_confutazione_il_candidato_con_True_non_combacia(tmp_path):
    """La controprova: la sfida negata non si fa passare per quella originale.
    Se questo test fallisse, le due modalita' verificherebbero la stessa cosa e
    tutta la funzione sarebbe inutile."""
    r = verify(PROBLEMA, _candidato(tmp_path, "sorry"), modalita=CONFUTAZIONE,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "tipo identico all'originale" in _motivo(r)
