"""Una connessione che cade a meta' answer non deve fermare il giro, far
sparire il job fatto, rendere meno rigido il limit total di spesa, ne'
consumare il cap del problem.

Gli incidenti:
  * 12 settembre: un «Connection reset by peer» durante lo streaming del terzo
    problem. L'eccezione era `httpx2.ReadError`, che l'SDK non traduce in
    `anthropic.APIError`: il processo e' morto e il report, scritto only_ alla
    end, non e' mai state scritto.
  * notte del 13 settembre: con la before correzione, ogni call interrupted
    veniva addebitata al caso worst ANCHE sul cap del problem. Un addebito
    da $0,84 su un cap da $1 chiudeva il attempt da only_: sei problems su
    dodici sono finiti cosi'. La cause delle interruzioni era il Mac in
    sospensione (vedi agent/awake.py).

Qui si simula il client, senza chiamare l'API.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx2
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "verifier"))

import agent
from costs import Budget, SpendLimitExceeded

TEMPLATE = "claude-opus-5"
INPUT_TOKENS = 1000


class _Usage:
    input_tokens = 10
    output_tokens = 10
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0
    cache_creation = None


class _Answer:
    """Una answer senza tools: il attempt finisce li'."""
    content = [SimpleNamespace(type="text", text="mi fermo")]
    stop_reason = "end_turn"
    usage = _Usage()


class _Stream:
    def __init__(self, result):
        self.result = result

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class _Client:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0
        self.max_tokens = []
        self.messages = self

    def count_tokens(self, **kw):
        return SimpleNamespace(input_tokens=INPUT_TOKENS)

    def stream(self, **kw):
        self.calls += 1
        self.max_tokens.append(kw["max_tokens"])
        return _Stream(self.results.pop(0))


_PROBLEMA = SimpleNamespace(theorem="Prova.rete", module="FormalConjectures.Prova",
                            category="test", docstring="")


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "file_without_proofs", lambda p, i: "theorem x : True := sorry")
    monkeypatch.setattr(agent, "check_it_is_hidden", lambda p, t: None)
    monkeypatch.setattr(agent.verifier_config, "ROOT", tmp_path)
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)


def _reset():
    return httpx2.ReadError("[Errno 54] Connection reset by peer")


def _solve(client, budget, cap):
    return agent.solve_(_PROBLEMA, None, client=client, model=TEMPLATE, budget=budget,
                          problem_cap=cap, verbose=False)


def _worst(budget):
    return budget.max_possible_cost(INPUT_TOKENS, agent.MAX_TOKENS)


def test_una_connessione_caduta_si_ritenta_e_va_sul_budget_totale():
    client = _Client([_reset(), _Answer()])
    b = Budget(dollar_limit=20.0, model=TEMPLATE)
    t = _solve(client, b, cap=5.0)
    assert client.calls == 2, "la call interrupted va rifatta"
    assert t.network_interruptions == 1
    assert "smesso di usare gli tools" in t.reason, t.reason
    assert b.spent >= _worst(b) - 1e-9, "il budget total deve contare il caso worst"
    assert t.network_charge == pytest.approx(_worst(b)), "e il report deve dirlo"
    assert t.usage.cost(TEMPLATE) < 0.01, "ma il cost del problem resta quello vero"


def test_l_interruzione_non_consuma_il_tetto_del_problema():
    """E' il test che la before correzione avrebbe fatto fallire: con un cap da
    $1, two interruzioni da $0,81 non devono impedire la terza call, e la
    terza deve avere lo stesso spazio della before."""
    client = _Client([_reset(), _reset(), _Answer()])
    b = Budget(dollar_limit=20.0, model=TEMPLATE)
    t = _solve(client, b, cap=1.0)
    assert client.calls == 3, t.reason
    assert "smesso di usare gli tools" in t.reason, t.reason
    assert client.max_tokens[2] == client.max_tokens[0], client.max_tokens
    assert t.network_charge > 1.0, "gli addebiti superano il cap, ed e' giusto: stanno out_of"


def test_tre_interruzioni_di_fila_chiudono_il_problema_non_il_giro():
    client = _Client([_reset() for _ in range(10)])
    b = Budget(dollar_limit=20.0, model=TEMPLATE)
    t = _solve(client, b, cap=5.0)          # nessuna eccezione deve uscire da qui
    assert client.calls == agent.MAX_CONSECUTIVE_NETWORK_ERRORS
    assert t.network_interruptions == agent.MAX_CONSECUTIVE_NETWORK_ERRORS
    assert "error di rete" in t.reason, t.reason


def test_con_le_interruzioni_il_limite_totale_resta_rigido():
    client = _Client([_reset() for _ in range(10)])
    b = Budget(dollar_limit=1.0, model=TEMPLATE)
    with pytest.raises(SpendLimitExceeded):
        _solve(client, b, cap=5.0)
    assert b.spent <= 1.0 + 1e-9, f"spent ${b.spent:.4f} con un limit total di $1"


def test_il_rapporto_si_scrive_anche_a_giro_non_finito(tmp_path):
    client = _Client([_reset(), _Answer()])
    b = Budget(dollar_limit=20.0, model=TEMPLATE)
    t = _solve(client, b, cap=5.0)
    args = SimpleNamespace(model=TEMPLATE, effort="low", istruzioni="insistenti", budget=20.0)
    path = tmp_path / "report.json"
    agent.write_report(path, args=args, cap=5.0, budget=b, attempts=[t],
                           full_=False)
    data_ = json.loads(path.read_text(encoding="utf-8"))
    assert data_["full_"] is False
    assert data_["spent"] == pytest.approx(b.spent)
    assert data_["attempts"][0]["network_interruptions"] == 1
    assert data_["attempts"][0]["addebito_rete_prudenziale"] == pytest.approx(_worst(b))
