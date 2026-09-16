"""A connection that drops mid-response must not stop the run, make the work done
disappear, soften the global spending limit, or consume the problem's cap.

The incidents:
  * 12 September: a "Connection reset by peer" while streaming the third problem.
    The exception was `httpx2.ReadError`, which the SDK does not translate into
    `anthropic.APIError`: the process died and the report, written only at the end,
    was never written at all.
  * the night of 13 September: with the first fix, every interrupted call was
    charged at its worst case AGAINST THE PROBLEM'S CAP as well. A $0.84 charge on
    a $1 cap closed the attempt on its own: six problems out of twelve ended that
    way. The cause of the interruptions was the Mac going to sleep (see
    agent/awake.py).

Here the client is simulated; the API is never called.
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

MODEL = "claude-opus-5"
INPUT_TOKENS = 1000


class _Usage:
    input_tokens = 10
    output_tokens = 10
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0
    cache_creation = None


class _Answer:
    """A response with no tool calls: the attempt ends there."""
    content = [SimpleNamespace(type="text", text="stopping")]
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


_PROBLEM = SimpleNamespace(theorem="Trial.network", module="FormalConjectures.Trial",
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
    return agent.solve(_PROBLEM, None, client=client, model=MODEL, budget=budget,
                       problem_cap=cap, verbose=False)


def _worst(budget):
    return budget.max_possible_cost(INPUT_TOKENS, agent.MAX_TOKENS)


def test_a_dropped_connection_is_retried_and_charged_to_the_global_budget():
    client = _Client([_reset(), _Answer()])
    b = Budget(dollar_limit=20.0, model=MODEL)
    t = _solve(client, b, cap=5.0)
    assert client.calls == 2, "the interrupted call has to be made again"
    assert t.network_interruptions == 1
    assert "stopped using the tools" in t.reason, t.reason
    assert b.spent >= _worst(b) - 1e-9, "the global budget has to count the worst case"
    assert t.network_charge == pytest.approx(_worst(b)), "and the report has to say so"
    assert t.usage.cost(MODEL) < 0.01, "but the problem's cost stays the real one"


def test_an_interruption_does_not_consume_the_problems_cap():
    """This is the test the first fix would have failed: with a $1 cap, two $0.81
    interruptions must not prevent the third call, and the third must have the same
    room as the first."""
    client = _Client([_reset(), _reset(), _Answer()])
    b = Budget(dollar_limit=20.0, model=MODEL)
    t = _solve(client, b, cap=1.0)
    assert client.calls == 3, t.reason
    assert "stopped using the tools" in t.reason, t.reason
    assert client.max_tokens[2] == client.max_tokens[0], client.max_tokens
    assert t.network_charge > 1.0, "the charges exceed the cap, rightly: they sit outside it"


def test_three_interruptions_in_a_row_close_the_problem_not_the_run():
    client = _Client([_reset() for _ in range(10)])
    b = Budget(dollar_limit=20.0, model=MODEL)
    t = _solve(client, b, cap=5.0)          # no exception may escape from here
    assert client.calls == agent.MAX_CONSECUTIVE_NETWORK_ERRORS
    assert t.network_interruptions == agent.MAX_CONSECUTIVE_NETWORK_ERRORS
    assert "repeated network error" in t.reason, t.reason


def test_with_interruptions_the_global_limit_stays_hard():
    client = _Client([_reset() for _ in range(10)])
    b = Budget(dollar_limit=1.0, model=MODEL)
    with pytest.raises(SpendLimitExceeded):
        _solve(client, b, cap=5.0)
    assert b.spent <= 1.0 + 1e-9, f"spent ${b.spent:.4f} against a global limit of $1"


def test_the_report_is_written_even_when_the_run_is_unfinished(tmp_path):
    client = _Client([_reset(), _Answer()])
    b = Budget(dollar_limit=20.0, model=MODEL)
    t = _solve(client, b, cap=5.0)
    args = SimpleNamespace(model=MODEL, effort="low", instructions="insistent", budget=20.0)
    path = tmp_path / "report.json"
    agent.write_report(path, args=args, cap=5.0, budget=b, attempts=[t], full=False)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["full"] is False
    assert data["spent"] == pytest.approx(b.spent)
    assert data["attempts"][0]["network_interruptions"] == 1
    assert data["attempts"][0]["precautionary_network_charge"] == pytest.approx(_worst(b))
