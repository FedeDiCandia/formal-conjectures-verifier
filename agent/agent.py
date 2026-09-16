"""
A minimal agent that tries to prove a problem from the archive.

HOW IT WORKS
------------
It is a simple loop:

  1. the statement to prove and the rules are sent to the model;
  2. the model answers, possibly asking to use a tool;
  3. the tool is run and its result is handed back;
  4. this repeats until the model stops asking for tools, or `lean_check`
     accepts a proof, or the money or the attempts run out.

There are three tools available (see agent/tools.py):
  * `lean_explore` — compiles a scratch Lean file and returns every message;
  * `lean_check`   — submits a Lean file to the verifier;
  * `run_python`   — runs isolated Python code, with no network and a timeout.

THE SPENDING LIMIT
------------------
It is a HARD limit, computed from the `usage` fields the API returns with every
response — so from the tokens actually billed, not from an estimate. Before each
call the balance is checked: if it is exhausted, the agent stops and says so.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
import httpx2   # the SDK's transport: its mid-response errors do not become APIError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "agent"))

import config as verifier_config          # noqa: E402
from index import ProblemIndex, Problem       # noqa: E402
from costs import Budget, SpendLimitExceeded, Usage   # noqa: E402

#: The maximum room allowed for one response. It has to be high because extended
#: reasoning is counted inside it; the budget check reduces it when necessary.
MAX_TOKENS = 32_000

#: Below this threshold a response cannot be useful even for saying something
#: short: then, and only then, the attempt stops.
#:
#: WHY 2000 AND NOT 6000. The budget check reduces `max_tokens` to what fits in
#: what is left, and gives up when that number falls below this threshold. With
#: 6000 and Fable 5.1's prices ($50 per million on output) every call needed $0.30
#: of headroom on top of the input cost: a $0.50 per-problem cap allowed ONE call,
#: and two problems out of eleven got ZERO. It was not the model giving up, it was
#: our accountant. With 2000 the threshold costs $0.10 and a low cap stays usable.
#:
#: The limit stays HARD: no call starts if its maximum possible cost exceeds what
#: is left. What changes is only where the line falls between "shorten the answer"
#: and "stop".
MIN_USEFUL_TOKENS = 2_000

#: Below this threshold the response is so cramped that it is worth noting in the
#: log: it makes it possible to tell, reading an attempt back, whether the model
#: stopped because it had run out of ideas or out of room.
TIGHT_TOKENS = 8_000

#: How many consecutive network interruptions are tolerated on one problem before
#: closing it. On 12 September a "Connection reset by peer" mid-response stopped a
#: whole run at the third problem: the error came from httpx2, which the SDK does
#: not translate into `anthropic.APIError`, so the main loop's `try` did not catch
#: it.
MAX_CONSECUTIVE_NETWORK_ERRORS = 3

#: The exceptions that mean a dropped connection rather than an API response.
NETWORK_ERRORS = (anthropic.APIConnectionError, anthropic.APITimeoutError,
                  httpx2.TransportError)


class _WorstCaseUsage:
    """A fake `usage` that costs exactly `Budget.max_possible_cost`.

    It is needed when a response never arrives: its real cost is unknown, but the
    API may have billed part of it. Charging the worst case keeps the limit hard:
    the spend recorded can come out higher than the real one, never lower.
    """
    def __init__(self, input_tokens: int, max_tokens: int):
        self.input_tokens = 0
        self.output_tokens = max_tokens
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = input_tokens
        self.cache_creation = None
from hide import file_without_proofs, check_it_is_hidden  # noqa: E402
import tools                              # noqa: E402
import awake                                 # noqa: E402


DEFAULT_MODEL = "claude-opus-5"


def load_env() -> None:
    """Read the project's `.env` file and put its variables in the environment.

    This is for the API key. The file is excluded from git (see .gitignore), so the
    key cannot end up in a commit by accident. Variables already present in the
    environment take precedence and are not overwritten.
    """
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# ---------------------------------------------------------------------------
# The system text (the fixed instructions). It has to be kept STABLE between
# calls: it is the part that gets cached, and any different byte would invalidate
# the cache and make everything cost full price.
# ---------------------------------------------------------------------------

INSTRUCTIONS = """You are working on the `formal-conjectures` benchmark (Google DeepMind), \
proving theorems in Lean 4 with Mathlib.

You will be given one theorem to prove. Your answer is judged by a program, not \
by a person, so the rules below are absolute.

# What you must produce

A single, self-contained Lean 4 file that:

1. Starts with `import {UTILITY_MODULE}` (you may add `import Mathlib...` \
lines if you need something specific).
2. **Does NOT import the module of the problem itself** — that module already \
declares the theorem, and importing it makes the file fail to compile.
3. Re-declares, verbatim, every auxiliary definition the statement depends on \
that lives in the problem's own file (`def`, `abbrev`, `structure`, `instance`, \
notation, `open` commands...). Copy them character for character. If you change \
one, even in a way that looks equivalent, you are proving a different theorem \
and will be rejected.
4. Declares the target theorem with **exactly** the original name (namespace \
included) and **exactly** the original statement, followed by a complete proof.

# How the judge works

The judge is `comparator`, written by the Lean FRO. It compiles your file, \
exports it, and:

- compares the **elaborated syntax tree** of your statement with the original's. \
The comparison is structural, not up to definitional unfolding: stating \
`2 + 2 = 5 - 1` instead of `2 + 2 = 4` is REJECTED even though Lean considers \
them equal. Reproduce the statement exactly as given.
- checks every constant your statement mentions is identical to the archive's.
- checks the axioms your proof depends on. Only `propext`, `Classical.choice` \
and `Quot.sound` are permitted.
- replays the whole proof term through the Lean kernel.

Therefore the following are all automatic rejections, with no partial credit:

- `sorry` or `admit` anywhere in the file (leaves the axiom `sorryAx`);
- a new `axiom` declaration;
- `native_decide` (leaves the axiom `Lean.ofReduceBool` — use `decide` instead, \
which the kernel checks);
- weakening or altering the statement in any way;
- redefining any archive definition differently;
- `set_option debug.skipKernelTC`, `#eval`, `macro`, `elab`, `implemented_by`, \
or any other construct that runs code or disables checks.

Helper lemmas of your own are welcome — declare them before the theorem, with \
fresh names, and prove them properly.

# How to work

You have three tools. Using the right one matters:

**`lean_explore` — to understand.** Compiles a scratch file and returns every \
Lean message, untruncated. Use it to look things up instead of guessing:

    #print Nat.Perfect              -- the actual definition
    #print Selfridge.IsSelfridge    -- a structure's fields and constructor
    #check @Finset.sum_congr        -- the exact type, implicits included
    example : GOAL := by exact?     -- search Mathlib for a closing lemma
    example : GOAL := by apply?     -- same, by application

You may `import` the problem's own module here (you may not in `lean_check`), \
so you can inspect its definitions directly. Errors come back complete, with \
the goal state. About 8-10 seconds. This is not a judgment and costs you \
nothing but time.

**`lean_check` — to submit.** The only judgment that counts. About 30 seconds. \
Use it when you believe you have a proof, not to look something up: it will \
just tell you the theorem is missing.

**`run_python` — to compute.** Searching for a witness or a counterexample, \
checking a hypothesis on small cases, computing a constant. Do not do \
arithmetic in your head when you can compute it. `numpy`, `sympy` and `numba` \
are installed: `sympy.isprime`, `factorint`, `nextprime`, `divisors`, `totient` \
are there, so use them rather than writing your own. **The working directory \
persists between calls**: write a checkpoint file and a later call can resume \
it. Each call has a time limit, so for a long search proceed in blocks, saving \
the position reached — this is how you can search far further than a single \
call allows.

# How much room you have

This is a long attempt, not a quick one: you may use **many dozens of \
iterations**. Every tool result tells you how much of the per-problem budget \
is left and which iteration you are on. Spend the early iterations \
understanding the problem and the definitions, and do not rush a submission. \
If the conversation gets long, older tool results are shortened automatically \
to make room; ask again for anything you still need.

A disproof counts as much as a proof. If the statement is of the form \
`True ↔ P` (the archive asserting the answer is yes), and your computation \
finds a counterexample to `P`, say so clearly and explain what you found: that \
is a result, and it is checked separately.

Practical advice:

- Look it up before you guess. One `lean_explore` with `#check` and `exact?` is \
cheaper than three failed proof attempts, in both time and money.
- Read the error messages carefully; they tell you exactly what failed, and you \
now get them in full.
- If a proof strategy fails twice in a row, change strategy rather than \
patching it.
- You have no internet access. Rely on what you know about Mathlib, and use \
`lean_explore` to correct yourself.
- Stop when `lean_check` reports ACCEPTED. If you become convinced the problem \
is beyond you, say so plainly instead of submitting a proof you know is broken."""


#: The "insistent" variant of the instructions.
#:
#: WHY IT EXISTS. On the first round of open problems the agent failed ten times
#: out of ten in the same way: it explored, computed, concluded it could not manage
#: and stopped — spending on average $0.23 of a $2 cap and submitting NOT ONE
#: candidate to `lean_check`. The current instructions offer it that way out: "if
#: you become convinced the problem is beyond you, say so plainly". Whoever
#: measured the OEIS Open benchmark had agents that reached the cap 70% of the
#: time.
#:
#: This variant removes the invitation to give up and says the budget is there to
#: be spent. It exists to answer one precise question: does the zero out of ten
#: come from the difficulty of the problems or from the way the agent gives up?
INSISTENT_INSTRUCTIONS = INSTRUCTIONS.replace(
    """- Stop when `lean_check` reports ACCEPTED. If you become convinced the problem \
is beyond you, say so plainly instead of submitting a proof you know is broken.""",
    """- **Stop only when `lean_check` reports ACCEPTED, or when your budget is \
gone.** The per-problem budget exists to be spent: every tool result tells you \
how much is left.
- **When a route fails, change route — do not stop.** Prove a weaker statement \
first and build on it. Prove a special case (a fixed small parameter, one \
congruence class, one family) and state it as a lemma. Search by computation for \
a counterexample. Look up a different corner of Mathlib. Try the negation.
- **Deciding that a problem is beyond reach is not your call while budget \
remains.** A helper lemma that compiles, or a special case proved, is worth more \
than an early stop — and by the time half the budget is spent you should already \
have sent at least one candidate to `lean_check`, even an imperfect one, because \
its error messages are the most informative thing you can buy.
- Never submit a proof you know is broken, and never claim to have proved \
something you have not. But do not stop while you still have room to try another \
route.""")


def chosen_instructions(variant: str) -> str:
    """The system text, according to the variant asked for."""
    if variant == "insistent":
        base = INSISTENT_INSTRUCTIONS
    elif variant == "current":
        base = INSTRUCTIONS
    else:
        raise SystemExit(f"unknown instruction variant: {variant!r} "
                         f"(they are 'current' and 'insistent')")
    return base.replace("{UTILITY_MODULE}", verifier_config.utility_module())


def _verification_kind(report: str, accepted: bool) -> tuple[str, str]:
    """Return (the failed check, the kind), reading verify.py's report."""
    if accepted:
        return "", "accepted"
    failed = ""
    for line in report.split("\n"):
        if line.strip().startswith("[FAILED]"):
            failed = line.split("]", 1)[1].split("—")[0].strip()
            break
    text = report.lower()
    if "does not declare" in text or "not found in solution" in text:
        return failed, "exploration"
    if "does not compile" in text or "compiles without errors" in failed:
        return failed, "technical_error"
    if "axiom" in failed:
        return failed, "hole_or_axiom"
    if "type identical" in failed or "archive definitions" in failed:
        return failed, "wrong_statement"
    return failed, "technical_error"


def instructions() -> str:
    """The instructions, with THIS snapshot's utility module name.

    It changes between versions of the archive: `FormalConjectures.Util.ProblemImports`
    in the bench-v1 tag, `FormalConjecturesUtil` on the main branch. Hard-coding it
    made every attempt on the second snapshot fail.
    """
    return INSTRUCTIONS.replace("{UTILITY_MODULE}", verifier_config.utility_module())


def problem_message(problem: Problem, file_text: str) -> str:
    description = (problem.docstring or "").strip()
    return f"""# The problem

**Theorem to prove:** `{problem.theorem}`
**Module it lives in:** `{problem.module}` (do NOT import this)
**Category:** {problem.category}

{"**Informal statement:** " + description if description else ""}

Below is the problem's source file, with every proof replaced by `sorry`.
Everything else — imports, `open` commands, definitions, notation — is exactly
as it appears in the archive. Your file must reproduce whatever the statement
depends on.

```lean
{file_text}
```

Produce a complete Lean file proving `{problem.theorem}`, and check it with
`lean_check`."""


# ---------------------------------------------------------------------------
# The result of one attempt
# ---------------------------------------------------------------------------

@dataclass
class LeanCheck:
    """One call to lean_check, with its measured outcome."""
    chars: int
    result: str                  # ACCEPTED / REJECTED / ERROR / TIMEOUT
    failed_check: str            # which check did not pass
    seconds: float               # LOCAL computation time (Lean), not the API's
    #: how the attempt is classified. A declared rule:
    #:   exploration      -> the file did not declare the requested theorem
    #:                       (the model was inspecting, not attempting)
    #:   technical_error  -> the file does not compile
    #:   hole_or_axiom    -> it compiles but the proof has a hole
    #:   wrong_statement  -> it compiles but proves something else
    #:   accepted         -> passed
    kind: str


@dataclass
class Iteration:
    """One pass of the loop: one API call plus the tools used."""
    number: int
    input_tokens: int = 0
    output_tokens: int = 0
    cache_written: int = 0
    cache_read: int = 0
    cost: float = 0.0
    api_seconds: float = 0.0
    lean_seconds: float = 0.0
    python_seconds: float = 0.0
    checks: list = field(default_factory=list)     # list[LeanCheck]
    python_runs: int = 0
    explorations: int = 0
    exploration_seconds: float = 0.0
    reasoning: str = ""


@dataclass
class Attempt:
    problem: str
    solved: bool = False
    reason: str = ""
    iterations: int = 0
    checks: int = 0
    explorations: int = 0
    python_runs: int = 0
    seconds: float = 0.0
    usage: Usage = field(default_factory=Usage)
    solution: str = ""
    transcript: list = field(default_factory=list)
    #: measurements per iteration
    detail: list = field(default_factory=list)      # list[Iteration]
    api_seconds: float = 0.0
    lean_seconds: float = 0.0
    python_seconds: float = 0.0
    #: how many times the conversation was shortened to make room
    compactions: int = 0
    #: calls interrupted by the network, charged at the maximum possible cost
    network_interruptions: int = 0
    #: the total of those charges: it sits in the global budget, not in `usage`
    network_charge: float = 0.0
    #: classification of the failure, per the rule declared below
    cause: str = ""

    @property
    def verifications_by_kind(self) -> dict:
        count: dict = {}
        for it in self.detail:
            for v in it.checks:
                count[v.kind] = count.get(v.kind, 0) + 1
        return count

    def classify_failure(self) -> str:
        """Tell a MATHEMATICAL failure from a SYSTEM one.

        A declared rule, not a feeling:
          * if there was no real attempt at all (every verification was an
            exploration), the failure is SYSTEMIC: the agent never got as far as
            trying, it spent everything working out the tools and Mathlib's API;
          * if the real attempts ended only in compilation errors, it is TECHNICAL:
            it knew what to do but not how to write it in Lean;
          * if at least one attempt compiled and failed for a hole or for the wrong
            statement, it is MATHEMATICAL: the proof was not there.
        """
        if self.solved:
            return "solved"
        n = self.verifications_by_kind
        real = n.get("technical_error", 0) + n.get("hole_or_axiom", 0) + \
            n.get("wrong_statement", 0)
        if real == 0:
            return "systemic: no real attempt, everything spent exploring"
        if n.get("hole_or_axiom", 0) or n.get("wrong_statement", 0):
            return "mathematical: it compiled but the proof was not there"
        return "technical: it knew what to prove but could not write it in Lean"


#: Above this input-token threshold the conversation is compacted. It is needed
#: for long attempts: whoever measured the OEIS Open benchmark spent $50 per
#: problem, that is of the order of 200 iterations. Without compaction the
#: conversation outgrows the model's window and the attempt dies of exhausted
#: context rather than of exhausted ideas.
COMPACTION_THRESHOLD = 120_000

#: How many trailing messages stay intact when compacting. The model has to see
#: its recent work in full; the older work only serves as a trace.
MESSAGES_UNTOUCHED = 8

#: How many characters the older tool results are reduced to.
OLD_RESULTS_QUEUE = 600

_CUT_MARK = "\n… [result shortened to make room in the context; "\
            "ask again if you still need it]"


def compact_conversation(messages: list, *, intact: int = MESSAGES_UNTOUCHED,
                         tail: int = OLD_RESULTS_QUEUE) -> int:
    """Shorten the older tool results. Return how many were shortened.

    The first message (the problem's statement) and the last `intact` ones are never
    touched. Only `tool_result` blocks are shortened, because they are the bulk: one
    Lean error can reach 40,000 characters, and over two hundred iterations that is
    millions. The code the model wrote (the `tool_use` blocks) is kept whole: it is
    its work, and rebuilding it would cost more than it occupies.
    """
    if len(messages) <= intact + 1:
        return 0
    cut = 0
    for msg in messages[1:len(messages) - intact]:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            text = block.get("content")
            if not isinstance(text, str) or len(text) <= tail:
                continue
            if text.endswith(_CUT_MARK):
                continue
            block["content"] = text[:tail] + _CUT_MARK
            cut += 1
    return cut


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

class _Tee:
    """Writes to two places at once: the screen and a file.

    It is needed because a run launched in the background shows nothing until it
    finishes, and whoever is watching has no way of knowing whether it is getting
    anywhere. With the log on a file one can `tail -f` and watch the lines arrive.

    It does not rely on `print` redirected with `>`, because that is the launcher's
    choice: the log has to be there always, including when the output goes into a
    pipe.
    """

    def __init__(self, stream, path: Path):
        self.stream = stream
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(path, "a", encoding="utf-8", buffering=1)  # line by line

    def write(self, text):
        self.stream.write(text)
        self.file.write(text)
        return len(text)

    def flush(self):
        self.stream.flush()
        self.file.flush()

    def isatty(self):
        return getattr(self.stream, "isatty", lambda: False)()



def solve(problem: Problem, index: ProblemIndex, *, client, model: str,
            budget: Budget, problem_cap: float, max_iterations: int = 30,
            effort: str = "high", lean_timeout: int | None = None,
            verbose: bool = True, instruction_variant: str = "current") -> Attempt:

    start = time.time()
    t = Attempt(problem=problem.theorem)

    file_text = file_without_proofs(problem, index)
    try:
        # The exercise has to be honest: if the proof has not been hidden, the
        # problem is SKIPPED. Earlier this aborted the whole run, and an
        # eleven-problem calibration stopped at the third.
        check_it_is_hidden(problem, file_text)
    except AssertionError as e:
        t.reason = f"skipped: {e}"
        t.cause = "systemic: the archive's proof cannot be hidden"
        t.seconds = time.time() - start
        return t

    api_tools = [tools.SCHEMA_LEAN_EXPLORE, tools.SCHEMA_LEAN_CHECK,
                     tools.SCHEMA_RUN_PYTHON]

    # One working directory per problem, surviving between calls: this is what lets
    # a multi-step search save a checkpoint. The name is sanitised because theorem
    # names contain dots and awkward characters.
    clean_name = re.sub(r"[^A-Za-z0-9_.-]", "_", problem.theorem)[:80]
    work_dir = verifier_config.ROOT / "runs" / "job" / clean_name
    work_dir.mkdir(parents=True, exist_ok=True)
    messages = [{"role": "user", "content": problem_message(problem, file_text)}]

    spent_at_start = budget.spent
    consecutive_network_errors = 0
    #: the precautionary charges for interrupted calls: they count against the
    #: global budget, not against this problem's cap
    network_charges_here = 0.0

    def show(*a):
        if verbose:
            print(*a, flush=True)

    for iteration in range(1, max_iterations + 1):
        t.iterations = iteration

        # --- the wallet check, BEFORE spending ---------------------------
        # Looking at what has been spent is not enough: what matters is how much the
        # next call can cost. Counting the tokens is exact and free, so the maximum
        # cost is known in advance.
        system = [{"type": "text", "text": chosen_instructions(instruction_variant),
                    "cache_control": {"type": "ephemeral"}}]
        count = client.messages.count_tokens(
            model=model, system=system, tools=api_tools, messages=messages)
        input_tokens = count.input_tokens

        # --- if the context has grown too large, shorten the past
        if input_tokens > COMPACTION_THRESHOLD:
            cut = compact_conversation(messages)
            if cut:
                count = client.messages.count_tokens(
                    model=model, system=system, tools=api_tools,
                    messages=messages)
                show(f"     [context compacted: {cut} results shortened, "
                     f"{input_tokens:,} -> {count.input_tokens:,} tokens]")
                input_tokens = count.input_tokens
                t.compactions += 1

        spent_here = budget.spent - spent_at_start - network_charges_here
        problem_residue = problem_cap - spent_here
        max_tokens = budget.affordable_max_tokens(
            input_tokens, MAX_TOKENS, residue=problem_residue)

        if max_tokens < MIN_USEFUL_TOKENS:
            worst = budget.max_possible_cost(input_tokens, MIN_USEFUL_TOKENS)
            reason = (f"not enough budget to continue: {input_tokens:,} input tokens, "
                      f"the next call would cost up to ${worst:.4f} but "
                      f"${min(budget.residue, problem_residue):.4f} is left "
                      f"(${budget.residue:.4f} globally, ${problem_residue:.4f} on this "
                      f"problem)")
            if budget.residue <= worst:
                # The attempt has to be attached to the exception: without it, the
                # work done on THIS problem vanishes from the report — cost,
                # iterations and verifications included. It really happened: in round
                # 0-bis the seventh problem came out with $0.00 and zero
                # verifications while the log showed one verification submitted and
                # half a dollar spent. A report that understates the spend is a
                # safety problem, not a cosmetic one.
                t.reason = reason
                t.cause = t.classify_failure()
                t.seconds = time.time() - start
                e = SpendLimitExceeded(reason)
                e.attempt = t
                raise e
            t.reason = reason                        # only this problem stops
            break

        # belt and braces: if even that does not fit, it does not start
        budget.check_before_calling(input_tokens, max_tokens)

        tight = ("  ← CRAMPED: the response is limited by the budget, not by the "
                 "model" if max_tokens < TIGHT_TOKENS else "")
        show(f"\n  ── iteration {iteration}  {budget.status_line()}  "
               f"[{input_tokens:,} input tokens, up to {max_tokens:,} on output, "
               f"at most ${budget.max_possible_cost(input_tokens, max_tokens):.4f}]"
               f"{tight}")

        it = Iteration(number=iteration)
        t0_api = time.time()
        try:
            with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": effort},
                tools=api_tools,
                messages=messages,
                cache_control={"type": "ephemeral"},   # cache the conversation too
            ) as stream:
                answer = stream.get_final_message()
        except NETWORK_ERRORS as e:
            # The conversation does not change: the next iteration repeats the same
            # call, after re-checking the budget with the charge made here.
            it.api_seconds = time.time() - t0_api
            worst = _WorstCaseUsage(input_tokens, max_tokens)
            before = budget.spent
            # The worst case goes against the GLOBAL budget, which therefore stays
            # hard, but not against the problem's cap nor its cost. The first version
            # charged it there too: a $0.84 interruption consumed a $1 cap on its
            # own, and on the night of 13 September six attempts out of twelve ended
            # that way, saying nothing about the agent.
            budget.record(worst)
            it.cost = budget.spent - before
            t.network_charge += it.cost
            network_charges_here += it.cost
            t.network_interruptions += 1
            t.detail.append(it)
            t.api_seconds += it.api_seconds
            consecutive_network_errors += 1
            show(f"     !! connection interrupted ({type(e).__name__}: {e}); ${it.cost:.4f} "
                 f"charged to the global budget (the worst case), not to the problem's cap")
            if consecutive_network_errors >= MAX_CONSECUTIVE_NETWORK_ERRORS:
                t.reason = (f"repeated network error: {consecutive_network_errors} calls "
                            f"interrupted in a row ({type(e).__name__})")
                break
            time.sleep(10 * consecutive_network_errors)
            continue
        consecutive_network_errors = 0
        it.api_seconds = time.time() - t0_api

        before = budget.spent
        budget.record(answer.usage, problem.theorem)
        t.usage.add(answer.usage)
        u = answer.usage
        it.input_tokens = getattr(u, "input_tokens", 0) or 0
        it.output_tokens = getattr(u, "output_tokens", 0) or 0
        it.cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
        it.cache_written = getattr(u, "cache_creation_input_tokens", 0) or 0
        it.cost = budget.spent - before

        if answer.stop_reason == "refusal":
            t.reason = "the model refused the request"
            break

        # show the reasoning and the text
        for block in answer.content:
            if block.type == "thinking" and getattr(block, "thinking", ""):
                show(f"     [reasoning] {block.thinking.strip()[:400]}")
            elif block.type == "text" and block.text.strip():
                show(f"     {block.text.strip()[:600]}")
        it.reasoning = " ".join(
            b.thinking for b in answer.content
            if b.type == "thinking" and getattr(b, "thinking", ""))[:4000]

        calls = [b for b in answer.content if b.type == "tool_use"]
        messages.append({"role": "assistant", "content": answer.content})

        if not calls:
            t.reason = "the model stopped using the tools without an accepted proof"
            text = " ".join(b.text for b in answer.content if b.type == "text")
            t.transcript.append({"kind": "end", "text": text})
            t.detail.append(it)
            t.api_seconds += it.api_seconds
            break

        results = []
        accepted = False
        for call in calls:
            if call.name == "lean_explore":
                t.explorations += 1
                it.explorations += 1
                code = call.input.get("lean_code", "")
                show(f"     -> lean_explore ({len(code)} chars)...")
                t0 = time.time()
                output = tools.run_lean_explore(
                    code, timeout=lean_timeout or 240)
                duration = time.time() - t0
                it.exploration_seconds += duration
                first_line = output.splitlines()[0] if output else "(empty)"
                show(f"        {first_line}  [{duration:.0f}s]")
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                  "content": output})
            elif call.name == "lean_check":
                t.checks += 1
                code = call.input.get("lean_code", "")
                show(f"     -> lean_check ({len(code)} chars)...")
                t0 = time.time()
                report, ok = tools.run_lean_check(
                    problem.theorem, code, timeout=lean_timeout)
                duration = time.time() - t0
                it.lean_seconds += duration
                failed, kind = _verification_kind(report, ok)
                it.checks.append(LeanCheck(
                    chars=len(code), result=report.split("\n")[0].replace("VERDICT: ", ""),
                    failed_check=failed, seconds=duration, kind=kind))
                headline = report.split("\n")[0]
                show(f"        {headline}  [{kind}, {duration:.0f}s]")
                if ok:
                    accepted = True
                    t.solution = code
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                  "content": report})
            elif call.name == "run_python":
                t.python_runs += 1
                code = call.input.get("code", "")
                show(f"     -> run_python ({len(code)} chars)...")
                t0 = time.time()
                output = tools.run_python_tool(
                    code, folder=work_dir)
                it.python_seconds += time.time() - t0
                it.python_runs += 1
                show(f"        {output.strip()[:200]}")
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                  "content": output})
            else:
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                  "content": f"Unknown tool: {call.name}",
                                  "is_error": True})

        # The model paces itself better if it knows what is left: whoever measured
        # OEIS Open gave the model a tool specifically for this.
        spent_here = budget.spent - spent_at_start - network_charges_here
        results.append({
            "type": "text",
            "text": (f"[budget: ${spent_here:.2f} spent of the ${problem_cap:.2f} "
                     f"available for this problem; iteration {iteration} "
                     f"of {max_iterations}]")})
        messages.append({"role": "user", "content": results})
        t.detail.append(it)
        t.api_seconds += it.api_seconds
        t.lean_seconds += it.lean_seconds + it.exploration_seconds
        t.python_seconds += it.python_seconds

        if accepted:
            t.solved = True
            t.reason = "proof accepted by the verifier"
            break
    else:
        t.reason = f"ran out of the {max_iterations} iterations available"

    t.seconds = time.time() - start
    t.cause = t.classify_failure()
    return t


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def write_report(path: Path, *, args, cap: float, budget: Budget,
                 attempts: list, full: bool) -> None:
    """Write the JSON report. `full` is false until the run has finished."""
    path.write_text(json.dumps({
        "model": args.model, "effort": args.effort,
        "instructions": args.instructions,
        "problem_cap": cap,
        "budget": args.budget, "spent": budget.spent,
        "full": full,
        "total_usage": budget.usage.__dict__,
        "attempts": [{
            "problem": t.problem, "solved": t.solved, "reason": t.reason,
            "cause": t.cause,
            "iterations": t.iterations, "checks": t.checks,
            "explorations": t.explorations,
            "python_runs": t.python_runs,
            "network_interruptions": t.network_interruptions,
            "precautionary_network_charge": t.network_charge,
            "total_seconds": t.seconds,
            "api_seconds": t.api_seconds,
            "lean_seconds": t.lean_seconds,
            "python_seconds": t.python_seconds,
            "cost": t.usage.cost(args.model), "usage": t.usage.__dict__,
            "verifications_by_kind": t.verifications_by_kind,
            "iteration_detail": [{
                "number": it.number, "cost": it.cost,
                "input_tokens": it.input_tokens, "output_tokens": it.output_tokens,
                "cache_written": it.cache_written, "cache_read": it.cache_read,
                "api_seconds": it.api_seconds, "lean_seconds": it.lean_seconds,
                "python_seconds": it.python_seconds,
                "python_runs": it.python_runs,
                "explorations": it.explorations,
                "exploration_seconds": it.exploration_seconds,
                "checks": [{
                    "chars": v.chars, "result": v.result,
                    "failed_check": v.failed_check,
                    "seconds": v.seconds, "kind": v.kind,
                } for v in it.checks],
                "reasoning": it.reasoning,
            } for it in t.detail],
            "solution": t.solution,
        } for t in attempts],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Try to prove one or more of the archive's problems with the Anthropic API.")
    ap.add_argument("problems", nargs="*", help="names of the theorems to attempt")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"the model to use (default: {DEFAULT_MODEL})")
    ap.add_argument("--budget", type=float, default=5.0,
                    help="HARD spending limit in dollars for the whole run (default: 5)")
    ap.add_argument("--problem-cap", type=float, default=None,
                    help="maximum spend per problem (default: the budget divided by the number of problems)")
    ap.add_argument("--max-iterations", type=int, default=30)
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--lean-timeout", type=int, default=None)
    ap.add_argument("--report", default=None, help="where to save the JSON report")
    ap.add_argument("--instructions", default="current",
                    choices=["current", "insistent"],
                    help="which variant of the system prompt to use. "
                         "'insistent' removes the invitation to give up and says the "
                         "budget is there to be spent (see INSISTENT_INSTRUCTIONS)")
    ap.add_argument("--log", default=None,
                    help="where to write the line-by-line log (default: "
                         "runs/jobs/agent-<date>.log). It is what makes it possible to "
                         "follow the run with `tail -f` while it works.")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--no-awake", action="store_true",
                    help="do not start caffeinate and do not check mains power "
                         "(not recommended: see agent/awake.py)")
    args = ap.parse_args()

    # --- the log, before anything is printed
    log_path = Path(args.log) if args.log else (
        verifier_config.ROOT / "runs" / "jobs" /
        f"agent-{time.strftime('%Y%m%d-%H%M%S')}.log")
    sys.stdout = _Tee(sys.stdout, log_path)
    print(f"Log: {log_path}")
    print(f"  from another terminal:  tail -f {log_path}")

    load_env()

    if not args.problems:
        ap.error("name at least one theorem to attempt")

    environment_problems = verifier_config.check_installation()
    if environment_problems:
        print("Environment not ready:\n  - " + "\n  - ".join(environment_problems), file=sys.stderr)
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        print("The API key is missing.\n"
              f"Create the file {ROOT / '.env'} with one line in it:\n"
              "  ANTHROPIC_API_KEY=sk-ant-...\n"
              "(the file is already excluded from git, so the key can never be committed)",
              file=sys.stderr)
        return 2

    index = ProblemIndex.load()
    try:
        listing = [index.get(n) for n in args.problems]
    except KeyError as e:
        print(e, file=sys.stderr)
        return 2

    # --- the Mac has to stay awake: checked BEFORE spending a cent
    awake_process = None
    if not args.no_awake and sys.platform == "darwin":
        awake_process = awake.start_job(os.getpid())
        reasons = awake.check(awake_process)
        if reasons:
            awake_process.terminate()
            print("NOT STARTING: the Mac has to stay awake and on mains power for the "
                  "whole run.\n  - "
                  + "\n  - ".join(reasons)
                  + "\nKeep the lid open too: with the lid closed the Mac sleeps anyway. "
                    "To skip the check: --no-awake (not recommended).",
                  file=sys.stderr)
            return 2
        print("Keep-awake: caffeinate running, on mains power. Keep the lid open.")

    client = anthropic.Anthropic()
    budget = Budget(dollar_limit=args.budget, model=args.model)
    cap = args.problem_cap or (args.budget / len(listing))

    print(f"Model: {args.model} | effort: {args.effort} | "
          f"instructions: {args.instructions}")
    print(f"Total budget: ${args.budget:.2f}  (cap per problem: ${cap:.2f})")
    print(f"Problems: {len(listing)}")

    attempts: list[Attempt] = []

    def save(full: bool) -> None:
        # The report is rewritten after EVERY problem. On 12 September a network
        # error stopped a run at the third problem and, because the report was only
        # written at the end, the two attempts already finished vanished.
        if args.report:
            write_report(Path(args.report), args=args, cap=cap, budget=budget,
                            attempts=attempts, full=full)

    for i, p in enumerate(listing, 1):
        if awake_process is not None and not awake.on_mains_power():
            print(f"\n!! Unplugged from mains: stopping before {p.theorem}. "
                  f"The report holds the problems already finished.")
            break
        print(f"\n{'='*78}\n[{i}/{len(listing)}] {p.theorem}   ({p.category})\n{'='*78}")
        try:
            t = solve(p, index, client=client, model=args.model, budget=budget,
                        problem_cap=cap, max_iterations=args.max_iterations,
                        effort=args.effort, lean_timeout=args.lean_timeout,
                        verbose=not args.quiet,
                        instruction_variant=args.instructions)
        except SpendLimitExceeded as e:
            print(f"\n!! {e}")
            partial = getattr(e, "attempt", None)
            attempts.append(partial if partial is not None
                             else Attempt(problem=p.theorem, reason=str(e)))
            if partial is not None:
                print(f"     work done before stopping: "
                      f"{partial.iterations} iterations, {partial.checks} "
                      f"verifications, ${partial.usage.cost(args.model):.4f}")
            break
        except anthropic.APIError as e:
            print(f"\n!! Error from the API: {e}")
            attempts.append(Attempt(problem=p.theorem, reason=f"API error: {e}"))
            save(full=False)
            continue
        attempts.append(t)
        save(full=False)
        result = "SOLVED" if t.solved else "not solved"
        print(f"\n  => {result}: {t.reason}")
        print(f"     {t.iterations} iterations, {t.explorations} explorations, "
              f"{t.checks} Lean verifications, "
              f"{t.python_runs} Python runs, {t.seconds:.0f}s, "
              f"${t.usage.cost(args.model):.4f}")
        print(f"     time: {t.api_seconds:.0f}s waiting for the API, "
              f"{t.lean_seconds:.0f}s of Lean locally, "
              f"{t.python_seconds:.0f}s of Python locally")
        print(f"     kinds of verification: {t.verifications_by_kind or 'none'}")
        print(f"     cause: {t.cause}")

    # --- summary
    print(f"\n{'='*78}\nSUMMARY\n{'='*78}")
    solved = sum(1 for t in attempts if t.solved)
    for t in attempts:
        print(f"  [{'SOLVED    ' if t.solved else 'not solved'}] {t.problem}"
              f"   ${t.usage.cost(args.model):.4f}   {t.reason}")
    print(f"\n  Solved: {solved}/{len(attempts)}")
    print(f"  Total spend: ${budget.spent:.4f} of ${args.budget:.2f} available")
    print(f"  {budget.usage.summary(args.model)}")

    if args.report:
        save(full=True)
        print(f"\n  Report saved to {args.report}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
