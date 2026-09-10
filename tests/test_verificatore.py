"""
Test del verificatore completo (verifier/verify.py).

Questi test fanno partire Lean davvero, quindi sono LENTI (circa 20-30 secondi
ciascuno). Richiedono che l'ambiente sia installato e l'archivio compilato.

Il problema usato come banco di prova e' `JugglerConjecture.jugglerStep_36`:

    noncomputable def jugglerStep (n : ℕ) : ℕ :=
      if Even n then ⌊(n : ℝ) ^ (1/2 : ℝ)⌋₊ else ⌊(n : ℝ) ^ (3/2 : ℝ)⌋₊

    theorem jugglerStep_36 : jugglerStep 36 = 6 := by ...

E' stato scelto perche':
  * l'archivio ne contiene gia' una dimostrazione completa (quindi possiamo
    verificare che il verificatore ACCETTI qualcosa, non solo che rifiuti);
  * l'enunciato usa `jugglerStep`, una definizione dichiarata nello stesso file:
    serve per il test "rifiuta chi ridefinisce una definizione dell'archivio";
  * e' piccolo, quindi i test non durano un'eternita'.

DUE LIVELLI DI DIFESA
---------------------
Il verificatore rifiuta `sorry`, gli assiomi e `native_decide` in due punti
indipendenti: il controllo sintattico preventivo (veloce, testuale) e
comparator (lento, ma e' la garanzia vera). Ogni volta che entrambi si
applicano, qui li collaudiamo SEPARATAMENTE: con `run_guard=False` il filtro
testuale viene disattivato e resta solo il giudizio di comparator. Se un giorno
qualcuno aggirasse il filtro testuale, questi test dimostrano che il sistema
regge lo stesso.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
import config
from index import ProblemIndex
from verify import verify, ACCEPTED, REJECTED, TIMEOUT, UNVERIFIABLE, verify_many

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROBLEMA = "JugglerConjecture.jugglerStep_36"


# --- prerequisiti -----------------------------------------------------------

def setup_module(module):
    """Salta tutti i test (con una spiegazione) se l'ambiente non e' pronto."""
    problemi = config.check_installation()
    if problemi:
        pytest.skip("Ambiente non installato:\n  - " + "\n  - ".join(problemi),
                    allow_module_level=True)
    if not config.INDEX_FILE.is_file():
        pytest.skip("Indice mancante: esegui `python verifier/index.py --build`",
                    allow_module_level=True)


def _verifica(fixture: str, **kw):
    return verify(PROBLEMA, FIXTURES / fixture, **kw)


def _regola_fallita(risultato) -> set[str]:
    return {c.name for c in risultato.checks if not c.passed}


# --- 1. ACCETTA una dimostrazione corretta ----------------------------------

def test_1_accetta_dimostrazione_corretta():
    """Il requisito piu' importante: se il verificatore non accettasse MAI
    niente, sarebbe inutile pur essendo perfettamente sicuro."""
    r = _verifica("1_corretta.lean")
    assert r.status == ACCEPTED, f"atteso ACCETTATO, ottenuto {r.status}:\n{r.render()}"
    superati = {c.name for c in r.checks if c.passed}
    for atteso in ["compila senza errori", "tipo identico all'originale",
                   "definizioni dell'archivio intatte", "assiomi ammessi",
                   "accettato dal kernel"]:
        assert atteso in superati, f"controllo mancante: {atteso}"


# --- 2. RIFIUTA una prova con `sorry` ---------------------------------------

def test_2a_rifiuta_sorry_col_controllo_sintattico():
    r = _verifica("2_sorry.lean")
    assert r.status == REJECTED
    assert "controllo sintattico preventivo" in _regola_fallita(r)


def test_2b_rifiuta_sorry_anche_senza_controllo_sintattico():
    """Il giudizio vero: comparator vede l'assioma `sorryAx`."""
    r = _verifica("2_sorry.lean", run_guard=False)
    assert r.status == REJECTED
    assert "assiomi ammessi" in _regola_fallita(r)
    assert "sorryAx" in r.errors


# --- 3. RIFIUTA una prova che aggiunge un assioma ---------------------------

def test_3a_rifiuta_assioma_col_controllo_sintattico():
    r = _verifica("3_assioma.lean")
    assert r.status == REJECTED
    assert "controllo sintattico preventivo" in _regola_fallita(r)


def test_3b_rifiuta_assioma_anche_senza_controllo_sintattico():
    r = _verifica("3_assioma.lean", run_guard=False)
    assert r.status == REJECTED
    assert "assiomi ammessi" in _regola_fallita(r)
    assert "scorciatoia" in r.errors, "comparator deve nominare l'assioma aggiunto"


# --- 4. RIFIUTA una prova che usa `native_decide` ---------------------------

def test_4a_rifiuta_native_decide_col_controllo_sintattico():
    r = _verifica("4_native_decide.lean")
    assert r.status == REJECTED
    assert "controllo sintattico preventivo" in _regola_fallita(r)


def test_4b_rifiuta_native_decide_anche_senza_controllo_sintattico():
    """`native_decide` fa calcolare il compilatore invece del kernel: lascia
    l'assioma `Lean.ofReduceBool` nel termine di prova."""
    r = _verifica("4_native_decide.lean", run_guard=False)
    assert r.status == REJECTED
    assert "assiomi ammessi" in _regola_fallita(r)
    assert "ofReduceBool" in r.errors


# --- 5. RIFIUTA un enunciato indebolito -------------------------------------

def test_5_rifiuta_enunciato_piu_debole():
    """Il candidato dimostra `jugglerStep 36 = 6 ∨ jugglerStep 36 = 7`,
    che e' strettamente piu' debole dell'originale `jugglerStep 36 = 6`.
    Il controllo sintattico non puo' accorgersene: e' un lavoro per Lean."""
    r = _verifica("5_piu_debole.lean")
    assert r.status == REJECTED
    assert "tipo identico all'originale" in _regola_fallita(r)


# --- 6. RIFIUTA chi ridefinisce una definizione dell'archivio ---------------

def test_6_rifiuta_ridefinizione_di_una_definizione():
    """Il candidato ridefinisce `jugglerStep` come la funzione costante 6.
    L'enunciato e' scritto IDENTICO all'originale, e la prova e' `rfl`: se il
    confronto fosse testuale, passerebbe."""
    r = _verifica("6_ridefinizione.lean")
    assert r.status == REJECTED
    assert "definizioni dell'archivio intatte" in _regola_fallita(r)
    assert "jugglerStep" in r.errors


# --- Extra: i problemi con un buco answer( ) --------------------------------

def test_7_segnala_i_problemi_con_buco_answer():
    """Un enunciato che contiene ancora `answer(sorry)` non proposizionale non
    e' dimostrabile onestamente. Il verificatore deve dirlo, non rifiutare e
    basta: e' un'informazione diversa."""
    idx = ProblemIndex.load()
    con_buco = idx.find(has_answer_hole=True)
    assert con_buco, "l'indice dovrebbe contenere problemi con buchi answer( )"
    r = verify(con_buco[0].theorem, FIXTURES / "1_corretta.lean", index=idx)
    assert r.status == UNVERIFIABLE, f"atteso NON_VERIFICABILE, ottenuto {r.status}"
    assert "risposta" in r.message.lower()


# --- Extra: il timeout ------------------------------------------------------

def test_8_il_timeout_funziona():
    """Con un secondo a disposizione nessuna verifica puo' finire."""
    r = _verifica("1_corretta.lean", timeout=1)
    assert r.status == TIMEOUT, f"atteso TIMEOUT, ottenuto {r.status}"
    assert "entro il tempo massimo" in _regola_fallita(r)


# --- Extra: la coda parallela -----------------------------------------------

def test_9_verifiche_in_parallelo():
    """Due verifiche insieme devono dare gli stessi esiti di due verifiche
    separate, senza pestarsi i piedi sui file temporanei."""
    risultati = verify_many(
        [(PROBLEMA, FIXTURES / "1_corretta.lean"),
         (PROBLEMA, FIXTURES / "5_piu_debole.lean")],
        jobs_parallel=2,
    )
    assert len(risultati) == 2
    assert risultati[0].status == ACCEPTED, risultati[0].render()
    assert risultati[1].status == REJECTED, risultati[1].render()
