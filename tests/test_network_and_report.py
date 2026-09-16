"""Una connessione che cade a meta' risposta non deve fermare il giro, far
sparire il lavoro fatto, rendere meno rigido il limite totale di spesa, ne'
consumare il tetto del problema.

Gli incidenti:
  * 12 settembre: un «Connection reset by peer» durante lo streaming del terzo
    problema. L'eccezione era `httpx2.ReadError`, che l'SDK non traduce in
    `anthropic.APIError`: il processo e' morto e il rapporto, scritto solo alla
    fine, non e' mai stato scritto.
  * notte del 13 settembre: con la prima correzione, ogni chiamata interrotta
    veniva addebitata al caso peggiore ANCHE sul tetto del problema. Un addebito
    da $0,84 su un tetto da $1 chiudeva il tentativo da solo: sei problemi su
    dodici sono finiti cosi'. La causa delle interruzioni era il Mac in
    sospensione (vedi agent/awake.py).

Qui si simula il client, senza chiamare l'API.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx2
import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "agent"))
sys.path.insert(0, str(RADICE / "verifier"))

import agent
from costs import Budget, LimiteSpesaSuperato

MODELLO = "claude-opus-5"
TOKEN_INGRESSO = 1000


class _Usage:
    input_tokens = 10
    output_tokens = 10
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0
    cache_creation = None


class _Risposta:
    """Una risposta senza tools: il tentativo finisce li'."""
    content = [SimpleNamespace(type="text", text="mi fermo")]
    stop_reason = "end_turn"
    usage = _Usage()


class _Flusso:
    def __init__(self, esito):
        self.esito = esito

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        if isinstance(self.esito, BaseException):
            raise self.esito
        return self.esito


class _Client:
    def __init__(self, esiti):
        self.esiti = list(esiti)
        self.chiamate = 0
        self.max_tokens = []
        self.messages = self

    def count_tokens(self, **kw):
        return SimpleNamespace(input_tokens=TOKEN_INGRESSO)

    def stream(self, **kw):
        self.chiamate += 1
        self.max_tokens.append(kw["max_tokens"])
        return _Flusso(self.esiti.pop(0))


_PROBLEMA = SimpleNamespace(theorem="Prova.rete", module="FormalConjectures.Prova",
                            category="test", docstring="")


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "file_senza_dimostrazioni", lambda p, i: "theorem x : True := sorry")
    monkeypatch.setattr(agent, "controlla_che_sia_nascosta", lambda p, t: None)
    monkeypatch.setattr(agent.config_verificatore, "ROOT", tmp_path)
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)


def _reset():
    return httpx2.ReadError("[Errno 54] Connection reset by peer")


def _risolvi(client, budget, tetto):
    return agent.risolvi(_PROBLEMA, None, client=client, modello=MODELLO, budget=budget,
                          tetto_problema=tetto, verboso=False)


def _peggiore(budget):
    return budget.costo_massimo_possibile(TOKEN_INGRESSO, agent.MAX_TOKENS)


def test_una_connessione_caduta_si_ritenta_e_va_sul_budget_totale():
    client = _Client([_reset(), _Risposta()])
    b = Budget(limite_dollari=20.0, modello=MODELLO)
    t = _risolvi(client, b, tetto=5.0)
    assert client.chiamate == 2, "la chiamata interrotta va rifatta"
    assert t.interruzioni_rete == 1
    assert "smesso di usare gli tools" in t.motivo, t.motivo
    assert b.speso >= _peggiore(b) - 1e-9, "il budget totale deve contare il caso peggiore"
    assert t.addebito_rete == pytest.approx(_peggiore(b)), "e il rapporto deve dirlo"
    assert t.consumo.costo(MODELLO) < 0.01, "ma il costo del problema resta quello vero"


def test_l_interruzione_non_consuma_il_tetto_del_problema():
    """E' il test che la prima correzione avrebbe fatto fallire: con un tetto da
    $1, due interruzioni da $0,81 non devono impedire la terza chiamata, e la
    terza deve avere lo stesso spazio della prima."""
    client = _Client([_reset(), _reset(), _Risposta()])
    b = Budget(limite_dollari=20.0, modello=MODELLO)
    t = _risolvi(client, b, tetto=1.0)
    assert client.chiamate == 3, t.motivo
    assert "smesso di usare gli tools" in t.motivo, t.motivo
    assert client.max_tokens[2] == client.max_tokens[0], client.max_tokens
    assert t.addebito_rete > 1.0, "gli addebiti superano il tetto, ed e' giusto: stanno fuori"


def test_tre_interruzioni_di_fila_chiudono_il_problema_non_il_giro():
    client = _Client([_reset() for _ in range(10)])
    b = Budget(limite_dollari=20.0, modello=MODELLO)
    t = _risolvi(client, b, tetto=5.0)          # nessuna eccezione deve uscire da qui
    assert client.chiamate == agent.MAX_ERRORI_RETE_DI_FILA
    assert t.interruzioni_rete == agent.MAX_ERRORI_RETE_DI_FILA
    assert "errore di rete" in t.motivo, t.motivo


def test_con_le_interruzioni_il_limite_totale_resta_rigido():
    client = _Client([_reset() for _ in range(10)])
    b = Budget(limite_dollari=1.0, modello=MODELLO)
    with pytest.raises(LimiteSpesaSuperato):
        _risolvi(client, b, tetto=5.0)
    assert b.speso <= 1.0 + 1e-9, f"speso ${b.speso:.4f} con un limite totale di $1"


def test_il_rapporto_si_scrive_anche_a_giro_non_finito(tmp_path):
    client = _Client([_reset(), _Risposta()])
    b = Budget(limite_dollari=20.0, modello=MODELLO)
    t = _risolvi(client, b, tetto=5.0)
    args = SimpleNamespace(modello=MODELLO, effort="low", istruzioni="insistenti", budget=20.0)
    percorso = tmp_path / "rapporto.json"
    agent.scrivi_rapporto(percorso, args=args, tetto=5.0, budget=b, tentativi=[t],
                           completo=False)
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    assert dati["completo"] is False
    assert dati["speso"] == pytest.approx(b.speso)
    assert dati["tentativi"][0]["interruzioni_rete"] == 1
    assert dati["tentativi"][0]["addebito_rete_prudenziale"] == pytest.approx(_peggiore(b))
