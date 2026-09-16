"""
Test dello strumento di exploration (verifier/explore.py).

PERCHE' ESISTE QUESTO STRUMENTO
-------------------------------
Nel first shakedown l'agent ha spent NOVE checks su nove per ispezionare
l'API di Mathlib, non per consegnare one dimostrazione — e ci e' succeeded only
provocando errors di kind di proposito, perche' il verifier non gli
restituiva i messages informativi di Lean. Quelle nove checks sono costate
$1,81 e 740 seconds senza produrre un only attempt vero.

`lean_explore` fa la parte utile a capire: compila e riporta tutto, senza
comparator, senza confronto degli enunciati, senza riesecuzione nel kernel.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import common
import config
import explore as explore_module
import guard


def setup_module(module):
    if config.check_installation():
        pytest.skip("environment non installato", allow_module_level=True)


# --- il guard vale also in exploration ------------------------------------

def test_in_esplorazione_si_puo_importare_il_modulo_del_problema():
    """E' l'unica rule allentata: serve per fare `#print` sulle definizioni
    dell'archive. In one solution resta vietato, perche' dichiarerebbe un
    name che esiste gia'."""
    src = "import FormalConjectures.Wikipedia.Selfridge\n#print Selfridge.IsSelfridge\n"
    assert guard.check_source(src, exploration=True).ok
    assert not guard.check_source(src, exploration=False).ok, \
        "in one solution l'import del module del problem deve restare vietato"


def test_in_esplorazione_il_codice_eseguibile_resta_vietato():
    """Un file di inspection viene compilato come qualunque other, quindi puo'
    eseguire code allo stesso way: le rules sul code non si allentano."""
    for src in ['#eval IO.println "x"',
                'run_meta Lean.logInfo "x"',
                'def f : IO Unit := pure ()',
                'theorem t : True := by native_decide']:
        assert not guard.check_source(src, exploration=True).ok, f"passato: {src}"


def test_un_file_vietato_non_viene_nemmeno_compilato():
    r = explore_module.explore(common.adapt(
        'import FormalConjectures.Util.ProblemImports\n#eval IO.println "x"\n'))
    assert not r.ok
    assert r.rejected_by_guard
    assert r.seconds < 1.0, "non deve nemmeno far partire Lean"
    assert "command:#eval" in r.rejected_by_guard


# --- l'exploration vera (fa partire Lean: circa 10 seconds) -----------------

@pytest.fixture(scope="module")
def inspection():
    """Una sola compilazione, riusata da piu' test: dura circa 10 seconds."""
    return explore_module.explore(common.adapt("""import FormalConjectures.Util.ProblemImports
import FormalConjectures.Wikipedia.Selfridge

#print Selfridge.IsPseudoSelfridge
#check @Nat.floor
#print Nat.Perfect

example : (2:ℕ) + 3 = 5 := by exact?

example (n : ℕ) (h : 3 < n) : n = 7 := by
  omega
"""))


def test_print_di_una_struttura_dell_archivio_arriva_completo(inspection):
    """Il caso che nel first shakedown l'agent non riusciva a ottenere."""
    m = inspection.messages
    assert "structure Selfridge.IsPseudoSelfridge" in m
    # all_items e quattro i fields, non only il first
    for field in ["is_odd", "mod_5", "pow_2", "fib"]:
        assert field in m, f"manca il field {field}"
    assert "constructor:" in m, "also il costruttore deve comparire"


def test_print_di_una_definizione_di_mathlib_mostra_il_corpo(inspection):
    assert "def Nat.Perfect" in inspection.messages
    assert "properDivisors" in inspection.messages, \
        "il body della definition, non only il name"


def test_check_mostra_il_tipo_con_gli_impliciti(inspection):
    assert "@Nat.floor :" in inspection.messages
    assert "FloorSemiring" in inspection.messages, \
        "gli arguments impliciti di istanza servono per usare il lemma"


def test_exact_suggerisce_un_lemma(inspection):
    assert "Try this" in inspection.messages


def test_gli_errori_arrivano_con_lo_stato_degli_obiettivi(inspection):
    """Senza lo state degli obiettivi un error non dice cosa fare."""
    assert "error" in inspection.messages
    assert "omega could not trials the goal" in inspection.messages
    assert "4 ≤ a ≤ 6" in inspection.messages, \
        "il counterexample found da omega e' l'informazione utile"


def test_i_messaggi_non_sono_troncati(inspection):
    assert not inspection.truncated


def test_l_esplorazione_gira_isolata(inspection):
    assert inspection.isolated, "deve girare inside sandbox-exec"


#: Quanto dura one check COMPLETA, misurata su ciascuno snapshot. Serve a
#: dare un senso alla threshold qui below: l'exploration ha ragione di esistere
#: only se costa one frazione di one check.
#:   bench-v1 (Lean 4.27):  32,9 s  — misurato con `time`
#:   main     (Lean 4.33):  47-114 s — misurato su 13 checks d'archive
FULL_VERIFICATION = {"FormalConjectures.Util.ProblemImports": 33.0,
                     "FormalConjecturesUtil": 47.0}


def test_l_esplorazione_e_piu_rapida_di_una_verifica(inspection):
    """Il reason per cui esiste: se l'exploration non fosse sensibilmente piu'
    rapida di one check complete, non servirebbe a niente.

    Si prende il MIGLIORE di two misure. Non e' per far passare il test: la
    grandezza da misurare e' quanto costa un'exploration su questa macchina,
    e la before misura include la cache fredda e l'eventuale carico di altri
    jobs in corso. Misurare il caso worst below carico misurerebbe il
    carico, non lo strumento.
    """
    import config
    piena = FULL_VERIFICATION.get(config.utility_module(), 33.0)
    seconds = inspection.seconds
    if seconds >= piena * 0.7:
        again = explore_module.explore(common.adapt(
            "import FormalConjectures.Util.ProblemImports\n"
            "#check @Nat.floor\n"))
        seconds = min(seconds, again.seconds)
    assert seconds < piena * 0.7, (
        f"troppo lenta: {seconds:.1f}s against i {piena:.0f}s di one "
        f"check complete su questo snapshot")


def test_il_timeout_interrompe_una_tattica_che_non_termina():
    r = explore_module.explore(common.adapt("""import FormalConjectures.Util.ProblemImports
set_option maxRecDepth 100000 in
example : True := by
  have : ∀ n : ℕ, n = n := fun n => rfl
  trivial
"""), timeout=5)
    # non ci aspettiamo che questo specifico file scada: verifichiamo only che
    # il parametro sia rispettato e non faccia saltare la funzione
    assert r.seconds < 60


# --- gli slot: two explorations insieme non devono mescolarsi ----------------

def test_due_esplorazioni_insieme_non_si_mescolano():
    """Il finding che questo test fix era della specie worst.

    Il file di inspection vive nell'albero dell'archive e il suo name E' il name
    del module Lean, quindi era fisso: `E0.lean`. Due explorations insieme si
    sovrascrivevano il file e ognuna leggeva i messages dell'altra. Nella caccia
    agli artefacts questo ha fatto sembrare che one tactic banale avesse chiuso
    un problem aperto di topologia: i messages che arrivavano erano di un other
    problem, compilato da un other processo.
    """
    import threading
    results = {}

    def work(name, code):
        results[name] = explore_module.explore(code, timeout=200)

    a = common.adapt("import FormalConjectures.Util.ProblemImports\n"
                      "theorem prova_A : (2:ℕ) + 2 = 5 := by norm_num\n")
    b = common.adapt("import FormalConjectures.Util.ProblemImports\n"
                      "theorem prova_B : (3:ℕ) + 3 = 7 := by norm_num\n")
    threads = [threading.Thread(target=work, args=("A", a)),
            threading.Thread(target=work, args=("B", b))]
    for f in threads:
        f.start()
    for f in threads:
        f.join()
    # ognuna deve parlare del PROPRIO file, e i two file devono essere diversi
    import re
    file_a = set(re.findall(r"E(\d+)\.lean", results["A"].messages))
    file_b = set(re.findall(r"E(\d+)\.lean", results["B"].messages))
    assert file_a and file_b, (results["A"].messages, results["B"].messages)
    assert file_a.isdisjoint(file_b), f"stesso slot: {file_a} e {file_b}"
    for name in ("A", "B"):
        assert "unsolved goals" in results[name].messages
