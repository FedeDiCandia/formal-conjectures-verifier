"""I cinque falsi positivi della probe, one test per ciascuno.

Cinque «ritrovamenti» annunciati e all_items falsi, per cinque meccanismi diversi.
La cause common è one sola, e vale la pena scriverla: **la probe giudicava il
proprio output.** Ogni strato di giudizio che le avevo aggiunto — «il file
compila», «which lines portano errors», «which axioms risultano» — era one
imitazione più povera di quello che `verify.py` fa per davvero, e ognuna aveva un
buco diverso.

La correzione strutturale è che la probe **propone** e `verify.py` **giudica**.
Questi test proteggono i cinque buchi in way che, se qualcuno rimette un
verdict inside la probe, si rompano.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "verifier"))

import pytest
import probe_artefacts as probe
import probe_lean


class FakeProblem:
    theorem = "Foo.bar"
    module = "FormalConjectures.Foo"


# --- 1. `plausible` lascia un `sorry` e il file compila ----------------------

def test_1_plausible_senza_controesempio_non_ha_dimostrato_niente():
    """Primo falso positivo. `plausible`, quando non trova controesempi, scrive
    «Unable to find a counter-example» e lascia un `sorry`: il file compila con un
    avviso. Il verdict guardava only se compilava."""
    result, _ = probe_lean.classify(
        "Unable to find a counter-example\n"
        "E0.lean:5:0: warning: declaration uses 'sorry'", ok=True)
    assert result == "aperta"
    # e con il criterio degli axioms, la stessa cosa
    r = probe.read("'sonda_plausible' depends on axioms: [sorryAx]",
                    {"sonda_plausible": ("plausible", False)})
    assert r["trials"][0]["result"] == "aperta"


# --- 2. two explorations che si scambiano i messages ------------------------

def test_2_gli_slot_di_esplorazione_sono_esclusivi():
    """Secondo falso positivo. Il file di inspection aveva un name fisso
    (`E0.lean`), quindi two explorations concorrenti si sovrascrivevano il file e
    ognuna leggeva i messages dell'altra: one tactic banale sembrava aver chiuso
    un problem di topologia, e i messages erano di un problem di grafi."""
    import explore
    assert hasattr(explore, "_exclusive_slot"), (
        "il meccanismo del lock è state rimosso: two explorations "
        "concorrenti tornerebbero a mescolarsi")
    assert explore.AVAILABLE_SLOTS >= 2
    import inspect
    assert "flock" in inspect.getsource(explore._exclusive_slot), (
        "il lock deve valere FRA PROCESSI, non only fra thread")


# --- 3. il verdict letto dalle lines di error -----------------------------

def test_3_il_verdetto_si_legge_per_nome_non_per_riga():
    """Terzo falso positivo. Il lettore attribuiva gli errors di Lean alla
    declaration sbagliata, e arrivava a dire che un statement E la sua negation
    erano entrambi dimostrati — cosa logicamente impossibile."""
    output = ("E0.lean:9:2: error: qualcosa non va qui\n"
              "'sonda_decide' depends on axioms: [sorryAx]\n"
              "'sonda_decide_neg' does not depend on any axioms")
    mapping = {"sonda_decide": ("decide", False), "sonda_decide_neg": ("decide", True)}
    results = {(p["tactic"], p["negated"]): p["result"]
             for p in probe.read(output, mapping)["trials"]}
    # la line di error non deve spostare nessun verdict: contano i names
    assert results[("decide", False)] == "aperta"
    assert results[("decide", True)] == "confutata"


# --- 4. `type_of%` senza `@` trial un statement diverso ---------------------

def test_4_type_of_va_scritto_con_la_chiocciola():
    """Quarto falso positivo. `type_of% Foo` senza `@` fa istanziare a Lean gli
    arguments impliciti come metavariabili: la probe provava un statement DIVERSO
    da quello dell'archive, e `aesop` «confutava» la congettura di Agrawal
    mentre il verifier vero rifiutava la stessa dimostrazione."""
    code, _ = probe.build(FakeProblem(), 200000)
    assert "type_of% @Foo.bar" in code
    assert "type_of% Foo.bar" not in code.replace("type_of% @Foo.bar", "")


# --- 5. l'environment sbagliato -----------------------------------------------

def test_5_rifiuta_di_girare_sull_archivio_sbagliato(tmp_path):
    """Quinto falso positivo. La probe girava con l'index predefinito
    (bench-v1) mentre i targets erano chosen su `main`: gli import fallivano, i
    messages erano spazzatura, e il lettore ci leggeva inside dei successi."""
    import json
    import config
    targets = tmp_path / "targets.json"
    targets.write_text(json.dumps(
        {"snapshot": "external/fc-main 0a8b856c", "candidates": []}), encoding="utf-8")
    if "fc-main" in str(config.ARCHIVE):
        pytest.skip("questo test vale quando l'archive in uso NON è fc-main")
    with pytest.raises(SystemExit) as e:
        probe.check_environment(targets)
    assert "AMBIENTE SBAGLIATO" in str(e.value)


# --- la correzione strutturale ---------------------------------------------

def test_la_sonda_non_segnala_senza_il_verificatore():
    """Il vincolo che rende impossibile un sesto falso positivo della stessa
    famiglia: il flag di segnalazione si accende SOLO after un ACCEPTED che
    arriva da `verify.py`."""
    import inspect
    src = inspect.getsource(probe.main)
    assert "confirm_with_verifier" in src, (
        "la probe deve passare i candidates al verifier")
    # ogni assegnazione del flag deve stare in un branch che controlla ACCEPTED
    pieces = src.split('entry["ATTENZIONE"]')
    for before in pieces[:-1]:
        assert "ACCEPTED" in before[-400:], (
            "un ATTENZIONE viene acceso senza passare dal verifier")


def test_conferma_col_verificatore_costruisce_il_candidato_giusto():
    """Nella forma negata deve usare la modalità confutazione e il `@`."""
    import inspect
    src = inspect.getsource(probe.confirm_with_verifier)
    assert "type_of% @{problem.theorem}" in src
    assert "REFUTATION" in src and "STRICT" in src
    assert "run_guard=False" in src   # il candidato importa il module di proposito
