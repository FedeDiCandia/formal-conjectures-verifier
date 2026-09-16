"""
Cost arithmetic and the spending limit.

The numbers come from the `usage` fields the API returns with EVERY response: they
are not estimates, they are the tokens actually billed.

The limit is enforced at TWO moments:

  * after the fact, by summing what has been spent;
  * beforehand, BEFORE every call: the exact number of tokens that will enter the
    request is counted (with the count endpoint, which is free) and the MAXIMUM
    possible cost of that call is computed. If it does not fit in what is left, the
    call does not start.

The second check is what makes the limit genuinely hard: without it, a single long
response could overshoot considerably before anyone noticed.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Prices:
    """Dollars per MILLION tokens."""
    input: float
    output: float
    cache_write_5m: float
    cache_write_1h: float
    cache_read: float


#: Prices in dollars per million tokens, VERIFIED against the official page
#: <https://platform.claude.com/docs/en/about-claude/pricing> on 11 September 2026.
#:
#: They are kept in absolute form rather than as multipliers because the
#: multipliers are NOT universal: a cache read costs 0.1x the input price on every
#: model except Fable 5.1 and Mythos 5.1, where it costs 0.025x. With a single
#: multiplier, Fable 5.1's budget would be wrong by a factor of four on the entry
#: that weighs most in a long session.
#:
#: A note on comparing models: Fable 5.1 costs twice Opus 5 on input and on output,
#: but its cache reads cost HALF as much in absolute terms ($0.25 against $0.50).
#: On the token profile of a long attempt — MEASURED by Epoch AI: 36.9 million
#: tokens read from cache against 685 thousand on output — the real ratio is not 2x
#: but 1.45x.
PRICE_LIST: dict[str, Prices] = {
    "claude-opus-5":    Prices(input=5.00,  output=25.00, cache_write_5m=6.25,
                               cache_write_1h=10.00, cache_read=0.50),
    "claude-opus-4-8":  Prices(input=5.00,  output=25.00, cache_write_5m=6.25,
                               cache_write_1h=10.00, cache_read=0.50),
    "claude-sonnet-5":  Prices(input=2.00,  output=10.00, cache_write_5m=2.50,
                               cache_write_1h=4.00,  cache_read=0.20),
    "claude-haiku-4-5": Prices(input=1.00,  output=5.00,  cache_write_5m=1.25,
                               cache_write_1h=2.00,  cache_read=0.10),
    "claude-fable-5-1": Prices(input=10.00, output=50.00, cache_write_5m=12.50,
                               cache_write_1h=20.00, cache_read=0.25),
    "claude-fable-5":   Prices(input=10.00, output=50.00, cache_write_5m=12.50,
                               cache_write_1h=20.00, cache_read=1.00),
}


def prices(model: str) -> Prices:
    if model in PRICE_LIST:
        return PRICE_LIST[model]
    raise KeyError(
        f"Unknown prices for the model '{model}'. Add them to agent/costs.py before "
        f"using it: without prices the spending limit cannot be enforced, and it is "
        f"better to stop than to pretend. "
        f"Known models: {', '.join(PRICE_LIST)}")


@dataclass
class Usage:
    """Tokens consumed, summed over several calls."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    calls: int = 0

    def add(self, usage) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0

        # The API distinguishes 5-minute cache writes from 1-hour ones, which cost
        # twice as much. If the detail is absent (older responses, or other
        # providers), the total is used and counted as 5 minutes — the cheaper rate,
        # so the detailed field is preferred when present, to avoid UNDERestimating.
        detail = getattr(usage, "cache_creation", None)
        if detail is not None:
            self.cache_write_5m += getattr(detail, "ephemeral_5m_input_tokens", 0) or 0
            self.cache_write_1h += getattr(detail, "ephemeral_1h_input_tokens", 0) or 0
        else:
            self.cache_write_5m += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.calls += 1

    def cost(self, model: str) -> float:
        p = prices(model)
        return (self.input_tokens * p.input
                + self.output_tokens * p.output
                + self.cache_write_5m * p.cache_write_5m
                + self.cache_write_1h * p.cache_write_1h
                + self.cache_read * p.cache_read) / 1_000_000

    def summary(self, model: str) -> str:
        cache = f"cache written {self.cache_write_5m:,}"
        if self.cache_write_1h:
            cache += f" (+{self.cache_write_1h:,} at 1h)"
        return (f"{self.calls} calls | input {self.input_tokens:,} | {cache} | "
                f"cache read {self.cache_read:,} | output {self.output_tokens:,} | "
                f"cost ${self.cost(model):.4f}")


class SpendLimitExceeded(RuntimeError):
    """Raised when the budget no longer suffices. It stops everything."""


@dataclass
class Budget:
    dollar_limit: float
    model: str
    usage: Usage = field(default_factory=Usage)
    per_problem: dict[str, Usage] = field(default_factory=dict)

    @property
    def prices(self) -> Prices:
        return prices(self.model)

    @property
    def spent(self) -> float:
        return self.usage.cost(self.model)

    @property
    def residue(self) -> float:
        return max(0.0, self.dollar_limit - self.spent)

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.dollar_limit

    def record(self, usage, problem: str = "") -> None:
        self.usage.add(usage)
        if problem:
            self.per_problem.setdefault(problem, Usage()).add(usage)

    # --- the check beforehand, which is what makes the limit hard ----------

    def max_possible_cost(self, input_tokens: int, max_tokens: int) -> float:
        """The worst-case cost a call can have.

        Genuinely worst-case:
          * every input token is counted at the cache-WRITE rate, the dearest of the
            three possibilities (1.25x the input price). In practice some of it will
            be read from the cache and cost ten times less, but no bets are placed
            here;
          * the output is counted as though the model filled all the room
            `max_tokens` allows it.
        """
        p = self.prices
        return (input_tokens * p.cache_write_5m + max_tokens * p.output) / 1_000_000

    def check_before_calling(self, input_tokens: int, max_tokens: int) -> None:
        """To be called BEFORE every request. Raises if it does not fit."""
        if self.exhausted:
            raise SpendLimitExceeded(
                f"Spending limit reached: ${self.spent:.4f} of "
                f"${self.dollar_limit:.2f}. Stopping.")
        worst = self.max_possible_cost(input_tokens, max_tokens)
        if worst > self.residue:
            raise SpendLimitExceeded(
                f"Not starting: this call could cost up to ${worst:.4f} "
                f"({input_tokens:,} input tokens, up to {max_tokens:,} on output) "
                f"but only ${self.residue:.4f} is left "
                f"(${self.spent:.4f} spent of ${self.dollar_limit:.2f}).")

    def affordable_max_tokens(self, input_tokens: int, cap: int,
                               residue: float | None = None) -> int:
        """How many output tokens can still be afforded.

        This is for reducing `max_tokens` instead of stopping, when what is left is
        little but not nothing. `residue` allows a tighter limit than the global one
        to be passed in — for instance a single problem's spending cap.
        """
        p = self.prices
        available = self.residue if residue is None else min(self.residue, residue)
        input_cost = input_tokens * p.cache_write_5m / 1_000_000
        leftover = available - input_cost
        if leftover <= 0:
            return 0
        return min(cap, int(leftover * 1_000_000 / p.output))

    def status_line(self) -> str:
        pct = 100 * self.spent / self.dollar_limit if self.dollar_limit else 0
        return f"[spend ${self.spent:.4f} / ${self.dollar_limit:.2f}  ({pct:.0f}%)]"
