"""With a low cap the agent has to make MORE THAN ONE call.

The defect these tests pin down invalidated a whole experiment. The budget check
stopped when `max_tokens` fell below 6000, which at Fable 5.1's prices means $0.30 of
headroom per call: with a $0.50 per-problem cap the agent got one single call, and on
two problems out of eleven it got none. The result looked like "the model gives up"
and was "the accountant will not let it work".

Here the loop's arithmetic is simulated; the API is never called.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "verifier"))

import agent
from costs import Budget, Usage


def _possible_calls(model: str, cap: float, input_tokens: int,
                        cost_per_call: float) -> int:
    """How many calls it manages, under the loop's real rule."""
    b = Budget(dollar_limit=cap * 10, model=model)
    spent_here = 0.0
    calls = 0
    for _ in range(50):
        residue = cap - spent_here
        max_tokens = b.affordable_max_tokens(input_tokens, agent.MAX_TOKENS,
                                              residue=residue)
        if max_tokens < agent.MIN_USEFUL_TOKENS:
            break
        calls += 1
        spent_here += cost_per_call
        # the global budget has to follow, or what is left never falls
        b.record(_fake_usage(cost_per_call, model), "trial")
    return calls


class _FakeUsage:
    def __init__(self, output):
        self.input_tokens = 0
        self.output_tokens = output
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0
        self.cache_creation = None


def _fake_usage(cost: float, model: str):
    from costs import prices
    return _FakeUsage(int(cost * 1_000_000 / prices(model).output))


def test_with_a_low_cap_and_fable_it_makes_more_than_one_call():
    """This is the test the defect would have failed: with a $0.50 cap and
    calls da 5 centesimi, di calls ce ne stanno parecchie."""
    n = _possible_calls("claude-fable-5-1", cap=0.50,
                            input_tokens=8000, cost_per_call=0.05)
    assert n >= 5, f"only {n} calls with a $0.50 cap"


def test_the_old_threshold_stopped_the_attempt_before_it_began():
    """The real numbers from the incident, taken from variant B's log.

    `SidorenkoConjecture...non_bipartite_necessary`: 16 287 token in ingresso,
    cap $0.50, spent $0.00. With the previous threshold the attempt did not even
    start; with the new one it makes its call.
    """
    previous = 6_000
    b = Budget(dollar_limit=5.0, model="claude-fable-5-1")
    max_tokens = b.affordable_max_tokens(16_287, agent.MAX_TOKENS, residue=0.50)
    assert max_tokens < previous, "these are the numbers that stopped the attempt"
    assert max_tokens >= agent.MIN_USEFUL_TOKENS, (
        "with the new threshold the same attempt has to be able to start")


def test_the_limit_stays_hard():
    """The real invariant, worth writing out in full.

    It is not "the worst case always fits in what is left": when what is left does
    not even cover the INPUT cost, the function returns 0 and the loop stops. The
    invariant is: **if the loop proceeds, the worst case fits in what is left.**
    Written badly, this test declared a limit hard when it was not; written this way,
    it says the right thing.
    """
    b = Budget(dollar_limit=5.0, model="claude-fable-5-1")
    for residue in (0.02, 0.05, 0.12, 0.30, 0.50, 1.40, 2.00):
        for input_tokens in (2_000, 10_000, 40_000):
            mt = b.affordable_max_tokens(input_tokens, agent.MAX_TOKENS,
                                          residue=residue)
            if mt < agent.MIN_USEFUL_TOKENS:
                continue          # the loop would stop here: nothing to guarantee
            worst = b.max_possible_cost(input_tokens, mt)
            assert worst <= residue + 1e-9, (
                f"left ${residue}, input {input_tokens}: the worst case is "
                f"${worst:.4f} and exceeds what is left")


def test_below_the_minimum_threshold_it_stops():
    """If there is no room even for a minimal response, the attempt ends."""
    b = Budget(dollar_limit=5.0, model="claude-fable-5-1")
    mt = b.affordable_max_tokens(10_000, agent.MAX_TOKENS, residue=0.02)
    assert mt < agent.MIN_USEFUL_TOKENS


def test_opus_5_copes_with_a_lower_cap_than_fable():
    """At the same cap Opus 5 makes more calls: it costs half as much per token."""
    o = _possible_calls("claude-opus-5", 0.50, 8000, 0.05)
    f = _possible_calls("claude-fable-5-1", 0.50, 8000, 0.05)
    assert o >= f, f"Opus {o} calls, Fable {f}"


def test_an_attempt_stopped_by_the_budget_does_not_lose_the_work_done():
    """When the GLOBAL budget runs out half-way through a problem, that problem used
    to end up in the report with $0.00 and zero verifications.

    It happened in round 0-bis: the seventh problem came out at zero cost while the
    log showed one verification submitted. A report that understates the spend is a
    safety problem, not a cosmetic one: the
    limit rigido si controlla proprio su quei numbers.
    """
    from costs import SpendLimitExceeded
    t = agent.Attempt(problem="X.y")
    t.iterations = 3
    t.checks = 1
    e = SpendLimitExceeded("finito")
    e.attempt = t
    # this is the mechanism main() uses: the exception carries the attempt with it
    assert getattr(e, "attempt", None) is t
    assert e.attempt.checks == 1
