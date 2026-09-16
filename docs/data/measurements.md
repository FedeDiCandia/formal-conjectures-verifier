# Measurements taken

Every row declares its **provenance**. No estimated numbers in this file: only
things observed.

## M1 — API connection test
*Provenance: terminal output of 2026-09-10, not saved to a file.*

| quantity | value |
|---|---|
| model | claude-opus-5 |
| input tokens | 16 |
| output tokens | 16 |
| cost | $0.0005 |

Note: `max_tokens=16` was consumed entirely by reasoning (on Opus 5 adaptive
reasoning is on by default), so the textual answer came back empty. It is the
first experimental confirmation that reasoning consumes the `max_tokens` budget.

## M2 — Shakedown run on a trivial problem
*Provenance: terminal output of 2026-09-10, not saved to a file.*
*Problem: `JugglerConjecture.jugglerStep_36` (category `test`), proof hidden.*

| quantity | value |
|---|---|
| outcome | **SOLVED** on the first iteration |
| iterations | 1 |
| Lean verifications | 1 |
| Python runs | 0 |
| time | 68 s |
| cost | $0.0526 |
| input tokens | 2 |
| tokens written to cache | 3,090 |
| tokens read from cache | 0 |
| output tokens | 1,333 |
| effort | high |

## M3 — A $5 test, interrupted
*Provenance: the agent's run log, readable with `interno/scripts/analizza_log_agente.py`.*

Deliberately interrupted at $1.81 of $5.00 after finding a defect in `lean_check`
(it discarded Lean's informational messages) that was wasting the budget on
exploration.

## M4 — Cost of one local verification (no API spend)
*Provenance: runs of `verify.py` timed with `time`.*

| configuration | time |
|---|---|
| without sandbox or fingerprint | 25.0 s |
| with sandbox and fingerprint | 32.9 s |
| one archive fingerprint | 0.75 s |

## M5 — Test suite
*Provenance: pytest output.*

| when | tests | time |
|---|---|---|
| after the four fixes | 58 passed | 295.9 s |

## M6 — Calibration, 11 post-cutoff problems
*Provenance: `calibration_full.json`, built from `calibration_run1.txt` and
`calibration_outcome.json`, in this directory.*

Snapshot `external/fc-main` (commit 0a8b856c, Lean 4.33.1), model
`claude-opus-5`, effort `medium`, at most 20 iterations per problem, the archive's
proof hidden and verified as acceptable before the attempt.

| quantity | value |
|---|---|
| problems attempted | 11 |
| solved | 9 |
| of which category `test` | 4 of 4 |
| of which category `research solved` | 5 of 7 |
| total spend | $2.9834 against a limit of $15 |
| mean cost of a success | $0.1162 |
| mean cost of a failure | $0.9686 |
| median cost of the first iteration | $0.0430 |
| total time | 0.45 hours, 46% of it Lean running locally |

The two failures: `JacobianConjecture.jacobian_conjecture` ($0.6886, stopped by
the 20 iterations) and `WrittenOnTheWallII.GraphConjecture65.conjecture65`
($1.2486, stopped by the spending cap). In both cases the mathematical strategy
was right — a counterexample known in the literature — and the obstacle was the
Lean engineering.

## M7 — Automatic probe on open statements
*Provenance: `probe_lean.json` in this directory.*

Four tactics (`decide`, `plausible`, `norm_num`, `simp_arith`) in direct and
negated form, 60 s timeout per attempt, no API spend.

| quantity | value |
|---|---|
| open statements tried | 30 (240 attempts) |
| that fall on their own | 0 |

One apparent case — `Arxiv.«2107.12475».CollatzLike` — was `plausible` failing to
find a counterexample and leaving a `sorry`: the file compiled with a warning and
the verdict reader took it as "closed". Fixed in `scripts/probe_lean.py`, with
five tests in `tests/test_sonda.py`.

## M8 — Speed of the local computation
*Provenance: the search log of `euclide_squarefree`.*

| quantity | value |
|---|---|
| Euclid-number search | 86 candidates per second on one core |
| prime reached | past 2,900,000, nothing found |
| complete Lean verification | 32.9 s with sandbox and fingerprint; 25.0 s without |

## M9 — The agent with Fable 5.1
*Provenance: `fable_trial.json` in this directory.*

| quantity | value |
|---|---|
| problem | `WilsonPrime.not_isWilsonPrime_seven`, proof hidden |
| outcome | **SOLVED** on the first iteration |
| cost | **$0.0792** (against $0.0148 with Opus 5) |
| tokens | 4 in, 4,799 written to cache, 383 out |
| Lean verification | 250 s — ten times the usual, because the artefact probe was occupying the machine |

It was there for one thing: to see whether the chain works with Fable 5.1 before
spending in earnest. It works.

## M10 — Our budget arithmetic against a real invoice
*Provenance: `external/LeanOpenProblems-results/.../A055487_conjecture/info.json`.*

One attempt from the OEIS Open benchmark, with the tokens published by Epoch AI:
607 in, 2,304,613 written to cache, 36,946,793 read from cache, 684,987 out, model
Opus 4.8.

| | |
|---|---|
| cost Epoch AI paid | $50.0049 |
| cost computed by `agent/costs.py` | **$50.00** |
| the same profile with Fable 5.1 | $72.30, that is **1.45×**, not 2× |

It is the strongest check we have on the spending arithmetic, because it comes
from outside. It is now a test.

## M11 — Cost of a success, measured on Epoch AI's data
*Provenance: the `info.json` files of the run `oeis-open-lite-fable51` (100 problems).*

| quantity | value |
|---|---|
| successes | 53 of 100 |
| **median cost of a success** | **$3.55** |
| successes obtained under $2 | 22 of 53 |
| useful lines of Lean, successes under $2 | median 52 |
| useful lines of Lean, successes over $30 | median 1,544 |
| share of refutations among the successes | 40% |

When it works, it works quickly and cheaply. The budget is eaten by the failures,
which always reach the cap.
