"""Una connessione che cade a meta' risposta non deve fermare il giro, far
sparire il lavoro fatto o rendere il limite di spesa meno rigido.

L'incidente, 12 settembre: un «Connection reset by peer» durante lo streaming
del terzo problema. L'eccezione era `httpx2.ReadError`, che l'SDK non traduce in
`anthropic.APIError`: il ciclo principale non la prendeva, il processo e' morto,
e il rapporto — scritto solo alla fine — non e' mai stato scritto. I due
tentativi gia' conclusi risultavano solo dal registro, e la spesa del terzo non
risultava da nessuna parte.

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

import agente
from costi import Budget

MODELLO = "claude-opus-5"
TOKEN_INGRESSO = 1000


class _Usage:
    input_tokens = 10
    output_tokens = 10
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0
    cache_creation = None


class _Risposta:
    """Una risposta senza strumenti: il tentativo finisce li'."""
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
        self.messages = self

    def count_tokens(self, **kw):
        return SimpleNamespace(input_tokens=TOKEN_INGRESSO)

    def stream(self, **kw):
        self.chiamate += 1
        return _Flusso(self.esiti.pop(0))


_PROBLEMA = SimpleNamespace(theorem="Prova.rete", module="FormalConjectures.Prova",
                            category="test", docstring="")


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, tmp_path):
    monkeypatch.setattr(agente, "file_senza_dimostrazioni", lambda p, i: "theorem x : True := sorry")
    monkeypatch.setattr(agente, "controlla_che_sia_nascosta", lambda p, t: None)
    monkeypatch.setattr(agente.config_verificatore, "ROOT", tmp_path)
    monkeypatch.setattr(agente.time, "sleep", lambda s: None)


def _reset():
    return httpx2.ReadError("[Errno 54] Connection reset by peer")


def _risolvi(client, budget, tetto):
    return agente.risolvi(_PROBLEMA, None, client=client, modello=MODELLO, budget=budget,
                          tetto_problema=tetto, verboso=False)


def test_una_connessione_caduta_si_ritenta_e_si_addebita_il_caso_peggiore():
    client = _Client([_reset(), _Risposta()])
    b = Budget(limite_dollari=20.0, modello=MODELLO)
    t = _risolvi(client, b, tetto=5.0)
    assert client.chiamate == 2, "la chiamata interrotta va rifatta"
    assert t.interruzioni_rete == 1
    assert "smesso di usare gli strumenti" in t.motivo, t.motivo
    peggiore = b.costo_massimo_possibile(TOKEN_INGRESSO, agente.MAX_TOKENS)
    assert b.speso >= peggiore - 1e-9, "la chiamata interrotta deve risultare nella spesa"
    assert t.consumo.costo(MODELLO) >= peggiore - 1e-9, "e nel costo del problema"


def test_tre_interruzioni_di_fila_chiudono_il_problema_non_il_giro():
    client = _Client([_reset() for _ in range(10)])
    b = Budget(limite_dollari=20.0, modello=MODELLO)
    t = _risolvi(client, b, tetto=5.0)          # nessuna eccezione deve uscire da qui
    assert client.chiamate == agente.MAX_ERRORI_RETE_DI_FILA
    assert t.interruzioni_rete == agente.MAX_ERRORI_RETE_DI_FILA
    assert "errore di rete" in t.motivo, t.motivo


def test_con_le_interruzioni_il_tetto_del_problema_resta_rigido():
    client = _Client([_reset() for _ in range(10)])
    b = Budget(limite_dollari=20.0, modello=MODELLO)
    t = _risolvi(client, b, tetto=1.0)
    assert b.speso <= 1.0 + 1e-9, f"speso ${b.speso:.4f} con un tetto di $1"
    assert t.motivo.startswith("budget insufficiente"), t.motivo


def test_il_rapporto_si_scrive_anche_a_giro_non_finito(tmp_path):
    client = _Client([_reset(), _Risposta()])
    b = Budget(limite_dollari=20.0, modello=MODELLO)
    t = _risolvi(client, b, tetto=5.0)
    args = SimpleNamespace(modello=MODELLO, effort="low", istruzioni="insistenti", budget=20.0)
    percorso = tmp_path / "rapporto.json"
    agente.scrivi_rapporto(percorso, args=args, tetto=5.0, budget=b, tentativi=[t],
                           completo=False)
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    assert dati["completo"] is False
    assert dati["speso"] == pytest.approx(b.speso)
    assert dati["tentativi"][0]["interruzioni_rete"] == 1
