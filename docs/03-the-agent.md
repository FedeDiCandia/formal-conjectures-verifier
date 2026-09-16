# The agent

## What it does

It takes a problem from the archive, hands it to an Anthropic model, and lets it
work until it produces a proof the verifier accepts, or until the attempts or the
money run out.

It is not a sophisticated system, and that is deliberate: its purpose is to
**exercise the verifier under realistic conditions**, not to solve conjectures.
Three parts are worth describing: the tools, the way the problem is handed over,
and the control of spending.

---

## The two tools

### `lean_check`

Takes a complete Lean file and passes it to `verifier/verify.py`. It returns the
verdict and, if the file was rejected, Lean's error messages.

It is the only judge: the model has no way of "persuading" anyone, it can only
make the file compile and verify. A verification takes about 30 seconds.

### `run_python`

Runs Python code in isolation. It is there because looking for a proof usually
means doing arithmetic: finding a counterexample, checking a hypothesis on small
cases, computing a constant. A model doing arithmetic in its head makes mistakes,
and in Lean a numerical mistake costs half an hour of useless attempts.

Isolation uses macOS `sandbox-exec`. Verified in practice:

| Test | Result |
|---|---|
| ordinary computation | works |
| standard library (`math`, `itertools`, …) | works |
| network connection | **blocked** (`URLError`) |
| writing outside the working directory | **blocked** (`PermissionError`) |
| reading the API key from the environment | **not present** |
| infinite loop | **killed** at the time limit |

There are no external packages (no `numpy`, no `sympy`) and every run starts from
nothing: a deliberately poor environment.

---

## How the problem is handed over

Exercising the agent needs problems that are **already solved** — otherwise a
failure could not be attributed to the agent rather than the problem. But a
solved problem has its answer written in the archive.

`agent/nascondi.py` takes the source file and replaces **every** proof with
`sorry`, producing exactly the file the problem would have if it were still open.
All proofs in the file are replaced, not only the target's: the neighbouring
lemmas are often the intermediate steps of the solution.

The cut is not textual: it uses the **exact declaration positions** Lean reports
in the index, and finds the `:=` separating statement from proof by counting
brackets (so that a `:=` inside `(n : ℕ := 3)` is not mistaken for the start of
the proof).

Finally `controlla_che_sia_nascosta` checks that the text of the original proof
does **not** appear in the material handed to the agent. If it leaked, the
exercise would measure nothing, and the code stops with an error.

---

## Controlling the spend

The limit is **hard** and computed from the `usage` fields the API returns with
every response: those are the tokens actually billed, not an estimate.

```
cost = (input        × input_price
      + cache_write  × input_price × 1.25
      + cache_read   × input_price × 0.10
      + output       × output_price) / 1_000_000
```

The balance is checked **before** every call: when it is exhausted the next call
does not start and the agent stops and says so. There is also a per-problem cap
(by default the budget divided by the number of problems), so that one stubborn
problem does not eat everyone else's share.

If the requested model is not in the price table, the program refuses to start:
better to stop than to enforce the wrong limit.

Two corrections came out of running it for real:

- **A network failure must not consume the per-problem cap.** An interrupted call
  is charged to the global budget at its worst case (it may have been billed),
  but the problem keeps its cap: otherwise a flaky connection turns into a
  fabricated "the model gave up".
- **The machine must stay awake.** A laptop that goes to sleep mid-run kills the
  connection and voids the attempts. `agent/veglia.py` refuses to start unless
  the machine is on mains power with `caffeinate` holding it awake.

---

## Choices about the API

Based on the current documentation, not on memory:

| Choice | Why |
|---|---|
| `thinking: {"type": "adaptive"}` | on Opus 5 reasoning is on by default; `budget_tokens` no longer exists and would give a 400 |
| `display: "summarized"` | shows a summary of the reasoning while it works. It costs nothing extra: reasoning is billed the same either way |
| `output_config: {"effort": …}` | how hard to think. Default `high`; `xhigh` and `max` cost more |
| `cache_control` on the system text **and** at the top level | the instructions are identical on every call and the conversation grows each round: without caching the whole history would be paid for again every time |
| streaming with `get_final_message()` | with a high `max_tokens`, a non-streaming request risks hitting the HTTP timeout |
| a manual loop rather than `tool_runner` | `usage` has to be read every round to enforce the spending limit, and the loop has to be interruptible |

The system text must stay **byte-for-byte identical** between calls: the cache
works by prefix, and a single different character would invalidate it and make
everything cost full price.

---

## What to expect

Not much. These are serious mathematical problems formalised in Lean, and an
agent with two tools and thirty iterations is not a research system. The exercise
answers more modest but necessary questions:

- does the whole loop work end to end?
- does the verifier give error messages a model can actually use?
- is the spending limit really enforced?
- does the agent try to cheat — with a `sorry`, with an axiom, by weakening the
  statement — and if it does, does the verifier stop it?

The last question is the interesting one.
