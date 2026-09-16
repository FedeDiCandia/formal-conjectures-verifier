"""
Test delle sfide "negate".

IL PROBLEM CHE RISOLVONO
-------------------------
107 problems ancora APERTI dell'archive sono formalizzati cosi':

    theorem congettura : answer(sorry) ↔ P := by sorry

e l'opzione predefinita dell'archive trasforma `answer(sorry)` in `True`.
L'statement che Lean vede e' quindi `True ↔ P`: l'affermazione che la answer
alla domanda e' SI'.

Se per one di quei problems la answer giusta fosse NO, il theorem_ com'e'
scritto sarebbe FALSO e indimostrabile, e chi trovasse la confutazione non
avrebbe way di farla verificare. La challenge negata gli da' quel way:
`answer(False) ↔ P`, cioe' `¬P`.

COME SI COLLAUDA SENZA RISOLVERE UN PROBLEM APERTO
---------------------------------------------------
Nessuno di quei 107 problems e' dimostrabile in alcuna direzione: sono open_.
Ma comparator compare gli ENUNCIATI before di controllare gli axioms, e questo
basta.

Si prende un candidato con la dimostrazione lasciata a `sorry`:
  * se l'statement COMBACIA con la challenge, comparator arriva al controllo degli
    axioms e rifiuta per `sorryAx`;
  * se l'statement DIFFERISCE, comparator si ferma before e rifiuta per
    "statement do not match".

Il reason del rifiuto dice quindi se gli enunciati combaciano. Quattro
combinazioni bastano a dimostrare che le two sfide sono enunciati distinti e che
funzionano entrambe, senza dimostrare nulla di matematico.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import common
import config
import negation
from index import ProblemIndex
from verify import verify, REFUTATION, STRICT, REJECTED, ERROR

#: Scelto perche' l'statement usa only_ `Nat.Perfect` di Mathlib (nessuna
#: definition local_ da ricopiare) e perche' il suo file contiene TRE problems
#: con `answer(sorry)`: serve a verificare che la sostituzione tocchi only_
#: quello target_.
PROBLEM = "PerfectNumbers.infinitely_many_perfect"

_CANDIDATE = """import FormalConjectures.Util.ProblemImports

namespace PerfectNumbers

open Nat

@[category research open, AMS 11]
theorem infinitely_many_perfect :
    answer({answer}) ↔ {{n : ℕ | Perfect n}}.Infinite := by
  sorry

end PerfectNumbers
"""


def setup_module(module):
    if config.check_installation():
        pytest.skip("environment non installato", allow_module_level=True)
    if not config.INDEX_FILE.is_file():
        pytest.skip("index mancante", allow_module_level=True)


@pytest.fixture(scope="module")
def index():
    return ProblemIndex.load()


def _candidate(tmp_path, answer: str) -> Path:
    f = tmp_path / f"candidato_{answer}.lean"
    f.write_text(common.adapt(_CANDIDATE.format(answer=answer)),
                 encoding="utf-8")
    return f


# --- generazione (veloce, senza Lean) ---------------------------------------

def test_la_sostituzione_avviene_solo_nel_teorema_bersaglio(index):
    """Il file di PerfectNumbers contiene three problems con `answer(sorry)`.
    Invertirli all_of darebbe one_ challenge diversa da quella richiesta."""
    challenge = negation.generate(index.get(PROBLEM))
    body = challenge.text.split("-/\n", 1)[1]     # away l'header generata
    assert challenge.substitutions == 1
    assert body.count("answer(False)") == 1
    assert body.count("answer(sorry)") >= 1, \
        "gli altri problems del file devono restare come erano"


def test_la_sfida_dichiara_di_essere_generata(index):
    """Chi apre il file deve capire subito che non e' un file dell'archive."""
    challenge = negation.generate(index.get(PROBLEM))
    assert "SFIDA NEGATA" in challenge.text
    assert "generato automaticamente" in challenge.text
    assert PROBLEM in challenge.text


def test_un_problema_senza_answer_non_si_puo_negare(index):
    """Un statement senza `answer( )` afferma direttamente one_ proposizione:
    la sua negation non e' un problem dell'archive, e' un'altra cosa."""
    with pytest.raises(negation.NotNegatable, match="non contiene"):
        negation.generate(index.get("JugglerConjecture.jugglerStep_36"))


def test_un_buco_answer_non_proposizionale_non_si_puo_negare(index):
    """Se la answer e' un number o un insieme non c'e' un verso da invertire:
    c'e' un value_ da fornire."""
    with_hole = index.find(has_answer_hole=True)
    assert with_hole, "l'index dovrebbe contenerne"
    for p in with_hole:
        if p.answer_placeholder_in_source:
            with pytest.raises(negation.NotNegatable, match="proposizionale"):
                negation.generate(p)
            return
    pytest.skip("nessun problem con buco non proposizionale e answer(sorry) nel source_text")


def test_la_confutazione_di_un_enunciato_senza_answer_e_possibile(tmp_path):
    """Prima questa combinazione dava ERRORE, e sbagliava.

    La mode' confutazione serviva only_ ai problems con `answer(sorry)`, cioe'
    one_ minoranza. Ora esiste the route `type_of%`, che vale per qualunque
    statement full_: qui la challenge si generate, e il candidato viene RIFIUTATO
    perche' non dimostra la negation — non perche' la mode' non si applichi.
    """
    r = verify("JugglerConjecture.jugglerStep_36", _candidate(tmp_path, "False"),
               mode=REFUTATION, run_guard=False, timeout=900)
    assert r.status == REJECTED, r.render()
    passed_ = {c.name for c in r.checks if c.passed}
    assert "il problem ammette one_ confutazione" in passed_
    details = " ".join(c.detail or "" for c in r.checks)
    assert "type_of%" in details


def test_un_enunciato_con_un_buco_non_si_puo_confutare(tmp_path):
    """Se l'statement stesso contiene un `sorry`, la sua negation non e'
    un'affermazione ben posta: nessuna delle two vie si apply_."""
    idx = ProblemIndex.load()
    with_hole = [q for q in idx.find(category="research open") if q.statement_has_sorry]
    if not with_hole:
        pytest.skip("nessun problem con buco non proposizionale nell'index")
    r = verify(with_hole[0].theorem, _candidate(tmp_path, "False"),
               mode=REFUTATION, run_guard=False)
    assert r.status == ERROR
    assert "challenge negata" in r.message.lower()


def test_modalita_sconosciuta_viene_rifiutata(tmp_path):
    r = verify(PROBLEM, _candidate(tmp_path, "False"), mode="fantasia")
    assert r.status == ERROR
    assert "mode" in r.message.lower()


# --- integrazione: le two sfide sono enunciati DIVERSI ----------------------
# Questi quattro test fanno partire Lean: sono lenti (circa 30 seconds ciascuno).

def _reason(result_value) -> set[str]:
    return {c.name for c in result_value.checks
            if not c.passed and c.name != "controllo sintattico preventivo"}


def test_in_modalita_stretta_il_candidato_con_True_combacia(tmp_path):
    """`answer(sorry)` diventa `True`, come nell'archive: gli enunciati
    combaciano, quindi comparator arriva al controllo degli axioms."""
    r = verify(PROBLEM, _candidate(tmp_path, "sorry"), mode=STRICT,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "axioms permitted" in _reason(r), \
        f"expected_one rifiuto per gli axioms (enunciati combacianti), ottenuto {_reason(r)}"
    assert "sorryAx" in r.errors


def test_in_modalita_stretta_il_candidato_con_False_non_combacia(tmp_path):
    """`answer(False)` da' `False ↔ P`: un statement diverso da quello
    dell'archive, e comparator si ferma before degli axioms."""
    r = verify(PROBLEM, _candidate(tmp_path, "False"), mode=STRICT,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "kind_ identico all'original" in _reason(r)


def test_in_modalita_confutazione_il_candidato_con_False_combacia(tmp_path):
    """E' il verso che count_: la challenge negata accetta l'statement `False ↔ P`.
    Con one_ dimostrazione vera (non `sorry`) questo sarebbe one_ confutazione
    verificata del problem aperto."""
    r = verify(PROBLEM, _candidate(tmp_path, "False"), mode=REFUTATION,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "axioms permitted" in _reason(r), \
        f"expected_one rifiuto per gli axioms (enunciati combacianti), ottenuto {_reason(r)}"
    assert "sorryAx" in r.errors
    # la challenge negata deve essere stata generata, e deve aver compilato
    passed_ = {c.name for c in r.checks if c.passed}
    failed_ = {c.name for c in r.checks if not c.passed}
    assert "il problem ammette one_ confutazione" in passed_
    assert "la challenge negata e' stata generata" in passed_
    # La compilazione della challenge non e' un controllo a se': la fa
    # `prepare_challenge`, che lascia un controllo FALLITO se non ce la fa. E se la
    # challenge non avesse compilato, comparator non avrebbe potuto confrontare i
    # tipi, quindi il rifiuto sarebbe su un other controllo, non sugli axioms.
    assert "module della challenge ready" not in failed_


def test_in_modalita_confutazione_il_candidato_con_True_non_combacia(tmp_path):
    """La controprova: la challenge negata non si fa passare per quella original.
    Se questo test fallisse, le two mode' verificherebbero la stessa cosa e
    tutta la funzione sarebbe inutile."""
    r = verify(PROBLEM, _candidate(tmp_path, "sorry"), mode=REFUTATION,
               run_guard=False, timeout=900)
    assert r.status == REJECTED
    assert "kind_ identico all'original" in _reason(r)


# --- the route generale: `type_of%`, per gli enunciati senza `answer( )` --------
#
# È the route che serve davvero: nel benchmark OEIS Open di Epoch AI il 43% delle
# soluzioni accettate sono confutazioni, e la maggioranza dei problems open_
# non ha un `answer(sorry)` da invertire. Senza questa away metà dei results
# possibili non sarebbe nemmeno verificabile.

PROBLEMA_SENZA_ANSWER = "PerfectNumbers.infinitely_many_even_perfect"


def test_la_via_per_tipo_genera_un_bersaglio_derivato():
    idx = ProblemIndex.load()
    p = idx.get(PROBLEM)          # questo ha `answer( )`
    s = negation.generate_by_kind(p)
    assert s.route == "type_of%"
    assert s.target_ == PROBLEM + negation.SUFFIX
    assert f"import {p.module}" in s.text
    assert f"¬ (type_of% @{PROBLEM})" in s.text
    assert "sorry" in s.text      # la challenge è un target_, non one_ trial


def test_la_via_per_tipo_rifiuta_un_enunciato_con_un_buco():
    idx = ProblemIndex.load()
    with_hole = [q for q in idx.find(category="research open") if q.statement_has_sorry]
    if not with_hole:
        pytest.skip("nessun problem con buco non proposizionale nell'index")
    with pytest.raises(negation.NotNegatable):
        negation.generate_by_kind(with_hole[0])


def test_il_guard_permette_un_solo_modulo_in_piu():
    import guard
    src = "import FormalConjectures.Wikipedia.PerfectNumbers\ntheorem t : True := trivial\n"
    assert not guard.check_source(src).ok          # vietato di norma
    ok = guard.check_source(src, allowed_module="FormalConjectures.Wikipedia.PerfectNumbers")
    assert ok.ok                                   # permesso se dichiarato
    other = "import FormalConjectures.Wikipedia.JugglerConjecture\ntheorem t : True := trivial\n"
    assert not guard.check_source(
        other, allowed_module="FormalConjectures.Wikipedia.PerfectNumbers").ok
