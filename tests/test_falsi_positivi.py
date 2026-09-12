"""I cinque falsi positivi della sonda, uno test per ciascuno.

Cinque «ritrovamenti» annunciati e tutti falsi, per cinque meccanismi diversi.
La causa comune è una sola, e vale la pena scriverla: **la sonda giudicava il
proprio output.** Ogni strato di giudizio che le avevo aggiunto — «il file
compila», «quali righe portano errori», «quali assiomi risultano» — era una
imitazione più povera di quello che `verify.py` fa per davvero, e ognuna aveva un
buco diverso.

La correzione strutturale è che la sonda **propone** e `verify.py` **giudica**.
Questi test proteggono i cinque buchi in modo che, se qualcuno rimette un
verdetto dentro la sonda, si rompano.
"""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "scripts"))
sys.path.insert(0, str(RADICE / "verifier"))

import pytest
import sonda_artefatti as sonda
import sonda_lean


class FintoProblema:
    theorem = "Foo.bar"
    module = "FormalConjectures.Foo"


# --- 1. `plausible` lascia un `sorry` e il file compila ----------------------

def test_1_plausible_senza_controesempio_non_ha_dimostrato_niente():
    """Primo falso positivo. `plausible`, quando non trova controesempi, scrive
    «Unable to find a counter-example» e lascia un `sorry`: il file compila con un
    avviso. Il verdetto guardava solo se compilava."""
    esito, _ = sonda_lean.classifica(
        "Unable to find a counter-example\n"
        "E0.lean:5:0: warning: declaration uses 'sorry'", ok=True)
    assert esito == "aperta"
    # e con il criterio degli assiomi, la stessa cosa
    r = sonda.leggi("'sonda_plausible' depends on axioms: [sorryAx]",
                    {"sonda_plausible": ("plausible", False)})
    assert r["prove"][0]["esito"] == "aperta"


# --- 2. due esplorazioni che si scambiano i messaggi ------------------------

def test_2_gli_slot_di_esplorazione_sono_esclusivi():
    """Secondo falso positivo. Il file di ispezione aveva un nome fisso
    (`E0.lean`), quindi due esplorazioni concorrenti si sovrascrivevano il file e
    ognuna leggeva i messaggi dell'altra: una tattica banale sembrava aver chiuso
    un problema di topologia, e i messaggi erano di un problema di grafi."""
    import esplora
    assert hasattr(esplora, "_slot_esclusivo"), (
        "il meccanismo del lucchetto è stato rimosso: due esplorazioni "
        "concorrenti tornerebbero a mescolarsi")
    assert esplora.SLOT_DISPONIBILI >= 2
    import inspect
    assert "flock" in inspect.getsource(esplora._slot_esclusivo), (
        "il lucchetto deve valere FRA PROCESSI, non solo fra thread")


# --- 3. il verdetto letto dalle righe di errore -----------------------------

def test_3_il_verdetto_si_legge_per_nome_non_per_riga():
    """Terzo falso positivo. Il lettore attribuiva gli errori di Lean alla
    dichiarazione sbagliata, e arrivava a dire che un enunciato E la sua negazione
    erano entrambi dimostrati — cosa logicamente impossibile."""
    uscita = ("E0.lean:9:2: error: qualcosa non va qui\n"
              "'sonda_decide' depends on axioms: [sorryAx]\n"
              "'sonda_decide_neg' does not depend on any axioms")
    mappa = {"sonda_decide": ("decide", False), "sonda_decide_neg": ("decide", True)}
    esiti = {(p["tattica"], p["negato"]): p["esito"]
             for p in sonda.leggi(uscita, mappa)["prove"]}
    # la riga di errore non deve spostare nessun verdetto: contano i nomi
    assert esiti[("decide", False)] == "aperta"
    assert esiti[("decide", True)] == "confutata"


# --- 4. `type_of%` senza `@` prova un enunciato diverso ---------------------

def test_4_type_of_va_scritto_con_la_chiocciola():
    """Quarto falso positivo. `type_of% Foo` senza `@` fa istanziare a Lean gli
    argomenti impliciti come metavariabili: la sonda provava un enunciato DIVERSO
    da quello dell'archivio, e `aesop` «confutava» la congettura di Agrawal
    mentre il verificatore vero rifiutava la stessa dimostrazione."""
    codice, _ = sonda.costruisci(FintoProblema(), 200000)
    assert "type_of% @Foo.bar" in codice
    assert "type_of% Foo.bar" not in codice.replace("type_of% @Foo.bar", "")


# --- 5. l'ambiente sbagliato -----------------------------------------------

def test_5_rifiuta_di_girare_sull_archivio_sbagliato(tmp_path):
    """Quinto falso positivo. La sonda girava con l'indice predefinito
    (bench-v1) mentre i bersagli erano scelti su `main`: gli import fallivano, i
    messaggi erano spazzatura, e il lettore ci leggeva dentro dei successi."""
    import json
    import config
    bersagli = tmp_path / "bersagli.json"
    bersagli.write_text(json.dumps(
        {"snapshot": "external/fc-main 0a8b856c", "candidati": []}), encoding="utf-8")
    if "fc-main" in str(config.ARCHIVE):
        pytest.skip("questo test vale quando l'archivio in uso NON è fc-main")
    with pytest.raises(SystemExit) as e:
        sonda.controlla_ambiente(bersagli)
    assert "AMBIENTE SBAGLIATO" in str(e.value)


# --- la correzione strutturale ---------------------------------------------

def test_la_sonda_non_segnala_senza_il_verificatore():
    """Il vincolo che rende impossibile un sesto falso positivo della stessa
    famiglia: il flag di segnalazione si accende SOLO dopo un ACCETTATO che
    arriva da `verify.py`."""
    import inspect
    src = inspect.getsource(sonda.main)
    assert "conferma_col_verificatore" in src, (
        "la sonda deve passare i candidati al verificatore")
    # ogni assegnazione del flag deve stare in un ramo che controlla ACCETTATO
    pezzi = src.split('voce["ATTENZIONE"]')
    for prima in pezzi[:-1]:
        assert "ACCETTATO" in prima[-400:], (
            "un ATTENZIONE viene acceso senza passare dal verificatore")


def test_conferma_col_verificatore_costruisce_il_candidato_giusto():
    """Nella forma negata deve usare la modalità confutazione e il `@`."""
    import inspect
    src = inspect.getsource(sonda.conferma_col_verificatore)
    assert "type_of% @{problema.theorem}" in src
    assert "CONFUTAZIONE" in src and "STRETTA" in src
    assert "run_guard=False" in src   # il candidato importa il modulo di proposito
