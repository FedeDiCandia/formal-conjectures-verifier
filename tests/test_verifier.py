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
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
import common
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


#: Le fixture adattate allo snapshot in uso, una volta sola per sessione.
_ADATTATE: dict[str, Path] = {}


def fixture(nome: str) -> Path:
    """Percorso della fixture, adattata allo snapshot in uso.

    Le fixture importano il modulo di utilita' dell'archivio: su `bench-v1` si
    chiama `FormalConjectures.Util.ProblemImports`, su `main`
    `FormalConjecturesUtil`. Invece di tenere due copie di ogni file, qui si
    riscrive la riga di import al volo, cosi' la stessa suite gira su tutti e
    due gli snapshot.
    """
    if nome in _ADATTATE:
        return _ADATTATE[nome]
    utilita = config.modulo_utilita()
    origine = FIXTURES / nome
    if utilita == "FormalConjectures.Util.ProblemImports":
        _ADATTATE[nome] = origine
        return origine
    testo = common.adatta(origine.read_text(encoding="utf-8"))
    dest = Path(tempfile.mkdtemp(prefix="fixture_adattata_")) / nome
    dest.write_text(testo, encoding="utf-8")
    _ADATTATE[nome] = dest
    return dest


def _verifica(nome: str, **kw):
    return verify(PROBLEMA, fixture(nome), **kw)


def _regola_fallita(risultato) -> set[str]:
    return {c.name for c in risultato.checks if not c.passed}


# --- 1. ACCETTA una dimostrazione corretta ----------------------------------

def test_1_accetta_dimostrazione_corretta():
    """Il requisito piu' importante: se il verificatore non accettasse MAI
    niente, sarebbe inutile pur essendo perfettamente sicuro."""
    r = _verifica("1_correct.lean")
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
    r = _verifica("3_axiom.lean")
    assert r.status == REJECTED
    assert "controllo sintattico preventivo" in _regola_fallita(r)


def test_3b_rifiuta_assioma_anche_senza_controllo_sintattico():
    r = _verifica("3_axiom.lean", run_guard=False)
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
    # Su Lean 4.27 l'assioma lasciato e' `Lean.ofReduceBool`; su Lean 4.33 e' un
    # assioma con un nome PER DICHIARAZIONE, del tipo
    # `JugglerConjecture.jugglerStep_36._native.native_decide.ax_1_1`. E' la
    # ragione per cui il verificatore lavora con una lista di assiomi AMMESSI e
    # non con una lista di assiomi vietati: un elenco di nomi da vietare
    # avrebbe mancato la forma nuova senza dire niente.
    assert ("ofReduceBool" in r.errors
            or "native_decide" in r.errors), r.errors[:300]


# --- 5. RIFIUTA un enunciato indebolito -------------------------------------

def test_5_rifiuta_enunciato_piu_debole():
    """Il candidato dimostra `jugglerStep 36 = 6 ∨ jugglerStep 36 = 7`,
    che e' strettamente piu' debole dell'originale `jugglerStep 36 = 6`.
    Il controllo sintattico non puo' accorgersene: e' un lavoro per Lean."""
    r = _verifica("5_weaker.lean")
    assert r.status == REJECTED
    assert "tipo identico all'originale" in _regola_fallita(r)


# --- 6. RIFIUTA chi ridefinisce una definizione dell'archivio ---------------

def test_6_rifiuta_ridefinizione_di_una_definizione():
    """Il candidato ridefinisce `jugglerStep` come la funzione costante 6.
    L'enunciato e' scritto IDENTICO all'originale, e la prova e' `rfl`: se il
    confronto fosse testuale, passerebbe."""
    r = _verifica("6_redefinition.lean")
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
    r = verify(con_buco[0].theorem, fixture("1_correct.lean"), index=idx)
    assert r.status == UNVERIFIABLE, f"atteso NON_VERIFICABILE, ottenuto {r.status}"
    assert "risposta" in r.message.lower()


# --- Extra: il timeout ------------------------------------------------------

def test_8_il_timeout_funziona():
    """Con un secondo a disposizione nessuna verifica puo' finire."""
    r = _verifica("1_correct.lean", timeout=1)
    assert r.status == TIMEOUT, f"atteso TIMEOUT, ottenuto {r.status}"
    assert "entro il tempo massimo" in _regola_fallita(r)


# --- Extra: la coda parallela -----------------------------------------------

def test_9_verifiche_in_parallelo():
    """Due verifiche insieme devono dare gli stessi esiti di due verifiche
    separate, senza pestarsi i piedi sui file temporanei."""
    risultati = verify_many(
        [(PROBLEMA, fixture("1_correct.lean")),
         (PROBLEMA, fixture("5_weaker.lean"))],
        jobs_parallel=2,
    )
    assert len(risultati) == 2
    assert risultati[0].status == ACCEPTED, risultati[0].render()
    assert risultati[1].status == REJECTED, risultati[1].render()


# --- Extra: i messaggi restituiti a chi ha scritto il file ------------------

RUMORE_COPYRIGHT = """\
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
    """`#check` e `#print` producono messaggi `info:`. Se li buttassimo via,
    chi scrive la dimostrazione non avrebbe modo di ispezionare le definizioni
    e dovrebbe dedurle provocando errori di proposito — cosa che e' davvero
    successa durante il primo collaudo con l'agent."""
    from verify import _lean_errors
    out = _lean_errors(RUMORE_COPYRIGHT)
    assert "@Nat.floor" in out, "l'output di #check deve arrivare"
    assert "def Even" in out, "l'output di #print deve arrivare"
    assert "fun a => exists r, a = r + r" in out, \
        "le righe di continuazione del messaggio devono restare attaccate"


def test_11_gli_errori_veri_arrivano_con_il_contesto():
    from verify import _lean_errors
    out = _lean_errors(RUMORE_COPYRIGHT)
    assert "unsolved goals" in out
    assert "|- n = 6" in out, "il contesto dell'obiettivo non dimostrato serve a capire l'errore"
    assert "Illegal axiom detected: 'sorryAx'" in out


def test_12_il_rumore_dei_linter_di_stile_viene_tolto():
    """Il linter del copyright dell'archivio ripete quindici righe di licenza a
    ogni messaggio: e' irrilevante per un file temporaneo e inonderebbe il
    contesto di chi legge."""
    from verify import _lean_errors
    out = _lean_errors(RUMORE_COPYRIGHT)
    assert "copyright" not in out.lower()
    assert "Apache" not in out
    assert "Building" not in out and "Build completed" not in out, \
        "le righe di stato di lake non sono messaggi di Lean"


def test_13_i_messaggi_ripetuti_compaiono_una_volta_sola():
    from verify import _lean_errors
    doppio = RUMORE_COPYRIGHT + RUMORE_COPYRIGHT
    assert _lean_errors(doppio).count("@Nat.floor") == 1


# --- Extra: un candidato che tenta di sabotare l'archivio -------------------

def test_14_un_candidato_non_riesce_a_riscrivere_un_file_dell_archivio(tmp_path):
    """Il test di sicurezza piu' importante.

    comparator esporta il Challenge PRIMA di compilare la Solution, quindi un
    sabotaggio dei file compilati dell'archivio non altera la verifica in corso:
    altera tutte quelle SUCCESSIVE, facendole confrontare la soluzione con un
    enunciato diverso da quello vero. E' l'assunto 2 del README di comparator,
    e per noi che facciamo verifiche a ripetizione non e' un assunto ma un
    rischio concreto.

    Il candidato qui usa `#eval` per riscrivere `JugglerConjecture.olean`.
    Verifichiamo tre cose: il guard lo rifiuta; con il guard disattivato la
    sandbox lo blocca comunque; e il file resta byte per byte identico.
    """
    import hashlib
    import guard

    bersaglio = (config.ARCHIVE / ".lake" / "build" / "lib" / "lean"
                 / "FormalConjectures" / "Wikipedia" / "JugglerConjecture.olean")
    if not bersaglio.is_file():
        pytest.skip("archivio non compilato")

    def hash_bersaglio() -> str:
        return hashlib.sha256(bersaglio.read_bytes()).hexdigest()

    prima = hash_bersaglio()

    sabotatore = tmp_path / "sabotatore.lean"
    sabotatore.write_text(common.adatta(f'''import FormalConjectures.Util.ProblemImports

#eval show IO Unit from do
  try
    IO.FS.writeFile "{bersaglio}" "ARCHIVIO ROVINATO"
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

    # 1. in uso normale il guard lo ferma prima di compilarlo
    rapporto = guard.check_file(sabotatore)
    assert not rapporto.ok, "il guard deve rifiutare un file che usa #eval e IO"
    regole = {f.rule for f in rapporto.findings}
    assert "comando:#eval" in regole
    assert "metaprogrammazione:IO" in regole

    # 2. col guard disattivato, la sandbox deve bloccarlo comunque
    r = verify(PROBLEMA, sabotatore, run_guard=False)
    assert "sabotaggio impedito" in r.raw_output or "SABOTAGGIO RIUSCITO" not in r.raw_output, \
        f"il sabotaggio non e' stato impedito:\n{r.raw_output[:2000]}"

    # 3. il file dell'archivio deve essere byte per byte identico
    assert hash_bersaglio() == prima, \
        "il file compilato dell'archivio E' STATO MODIFICATO: tutte le verifiche " \
        "successive confronterebbero le soluzioni con un enunciato alterato"


def test_i_problemi_oeis_si_leggono_dal_sorgente():
    """Le voci OEIS hanno un modulo fra guillemet e un file senza.

    Un identificatore Lean non puo' cominciare con una cifra, quindi il modulo
    della voce A109074 si chiama `FormalConjectures.OEIS.«109074»` mentre il file
    sul disco e' `109074.lean`. Finche' la conversione non toglieva le virgolette,
    NESSUNO dei 209 problemi OEIS era leggibile: l'agent non poteva riceverli,
    l'estrattore non poteva estrarli, la sfida negata non si poteva generare — e
    quei 209 sono la famiglia su cui il piano di spesa si appoggia.
    """
    idx = ProblemIndex.load()
    oeis = [p for p in idx.problems if "OEIS" in p.module]
    if not oeis:
        pytest.skip("questo snapshot non contiene voci OEIS")
    letti = 0
    for p in oeis[:20]:
        if p.source_file.is_file() and p.range:
            assert p.source_text().strip(), p.theorem
            letti += 1
    assert letti >= 15, f"solo {letti} voci OEIS su 20 leggibili dal sorgente"
