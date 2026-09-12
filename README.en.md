# Formal Conjectures Solver

An experimental system that points a language model at **open mathematical
problems** formalised in Lean 4, taken from Google DeepMind's
[formal-conjectures](https://github.com/google-deepmind/formal-conjectures)
archive, and tries to get a machine-checked answer out of it.

It did not solve an open problem. This README says what it *did* do, what it
measured, and which of our own defects nearly produced results that were not
there — because that last part is the most useful thing in here.

> **Not published, not affiliated.** This is a personal project. It is not
> connected to Google DeepMind, to Epoch AI, or to Anthropic. Nothing here has
> been reported to the archive's authors or to anyone else.

---

## The point is the verifier, not the agent

A model that writes Lean proofs has many ways to *look* like it solved a problem
without solving it: a `sorry` left in a helper lemma, an extra axiom, a statement
weakened by one hypothesis, a definition redefined more conveniently,
`native_decide` handing the work to the compiler instead of the kernel. Without a
judge you can trust, any result is meaningless.

So the judge came first, and it is not ours: it is
[**comparator**](https://github.com/leanprover/comparator), written by the Lean
FRO. It compiles the archive's statement and the candidate's file as two separate
modules, exports both through `lean4export` (never trusting `.olean` files),
compares the **elaborated syntax trees** of the statements structurally, checks
the axioms the proof depends on, and replays the whole proof term through the
Lean kernel.

Around it we added:

| | |
|---|---|
| a syntactic pre-scan | rejects 19 constructs that execute code at compile time before Lean ever sees the file |
| a sandbox | `sandbox-exec`: no network, writes only in the judge's own scratch directory |
| an archive fingerprint | content hashes of 786 `.olean` files and their sources, taken **before and after** every verification |
| a refutation mode | builds `theorem X_disproof : ¬ (type_of% @X)` as a trusted challenge, so a counterexample can be certified the same way a proof is |
| a hard spending limit | the maximum possible cost of the next API call is computed *before* making it |

Only `propext`, `Classical.choice` and `Quot.sound` are permitted axioms.

**Interesting coincidence:** Epoch AI's independent
[OEIS Open benchmark](https://arxiv.org/abs/2608.11941) uses the same comparator
for the same purpose. Where we could compare, the two judges agree in kind; their
isolation is stronger (three Docker containers against our `sandbox-exec`).

---

## How to check it yourself

```bash
bash scripts/setup.sh                        # long: ~1 hour, downloads ~8 GB
./.venv/bin/python verifier/index.py --build
./.venv/bin/python -m pytest tests/ -q       # 123 tests, ~6 minutes
```

The six tests that matter are the ones that try to cheat the judge, and they are
written to be read: the verifier must **accept** a correct proof and **reject** a
`sorry`, an added axiom, `native_decide`, a statement weakened by one hypothesis,
and a file that redefines an archive definition. Each is checked twice — once with
the syntactic pre-scan on, once with it off — so that a defence that gets bypassed
does not take the whole system with it.

One test writes a file that tries to overwrite an archive `.olean` from inside
Lean, and asserts that the **sandbox** stops it, not the pre-scan.

Verify a single proof:

```bash
./.venv/bin/python verifier/verify.py THEOREM_NAME candidate.lean
```

---

## What we measured

Every number below comes from a recorded run; the raw reports are in
[`docs/dati/`](docs/dati/).

### Calibration: can the agent prove things it has not seen?

Eleven problems that the archive itself proves, with the proof hidden, all added
to the archive **after** the model's declared training cutoff, and all with the
archive's own proof verified as acceptable first:

| | |
|---|---|
| solved | **9 / 11** |
| of which sanity-check problems (`test` category) | 4 / 4 |
| of which real conjecture variants (`research solved`) | **5 / 7** |
| median cost of a success | $0.14 |
| cost of a failure | the per-problem cap, every time |

The number to remember is 5 out of 7, not 9 out of 11.

### Open problems: three rounds, zero results

| round | model | instructions | cap | problems | spend | API calls | **candidates submitted** | solved |
|---|---|---|---|---|---|---|---|---|
| 0 | Fable 5.1 | default | $2.00 | 10 | $2.30 | 32 | **0** | 0 |
| 0-bis | Fable 5.1 | insistent | $2.00 | 7 | $5.51 | 57 | **1** | 0 |
| 0-ter | Opus 5 | insistent + budget fix | $1.50 | 4 | $3.86 | 50 | **1** | 0 |

The column that explains the result is the second-to-last. In 139 API calls
across ten distinct open problems, the agent submitted **two** candidates to the
verifier. It did not fail to prove: **it did not attempt to prove.** What it does
instead, it does well — it computes, confirms the conjecture numerically, locates
the hard step, and stops.

Three explanations were tested and ruled out, each with a measurement:

- **not the spending limit** — in round 0 it never triggered: all ten attempts
  stopped on their own having spent 6–32% of the cap;
- **not the give-up wording** — with instructions that remove the invitation to
  declare defeat, spend per problem triples and computation doubles; submissions
  stay at one;
- **not the model** — two different frontier models behave the same way.

### The external anchor, and what it changes

Epoch AI's OEIS Open results (public, measured by us from their files) reframe
the economics:

| | |
|---|---|
| open OEIS conjectures resolved by a frontier model at $50 each | **147 / 492 (30%)** |
| best result at $200 each | 53–57% |
| **median cost of a successful attempt** | **$3.55** |
| fraction of their successes that are **disproofs** | 40% |
| same model, 4× the budget, on its own failures | recovers **6.2%** |
| a *different, newer* model on those same failures | recovers **27.7%** and **33.8%** |

The last two rows are the most useful thing we learned from anyone: **changing
model beats spending more, by a factor of four to five.** Giving the model 476 000
arXiv papers, or a more elaborate agent loop, changed nothing (6.2% either way).

---

## What did not work, and why

- **The premise that a cheap sweep would find easy open problems.** It would not.
  The archive is curated so that it does not contain them, and nothing labelled
  `research open` carries a complete proof.
- **Small witnesses that do not exist.** Selecting problems where a result *would*
  be cheap to certify is not the same as selecting problems where a result exists.
  Free exhaustive searches settled three of them negatively (one up to 10³⁹⁹).
- **Counterexamples found by enumeration.** For "for every n there is k < n with
  P(n,k)", refuting one n means proving in Lean that *no* k works — a million
  compositeness facts for n above a million. The kernel does not get there.
- **The "are there any more?" trap.** An OEIS question like "after a(2), is there
  another prime?" becomes `True ↔ ∃ n, ...` under the archive's `answer(sorry)`
  convention: the statement *asserts the answer is yes*, while the honest prior is
  no. The certifiable direction is the empty one.

## Four defects of our own that nearly produced false results

All four shared a property worth naming: **none of them made anything fail
visibly. All of them made a result appear that was not there.**

1. `plausible`, Mathlib's property tester, leaves a `sorry` when it finds no
   counterexample — the file compiles with a warning. Our probe read that as
   "the tactic closed an open problem".
2. Two concurrent explorations wrote to the same scratch file, so each read the
   other's Lean output. A trivial tactic appeared to close a topology problem;
   the messages belonged to a different problem entirely.
3. A verdict reader attributed Lean's error messages to the wrong declaration, and
   reported that both a statement *and its negation* had been proved.
4. The spending guard reserved the worst case of the next call and refused to
   proceed, which looked exactly like the model giving up. It invalidated one
   experiment and mislabelled one calibration failure.

Every verdict is now read from `#print axioms`: a tactic closed a statement only
if the resulting declaration does not depend on `sorryAx`. That is the same
criterion the verifier uses, and it is the only one we trust.

---

## What the machine produced that is worth keeping

- **Computational frontiers nobody had published**, with the programs and
  checkpoints: Euclid numbers checked for square factors past the 216 815th prime
  (complete for all primes below 3·10⁶); A. Murthy's `nk+1` conjecture past
  n = 350 million; the fixed points of A113010 settled **exhaustively** for all n
  below 10³⁹⁹.
- **Seven stale "open" labels**: problems the archive still marks open that have
  since been resolved elsewhere — five Erdős problems resolved in Epoch's runs,
  plus two OEIS conjectures.
- **A defect in the archive's build configuration** (on `main`): two Lean
  libraries glob the same files into the same build directory with different
  `google.answer` settings, so the elaborated statement of any `answer(sorry)`
  problem depends on which build command ran last. A judge cannot work against a
  moving target; our snapshot disables the duplicate.
- **A reproducible cost model** for this kind of work, with every number labelled
  as measured or estimated.

None of this has been reported to anyone. It is written up in
[`docs/`](docs/) (in Italian) in case it is ever useful.

---

## Total cost

**$20.53** of API credit, across everything: the first connection test, the
calibration, three rounds on open problems, and the instruction experiments. The
local compute — Lean, the searches, the probes — was free, and there was a lot
more of it than there was API spend.

---

## Layout

| directory | contents |
|---|---|
| `verifier/` | the judge: `verify.py`, `guard.py`, the archive index, refutation challenges |
| `agent/` | the agent, its three tools, the cost accounting |
| `tests/` | 123 tests; the adversarial ones are the point |
| `scripts/` | setup, target selection, searches, probes, analysis |
| `docs/` | the full write-up, in Italian, including the finding protocol |
| `docs/dati/` | every raw report, so the numbers above can be checked |

## Licences

This repository is the glue. The things it stands on are other people's:
[formal-conjectures](https://github.com/google-deepmind/formal-conjectures)
(Apache 2.0, Google DeepMind), [comparator](https://github.com/leanprover/comparator)
(Lean FRO), [Mathlib](https://github.com/leanprover-community/mathlib4), and
Epoch AI's [LeanOpenProblems](https://github.com/epoch-research/LeanOpenProblems)
results (MIT), which we read but did not modify.
