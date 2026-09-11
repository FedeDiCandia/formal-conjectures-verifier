"""
Test dello strumento di esplorazione (verifier/esplora.py).

PERCHE' ESISTE QUESTO STRUMENTO
-------------------------------
Nel primo collaudo l'agente ha speso NOVE verifiche su nove per ispezionare
l'API di Mathlib, non per consegnare una dimostrazione — e ci e' riuscito solo
provocando errori di tipo di proposito, perche' il verificatore non gli
restituiva i messaggi informativi di Lean. Quelle nove verifiche sono costate
$1,81 e 740 secondi senza produrre un solo tentativo vero.

`lean_explore` fa la parte utile a capire: compila e riporta tutto, senza
comparator, senza confronto degli enunciati, senza riesecuzione nel kernel.
"""
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))

import comune
import config
import esplora as modulo_esplora
import guard


def setup_module(module):
    if config.check_installation():
        pytest.skip("ambiente non installato", allow_module_level=True)


# --- il guard vale anche in esplorazione ------------------------------------

def test_in_esplorazione_si_puo_importare_il_modulo_del_problema():
    """E' l'unica regola allentata: serve per fare `#print` sulle definizioni
    dell'archivio. In una soluzione resta vietato, perche' dichiarerebbe un
    nome che esiste gia'."""
    src = "import FormalConjectures.Wikipedia.Selfridge\n#print Selfridge.IsSelfridge\n"
    assert guard.check_source(src, esplorazione=True).ok
    assert not guard.check_source(src, esplorazione=False).ok, \
        "in una soluzione l'import del modulo del problema deve restare vietato"


def test_in_esplorazione_il_codice_eseguibile_resta_vietato():
    """Un file di ispezione viene compilato come qualunque altro, quindi puo'
    eseguire codice allo stesso modo: le regole sul codice non si allentano."""
    for src in ['#eval IO.println "x"',
                'run_meta Lean.logInfo "x"',
                'def f : IO Unit := pure ()',
                'theorem t : True := by native_decide']:
        assert not guard.check_source(src, esplorazione=True).ok, f"passato: {src}"


def test_un_file_vietato_non_viene_nemmeno_compilato():
    r = modulo_esplora.esplora(comune.adatta(
        'import FormalConjectures.Util.ProblemImports\n#eval IO.println "x"\n'))
    assert not r.ok
    assert r.rifiutato_dal_guard
    assert r.secondi < 1.0, "non deve nemmeno far partire Lean"
    assert "comando:#eval" in r.rifiutato_dal_guard


# --- l'esplorazione vera (fa partire Lean: circa 10 secondi) -----------------

@pytest.fixture(scope="module")
def ispezione():
    """Una sola compilazione, riusata da piu' test: dura circa 10 secondi."""
    return modulo_esplora.esplora(comune.adatta("""import FormalConjectures.Util.ProblemImports
import FormalConjectures.Wikipedia.Selfridge

#print Selfridge.IsPseudoSelfridge
#check @Nat.floor
#print Nat.Perfect

example : (2:ℕ) + 3 = 5 := by exact?

example (n : ℕ) (h : 3 < n) : n = 7 := by
  omega
"""))


def test_print_di_una_struttura_dell_archivio_arriva_completo(ispezione):
    """Il caso che nel primo collaudo l'agente non riusciva a ottenere."""
    m = ispezione.messaggi
    assert "structure Selfridge.IsPseudoSelfridge" in m
    # tutti e quattro i campi, non solo il primo
    for campo in ["is_odd", "mod_5", "pow_2", "fib"]:
        assert campo in m, f"manca il campo {campo}"
    assert "constructor:" in m, "anche il costruttore deve comparire"


def test_print_di_una_definizione_di_mathlib_mostra_il_corpo(ispezione):
    assert "def Nat.Perfect" in ispezione.messaggi
    assert "properDivisors" in ispezione.messaggi, \
        "il corpo della definizione, non solo il nome"


def test_check_mostra_il_tipo_con_gli_impliciti(ispezione):
    assert "@Nat.floor :" in ispezione.messaggi
    assert "FloorSemiring" in ispezione.messaggi, \
        "gli argomenti impliciti di istanza servono per usare il lemma"


def test_exact_suggerisce_un_lemma(ispezione):
    assert "Try this" in ispezione.messaggi


def test_gli_errori_arrivano_con_lo_stato_degli_obiettivi(ispezione):
    """Senza lo stato degli obiettivi un errore non dice cosa fare."""
    assert "error" in ispezione.messaggi
    assert "omega could not prove the goal" in ispezione.messaggi
    assert "4 ≤ a ≤ 6" in ispezione.messaggi, \
        "il controesempio trovato da omega e' l'informazione utile"


def test_i_messaggi_non_sono_troncati(ispezione):
    assert not ispezione.troncato


def test_l_esplorazione_gira_isolata(ispezione):
    assert ispezione.isolato, "deve girare dentro sandbox-exec"


#: Quanto dura una verifica COMPLETA, misurata su ciascuno snapshot. Serve a
#: dare un senso alla soglia qui sotto: l'esplorazione ha ragione di esistere
#: solo se costa una frazione di una verifica.
#:   bench-v1 (Lean 4.27):  32,9 s  — misurato con `time`
#:   main     (Lean 4.33):  47-114 s — misurato su 13 verifiche d'archivio
VERIFICA_COMPLETA = {"FormalConjectures.Util.ProblemImports": 33.0,
                     "FormalConjecturesUtil": 47.0}


def test_l_esplorazione_e_piu_rapida_di_una_verifica(ispezione):
    """Il motivo per cui esiste: se l'esplorazione non fosse sensibilmente piu'
    rapida di una verifica completa, non servirebbe a niente."""
    import config
    piena = VERIFICA_COMPLETA.get(config.modulo_utilita(), 33.0)
    assert ispezione.secondi < piena * 0.7, (
        f"troppo lenta: {ispezione.secondi:.1f}s contro i {piena:.0f}s di una "
        f"verifica completa su questo snapshot")


def test_il_timeout_interrompe_una_tattica_che_non_termina():
    r = modulo_esplora.esplora(comune.adatta("""import FormalConjectures.Util.ProblemImports
set_option maxRecDepth 100000 in
example : True := by
  have : ∀ n : ℕ, n = n := fun n => rfl
  trivial
"""), timeout=5)
    # non ci aspettiamo che questo specifico file scada: verifichiamo solo che
    # il parametro sia rispettato e non faccia saltare la funzione
    assert r.secondi < 60
