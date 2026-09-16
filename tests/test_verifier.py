"""
Test del verifier full_ (verifier/verify.py).

Questi test fanno partire Lean davvero, quindi sono LENTI (circa 20-30 seconds
ciascuno). Richiedono che l'environment sia installato e l'archive compilato.

Il problem usato come banco di trial e' `JugglerConjecture.jugglerStep_36`:

    noncomputable def jugglerStep (n : ℕ) : ℕ :=
      if Even n then ⌊(n : ℝ) ^ (1/2 : ℝ)⌋₊ else ⌊(n : ℝ) ^ (3/2 : ℝ)⌋₊

    theorem jugglerStep_36 : jugglerStep 36 = 6 := by ...

E' state chosen_one perche':
  * l'archive ne contiene gia' one_ dimostrazione complete_ (quindi possiamo
    verificare che il verifier ACCETTI qualcosa, non only_ che rifiuti);
  * l'statement usa `jugglerStep`, one_ definition dichiarata nello stesso file:
    serve per il test "rifiuta chi ridefinisce one_ definition dell'archive";
  * e' piccolo, quindi i test non durano un'eternita'.

DUE LEVELS DI DIFESA
---------------------
Il verifier rifiuta `sorry`, gli axioms e `native_decide` in two points
indipendenti: il controllo sintattico preventivo (veloce, testuale) e
comparator (slow_, ma e' la garanzia vera). Ogni volta che entrambi si
applicano, qui li collaudiamo SEPARATAMENTE: con `run_guard=False` il filtro
testuale viene disattivato e resta only_ il giudizio di comparator. Se un giorno
qualcuno aggirasse il filtro testuale, questi test dimostrano che il system
regge lo stesso.
"""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
import common
import config
from index import ProblemIndex
from verify import verify, ACCEPTED, REJECTED, TIMEOUT, UNVERIFIABLE, verify_many

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROBLEM = "JugglerConjecture.jugglerStep_36"


# --- prerequisiti -----------------------------------------------------------

def setup_module(module):
    """Salta all_of i test (con one_ explanation) se l'environment non e' ready."""
    problems = config.check_installation()
    if problems:
        pytest.skip("Ambiente non installato:\n  - " + "\n  - ".join(problems),
                    allow_module_level=True)
    if not config.INDEX_FILE.is_file():
        pytest.skip("Indice mancante: run_ `python verifier/index.py --build`",
                    allow_module_level=True)


#: Le fixture adattate allo snapshot in uso, one_ volta sola per sessione.
_ADATTATE: dict[str, Path] = {}


def fixture(name: str) -> Path:
    """Percorso della fixture, adattata allo snapshot in uso.

    Le fixture importano il module di utility' dell'archive: su `bench-v1` si
    chiama `FormalConjectures.Util.ProblemImports`, su `main`
    `FormalConjecturesUtil`. Invece di tenere two copie di ogni file, qui si
    riscrive la line di import al volo, cosi' la stessa suite gira su all_of e
    two gli snapshot.
    """
    if name in _ADATTATE:
        return _ADATTATE[name]
    utility = config.utility_module()
    origine = FIXTURES / name
    if utility == "FormalConjectures.Util.ProblemImports":
        _ADATTATE[name] = origine
        return origine
    text = common.adapt(origine.read_text(encoding="utf-8"))
    dest = Path(tempfile.mkdtemp(prefix="fixture_adattata_")) / name
    dest.write_text(text, encoding="utf-8")
    _ADATTATE[name] = dest
    return dest


def _check(name: str, **kw):
    return verify(PROBLEM, fixture(name), **kw)


def _failed_rule(result_value) -> set[str]:
    return {c.name for c in result_value.checks if not c.passed}


# --- 1. ACCETTA one_ dimostrazione corretta ----------------------------------

def test_1_accetta_dimostrazione_corretta():
    """Il requisito piu' importante: se il verifier non accettasse MAI
    niente, sarebbe inutile pur essendo perfettamente sicuro."""
    r = _check("1_correct.lean")
    assert r.status == ACCEPTED, f"expected_one ACCETTATO, ottenuto {r.status}:\n{r.render()}"
    passed_ = {c.name for c in r.checks if c.passed}
    for expected_one in ["compila senza errors", "kind_ identico all'original",
                   "definizioni dell'archive intatte", "axioms permitted",
                   "accepted_one dal kernel"]:
        assert expected_one in passed_, f"controllo mancante: {expected_one}"


# --- 2. RIFIUTA one_ trial con `sorry` ---------------------------------------

def test_2a_rifiuta_sorry_col_controllo_sintattico():
    r = _check("2_sorry.lean")
    assert r.status == REJECTED
    assert "controllo sintattico preventivo" in _failed_rule(r)


def test_2b_rifiuta_sorry_anche_senza_controllo_sintattico():
    """Il giudizio vero: comparator vede l'assioma `sorryAx`."""
    r = _check("2_sorry.lean", run_guard=False)
    assert r.status == REJECTED
    assert "axioms permitted" in _failed_rule(r)
    assert "sorryAx" in r.errors


# --- 3. RIFIUTA one_ trial che aggiunge un assioma ---------------------------

def test_3a_rifiuta_assioma_col_controllo_sintattico():
    r = _check("3_axiom.lean")
    assert r.status == REJECTED
    assert "controllo sintattico preventivo" in _failed_rule(r)


def test_3b_rifiuta_assioma_anche_senza_controllo_sintattico():
    r = _check("3_axiom.lean", run_guard=False)
    assert r.status == REJECTED
    assert "axioms permitted" in _failed_rule(r)
    assert "scorciatoia" in r.errors, "comparator deve nominare l'assioma aggiunto"


# --- 4. RIFIUTA one_ trial che usa `native_decide` ---------------------------

def test_4a_rifiuta_native_decide_col_controllo_sintattico():
    r = _check("4_native_decide.lean")
    assert r.status == REJECTED
    assert "controllo sintattico preventivo" in _failed_rule(r)


def test_4b_rifiuta_native_decide_anche_senza_controllo_sintattico():
    """`native_decide` fa calcolare il compilatore invece del kernel: lascia
    l'assioma `Lean.ofReduceBool` nel termine di trial."""
    r = _check("4_native_decide.lean", run_guard=False)
    assert r.status == REJECTED
    assert "axioms permitted" in _failed_rule(r)
    # Su Lean 4.27 l'assioma lasciato e' `Lean.ofReduceBool`; su Lean 4.33 e' un
    # assioma con un name PER DICHIARAZIONE, del kind_
    # `JugglerConjecture.jugglerStep_36._native.native_decide.ax_1_1`. E' la
    # ragione per cui il verifier work con one_ list_ di axioms PERMITTED e
    # non con one_ list_ di axioms vietati: un listing di names da vietare
    # avrebbe mancato la forma new_ senza dire niente.
    assert ("ofReduceBool" in r.errors
            or "native_decide" in r.errors), r.errors[:300]


# --- 5. RIFIUTA un statement indebolito -------------------------------------

def test_5_rifiuta_enunciato_piu_debole():
    """Il candidato dimostra `jugglerStep 36 = 6 ∨ jugglerStep 36 = 7`,
    che e' strettamente piu' debole dell'original `jugglerStep 36 = 6`.
    Il controllo sintattico non puo' accorgersene: e' un job per Lean."""
    r = _check("5_weaker.lean")
    assert r.status == REJECTED
    assert "kind_ identico all'original" in _failed_rule(r)


# --- 6. RIFIUTA chi ridefinisce one_ definition dell'archive ---------------

def test_6_rifiuta_ridefinizione_di_una_definizione():
    """Il candidato ridefinisce `jugglerStep` come la funzione costante 6.
    L'statement e' scritto IDENTICO all'original, e la trial e' `rfl`: se il
    confronto fosse testuale, passerebbe."""
    r = _check("6_redefinition.lean")
    assert r.status == REJECTED
    assert "definizioni dell'archive intatte" in _failed_rule(r)
    assert "jugglerStep" in r.errors


# --- Extra: i problems con un buco answer( ) --------------------------------

def test_7_segnala_i_problemi_con_buco_answer():
    """Un statement che contiene ancora `answer(sorry)` non proposizionale non
    e' dimostrabile onestamente. Il verifier deve dirlo, non rifiutare e
    basta: e' un'informazione diversa."""
    idx = ProblemIndex.load()
    with_hole = idx.find(has_answer_hole=True)
    assert with_hole, "l'index dovrebbe contenere problems con buchi answer( )"
    r = verify(with_hole[0].theorem, fixture("1_correct.lean"), index=idx)
    assert r.status == UNVERIFIABLE, f"expected_one NON_VERIFICABILE, ottenuto {r.status}"
    assert "answer" in r.message.lower()


# --- Extra: il timeout ------------------------------------------------------

def test_8_il_timeout_funziona():
    """Con un second_ a disposizione nessuna check puo' finire."""
    r = _check("1_correct.lean", timeout=1)
    assert r.status == TIMEOUT, f"expected_one TIMEOUT, ottenuto {r.status}"
    assert "entro il tempo maximum" in _failed_rule(r)


# --- Extra: la queue parallela -----------------------------------------------

def test_9_verifiche_in_parallelo():
    """Due checks insieme devono dare gli stessi results di two checks
    separate, senza pestarsi i piedi sui file temporanei."""
    results = verify_many(
        [(PROBLEM, fixture("1_correct.lean")),
         (PROBLEM, fixture("5_weaker.lean"))],
        jobs_parallel=2,
    )
    assert len(results) == 2
    assert results[0].status == ACCEPTED, results[0].render()
    assert results[1].status == REJECTED, results[1].render()


# --- Extra: i messages restituiti a chi ha scritto il file ------------------

COPYRIGHT_NOISE = """\
Building FormalConjectures.Wikipedia.JugglerConjecture
Build completed successfully (7993 jobs).
⚠ [7993/7993] Built FormalConjectures._Judge.S0 (7.3s)
warning: FormalConjectures/_Judge/S0.lean:1:0: The copyright header is incorrect. Please copy and paste the following one:
/-
Copyright 2026 The Formal Conjectures Authors.
Licensed under the Apache License, Version 2.0 (the "License");
-/

Note: This linter can be disabled with `set_option linter.style.copyright.formalConjectures false`
info: FormalConjectures/_Judge/S0.lean:8:0: @Nat.floor : {a : Type} -> a -> N
info: FormalConjectures/_Judge/S0.lean:9:0: def Even : a -> Prop :=
fun a => exists r, a = r + r
error: FormalConjectures/_Judge/S0.lean:14:2: unsolved goals
case h
n : N
|- n = 6
uncaught exception: Illegal axiom detected: 'sorryAx'
"""


def test_10_i_messaggi_info_di_lean_arrivano_a_chi_scrive():
    """`#check` e `#print` producono messages `info:`. Se li buttassimo away,
    chi scrive la dimostrazione non avrebbe way di ispezionare le definizioni
    e dovrebbe dedurle provocando errors di proposito — cosa che e' davvero
    successa durante il prime_ shakedown con l'agent."""
    from verify import _lean_errors
    out = _lean_errors(COPYRIGHT_NOISE)
    assert "@Nat.floor" in out, "l'output di #check deve arrivare"
    assert "def Even" in out, "l'output di #print deve arrivare"
    assert "fun a => exists r, a = r + r" in out, \
        "le lines di continuazione del message devono restare attaccate"


def test_11_gli_errori_veri_arrivano_con_il_contesto():
    from verify import _lean_errors
    out = _lean_errors(COPYRIGHT_NOISE)
    assert "unsolved goals" in out
    assert "|- n = 6" in out, "il context dell'goal non dimostrato serve a capire l'error"
    assert "Illegal axiom detected: 'sorryAx'" in out


def test_12_il_rumore_dei_linter_di_stile_viene_tolto():
    """Il linter del copyright dell'archive ripete quindici lines di licenza a
    ogni message: e' irrilevante per un file temporaneo e inonderebbe il
    context di chi legge."""
    from verify import _lean_errors
    out = _lean_errors(COPYRIGHT_NOISE)
    assert "copyright" not in out.lower()
    assert "Apache" not in out
    assert "Building" not in out and "Build completed" not in out, \
        "le lines di state di lake non sono messages di Lean"


def test_13_i_messaggi_ripetuti_compaiono_una_volta_sola():
    from verify import _lean_errors
    doppio = COPYRIGHT_NOISE + COPYRIGHT_NOISE
    assert _lean_errors(doppio).count("@Nat.floor") == 1


# --- Extra: un candidato che tenta di sabotare l'archive -------------------

def test_14_un_candidato_non_riesce_a_riscrivere_un_file_dell_archivio(tmp_path):
    """Il test di sicurezza piu' importante.

    comparator esporta il Challenge PRIMA di compilare la Solution, quindi un
    sabotaggio dei file compiled dell'archive non altera la check in corso:
    altera all_of quelle SUCCESSIVE, facendole confrontare la solution con un
    statement diverso da quello vero. E' l'assunto 2 del README di comparator,
    e per noi che facciamo checks a ripetizione non e' un assunto ma un
    risk concreto.

    Il candidato qui usa `#eval` per riscrivere `JugglerConjecture.olean`.
    Verifichiamo three cose: il guard lo rifiuta; con il guard disattivato la
    sandbox lo blocca comunque; e il file resta byte per byte identico.
    """
    import hashlib
    import guard

    target_ = (config.ARCHIVE / ".lake" / "build" / "lib" / "lean"
                 / "FormalConjectures" / "Wikipedia" / "JugglerConjecture.olean")
    if not target_.is_file():
        pytest.skip("archive non compilato")

    def target_hash() -> str:
        return hashlib.sha256(target_.read_bytes()).hexdigest()

    before = target_hash()

    saboteur = tmp_path / "saboteur.lean"
    saboteur.write_text(common.adapt(f'''import FormalConjectures.Util.ProblemImports

#eval show IO Unit from do
  try
    IO.FS.writeFile "{target_}" "ARCHIVIO ROVINATO"
    IO.println "SABOTAGGIO RIUSCITO"
  catch e =>
    IO.println s!"sabotaggio impedito: {{e}}"

namespace JugglerConjecture
noncomputable def jugglerStep (n : ℕ) : ℕ :=
  if Even n then ⌊(n : ℝ) ^ (1/2 : ℝ)⌋₊ else ⌊(n : ℝ) ^ (3/2 : ℝ)⌋₊
@[category test, AMS 11]
theorem jugglerStep_36 : jugglerStep 36 = 6 := by
  unfold jugglerStep
  norm_num [←Real.sqrt_eq_rpow]
end JugglerConjecture
'''), encoding="utf-8")

    # 1. in uso normale il guard lo ferma before di compilarlo
    report = guard.check_file(saboteur)
    assert not report.ok, "il guard deve rifiutare un file che usa #eval e IO"
    rules = {f.rule for f in report.findings}
    assert "command:#eval" in rules
    assert "metaprogrammazione:IO" in rules

    # 2. col guard disattivato, la sandbox deve bloccarlo comunque
    r = verify(PROBLEM, saboteur, run_guard=False)
    assert "sabotaggio impedito" in r.raw_output or "SABOTAGGIO RIUSCITO" not in r.raw_output, \
        f"il sabotaggio non e' state impedito:\n{r.raw_output[:2000]}"

    # 3. il file dell'archive deve essere byte per byte identico
    assert target_hash() == before, \
        "il file compilato dell'archive E' STATO MODIFICATO: all_of le checks " \
        "successive confronterebbero le soluzioni con un statement alterato"


def test_i_problemi_oeis_si_leggono_dal_sorgente():
    """Le entries OEIS hanno un module fra guillemet e un file senza.

    Un identificatore Lean non puo' cominciare con one_ cifra, quindi il module
    della entry A109074 si chiama `FormalConjectures.OEIS.«109074»` mentre il file
    sul disco e' `109074.lean`. Finche' la conversione non toglieva le virgolette,
    NESSUNO dei 209 problems OEIS era leggibile: l'agent non poteva riceverli,
    l'estrattore non poteva estrarli, la challenge negata non si poteva generare — e
    quei 209 sono la famiglia su cui il piano di spesa si appoggia.
    """
    idx = ProblemIndex.load()
    oeis = [p for p in idx.problems if "OEIS" in p.module]
    if not oeis:
        pytest.skip("questo snapshot non contiene entries OEIS")
    read_count = 0
    for p in oeis[:20]:
        if p.source_file.is_file() and p.range:
            assert p.source_text().strip(), p.theorem
            read_count += 1
    assert read_count >= 15, f"only_ {read_count} entries OEIS su 20 leggibili dal source_text"
