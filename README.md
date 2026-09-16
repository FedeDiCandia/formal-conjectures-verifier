# Formal Conjectures Solver

An experimental system that points a language model at mathematical problems
formalised in Lean 4 — taken from Google DeepMind's
[formal-conjectures](https://github.com/google-deepmind/formal-conjectures)
archive — and refuses to call anything a result until the Lean kernel says so.

It did not solve an open problem. What it did produce is a judge you can run
yourself, four machine-checked proofs of results that were already known but not
formalised, a short note on a formalised OEIS conjecture, and a set of
measurements about how much this kind of work costs. The section on **what did
not work** is the most useful part, and it is not an afterthought.

> **Not affiliated.** A personal project, unconnected to Google DeepMind, to
> Epoch AI, and to Anthropic.

---

## The point is the verifier, not the agent

A model that writes Lean proofs has many ways to *look* like it solved a problem
without solving it: a `sorry` in a helper lemma, an extra axiom, a statement
weakened by one hypothesis, a definition redefined more conveniently,
`native_decide` handing the work to the compiler instead of the kernel. Without a
judge you can trust, any result is meaningless.

So the judge came first, and it is not ours: it is
[**comparator**](https://github.com/leanprover/comparator), written by the Lean
FRO. It compiles the archive's statement and the candidate's file as two separate
modules, exports both through `lean4export` (never trusting `.olean` files),
compares the **elaborated syntax trees** of the statements structurally, checks
which axioms the proof depends on, and replays the whole proof term through the
Lean kernel.

Around it this repository adds:

| | |
|---|---|
| a syntactic pre-scan | rejects 24 commands, 22 attributes, 19 metaprogramming monads, 6 tokens and 6 options that run code at elaboration time, before Lean ever sees the file |
| a sandbox | `sandbox-exec`: no network, writes only inside the judge's own scratch directory |
| an archive fingerprint | content hashes of 786 `.olean` files and 795 sources, taken **before and after** every verification |
| a refutation mode | builds `theorem X_disproof : ¬ (type_of% @X)` as a trusted challenge, so a counterexample can be certified the same way a proof is |
| a hard spending limit | the maximum possible cost of the next API call is computed *before* making it |

Only `propext`, `Classical.choice` and `Quot.sound` are permitted axioms.

**Interesting coincidence:** Epoch AI's independent
[OEIS Open benchmark](https://arxiv.org/abs/2608.11941) uses the same comparator
for the same purpose. Where the two could be compared, the judges agree in kind;
their isolation is stronger (three Docker containers against our `sandbox-exec`).

---

## Installation

Requirements: macOS or Linux, Python 3.11+ (developed on 3.13), `curl`, git, and
about 40 GB of free disk.
Everything else — `elan`, Lean, the archive, Mathlib's cache, comparator,
`lean4export` — is installed by the setup script.

```bash
git clone https://github.com/FedeDiCandia/formal-conjectures-solver.git
cd formal-conjectures-solver

bash scripts/setup.sh                        # long: ~1 hour, downloads ~8 GB
./.venv/bin/python verifier/index.py --build # builds the problem index
```

The agent — and only the agent — needs an Anthropic API key. The verifier, the
searches and the tests run without one:

```bash
cp .env.esempio .env      # then put your key in .env; .env is gitignored
```

---

## Reproducing the verification

```bash
./.venv/bin/python -m pytest tests/ -q       # 158 tests, ~6 minutes
```

The tests that matter are the ones that try to cheat the judge, and they are
written to be read: the verifier must **accept** a correct proof and **reject** a
`sorry`, an added axiom, `native_decide`, a statement weakened by one hypothesis,
and a file that redefines an archive definition. Each is checked twice — once
with the syntactic pre-scan on, once with it off — so that a defence that gets
bypassed does not take the whole system with it. One test writes a file that
tries to overwrite an archive `.olean` from inside Lean, and asserts that the
**sandbox** stops it, not the pre-scan.

Check a single proof — this is the command behind every claim in this README:

```bash
./.venv/bin/python verifier/verify.py THEOREM_NAME candidate.lean
./.venv/bin/python verifier/verify.py THEOREM_NAME candidate.lean --json
```

The proofs in [`docs/contributi/formal-conjectures/candidati/`](docs/contributi/formal-conjectures/candidati/)
are the exact files that were submitted to it, and can be re-run as they are.

Two archive snapshots are pinned, and the second one is why the measurements mean
anything: the benchmark tag predates the model's declared training cutoff, so
results on it also measure memory. Select a snapshot with three environment
variables:

```bash
env FCS_ARCHIVE=$PWD/external/fc-main \
    FCS_LEAN4EXPORT=$PWD/external/lean4export-433/.lake/build/bin/lean4export \
    FCS_INDEX=$PWD/verifier/problem_index_main.json \
    ./.venv/bin/python -m pytest tests/ -q
```

| | benchmark snapshot | post-cutoff snapshot |
|---|---|---|
| formal-conjectures | tag `bench-v1-lean4.27.0` | `main` at commit `0a8b856c` (10 Sep 2026) |
| Lean | `v4.27.0` | `v4.33.1` |
| lean4export | recent source, built with the matching Lean | same |
| comparator | `2312244`, Lean 4.34.0-rc2 — deliberately a different version, since it only reads exported text | same |

---

## Results

### 1. A note on OEIS A105020 and binary Goldbach

[`docs/pubblicazione/A105020-goldbach.pdf`](docs/pubblicazione/A105020-goldbach.pdf)
(20 pages, source and Lean files in the same directory). The archive contains
`OeisA105020.conjecture`, a Lean formalisation of a 2007 OEIS comment presented as
"a Goldbach Conjecture for this sequence". The note proves that this formal
statement is **equivalent** to the archive's own statement of binary Goldbach —
including an index lemma that the formal statement needs because it quantifies
over arbitrary indices — and formalises every result in Lean 4, checked with
comparator. No novelty is claimed for the mathematics: the correspondence is
implicit in a 2021 formula of W. I. Hurt in OEIS A045917. The point is what it
means for the archive: one of its open entries is not an independent problem.

### 2. Four machine-checked proofs of known results

The archive marks some problems `research solved` or `textbook` — the proof is
known and published, but nobody has written it in Lean. Of 1209 such candidates,
a first band of 16 was attempted at a $1 cap per problem:

| | |
|---|---|
| attempts with a determinate outcome | 14 |
| proofs accepted by the verifier | 5 |
| of those, not already formalised elsewhere | **4** |
| rate on candidates that were actually open | **4 / 12 = 33%** |
| cost per valid contribution | about $3, faults included |

The four: `DiophantineTuple` (two statements), `erdos_1000.variants.totient_le`,
`Erdos1148…weaker`, and `ComplexityTheory.coP_eq_P`. Drafts, patches and the
verifier's reports are in
[`docs/contributi/formal-conjectures/`](docs/contributi/formal-conjectures/LEGGIMI.md).

**Status upstream, honestly:** accepted *by this verifier* is not accepted *by the
archive*. Two issues have been filed and assigned
([#5992](https://github.com/google-deepmind/formal-conjectures/issues/5992),
[#5993](https://github.com/google-deepmind/formal-conjectures/issues/5993)) and
the two corresponding pull requests are prepared. Nothing has been merged at the
time of writing. Every proof produced with model assistance says so, in the pull
request and in the commit.

A step that pays for itself: **check whether someone has already formalised it**,
before spending anything. Three of the thirteen problems attempted in the first
round were already proved in other repositories, and that is free to find out.

### 3. Calibration: can the agent prove things it has not seen?

Eleven problems the archive itself proves, with the proof hidden, all added to the
archive **after** the model's declared training cutoff, and all with the archive's
own proof verified as acceptable first:

| | |
|---|---|
| solved | **9 / 11** |
| of which sanity checks (`test` category) | 4 / 4 |
| of which real conjecture variants (`research solved`) | **5 / 7** |
| median cost of a success | $0.14 |
| cost of a failure | the per-problem cap, every time |

The number to remember is 5 out of 7, not 9 out of 11.

### 4. Reproducing published records in coding theory

On A(n,d,w), binary constant weight codes, against Brouwer's tables:

| | |
|---|---|
| published record codes verified exactly | 331 / 361 |
| known optima reached from scratch by our search | 23 / 26 |
| known optima **not** exceeded (falsification test) | 26 / 26 |
| published lower bounds matched, 3000 iterations per cell | 78 / 119 |
| published lower bounds beaten | **0** |

The third row is the important one: the engine never claimed more than a value
proved optimal. That is what makes the other rows worth reading.

---

## What did not work

- **The premise that a cheap sweep would find easy open problems.** It would not.
  The archive is curated so that it does not contain them, and nothing labelled
  `research open` carries a complete proof.
- **Open problems, three rounds, zero results.** In 139 API calls across ten
  distinct open problems, the agent submitted **two** candidates to the verifier.
  It did not fail to prove: **it did not attempt to prove.** What it does instead,
  it does well — it computes, confirms the conjecture numerically, locates the hard
  step, and stops. Three explanations were tested and ruled out, each with a
  measurement: not the spending cap (all ten attempts stopped on their own having
  spent 6–32% of it), not the give-up wording (removing the invitation to give up
  triples the spend and leaves submissions at one), not the model (two frontier
  models behave the same way).
- **Small witnesses that do not exist.** Selecting problems where a result *would*
  be cheap to certify is not the same as selecting problems where a result exists.
  Free exhaustive searches settled three of them negatively (one up to 10³⁹⁹).
- **Counterexamples found by enumeration.** For "for every n there is k < n with
  P(n,k)", refuting one n means proving in Lean that *no* k works — a million
  compositeness facts for n above a million. The kernel does not get there.
- **The "are there any more?" trap.** An OEIS question like "after a(2), is there
  another prime?" becomes `True ↔ ∃ n, …` under the archive's `answer(sorry)`
  convention: the statement *asserts the answer is yes*, while the honest prior is
  no. The certifiable direction is the empty one.
- **Known-but-unformalised proofs, below the top band.** Of 1209 candidates, the
  projection is 10–20 valid contributions in total, nearly all in the two easiest
  bands; below them a $1 cap buys exploration, not proofs. In the last round, five
  of seven failures spent the whole cap reading definitions (Turing machines, plane
  geometry, Sidon sets) and never submitted a candidate at all.

## Four defects of our own that nearly produced false results

All four shared a property worth naming: **none of them made anything fail
visibly. All of them made a result appear that was not there.**

1. `plausible`, Mathlib's property tester, leaves a `sorry` when it finds no
   counterexample — the file compiles with a warning. A probe read that as "the
   tactic closed an open problem".
2. Two concurrent explorations wrote to the same scratch file, so each read the
   other's Lean output. A trivial tactic appeared to close a topology problem; the
   messages belonged to a different problem entirely.
3. A verdict reader attributed Lean's error messages to the wrong declaration, and
   reported that both a statement *and its negation* had been proved.
4. The spending guard reserved the worst case of the next call and refused to
   proceed, which looked exactly like the model giving up. It invalidated one
   experiment and mislabelled one calibration failure.

Every verdict is now read from `#print axioms`: a tactic closed a statement only
if the resulting declaration does not depend on `sorryAx`. That is the criterion
the verifier uses, and the only one we trust.

A fifth defect was in the environment, not the code: a laptop that went to sleep
mid-run killed six attempts and charged them to their cap. Network failures no
longer consume a problem's budget, and the agent refuses to start unless the
machine is on mains power with `caffeinate` holding it awake.

---

## Other things worth keeping

- **Computational frontiers nobody had published**, with programs and
  checkpoints: Euclid numbers checked for square factors past the 216 815th prime
  (complete for all primes below 3·10⁶); A. Murthy's `nk+1` conjecture past
  n = 350 million; the fixed points of A113010 settled **exhaustively** for all n
  below 10³⁹⁹.
- **Seven stale "open" labels**: problems the archive still marks open that have
  been resolved elsewhere — five Erdős problems resolved in Epoch AI's runs, plus
  two OEIS conjectures.
- **A defect in the archive's build configuration** (on `main`): two Lean
  libraries glob the same files into the same build directory with different
  `google.answer` settings, so the elaborated statement of an `answer(sorry)`
  problem depends on which build command ran last. A judge cannot work against a
  moving target; our snapshot disables the duplicate.
- **A cost model** for this kind of work, with every number labelled as measured
  or estimated. The most useful number came from someone else: Epoch AI's results
  show that on a model's own failures, **changing model beats spending more, by a
  factor of four to five** (6.2% recovered at 4× the budget; 27.7% and 33.8% with a
  newer model).

## Total cost

About **$37** of API credit, across everything: the connection test, the
calibration, three rounds on open problems, the instruction experiments, and two
rounds of formalising known proofs. The local compute — Lean, the searches, the
probes — was free, and there was far more of it than there was API spend.

---

## Layout

| directory | contents |
|---|---|
| `verifier/` | the judge: `verify.py`, `guard.py`, the archive index, refutation challenges |
| `agent/` | the agent, its tools, the cost accounting, the keep-awake check |
| `tests/` | 158 tests; the adversarial ones are the point |
| `scripts/` | setup, target selection, searches, probes, analysis |
| `ricerca/` | the coding-theory search and the reproduction of published records |
| `docs/` | the full write-up, in Italian, including the finding protocol |
| `docs/pubblicazione/` | the A105020 note: PDF, LaTeX source, Lean files |
| `docs/contributi/` | the proofs prepared for the archive, with patches and reports |
| `docs/dati/` | every raw report, so the numbers above can be checked |

Most documentation is in Italian; [`README.it.md`](README.it.md) is the Italian
version of this page. The code, the Lean files and the published note are in
English.

## Known limits

Set out in full in [docs/02-verificatore.md](docs/02-verificatore.md). In short:

- **The sandbox on macOS is `sandbox-exec`, which Apple has deprecated.** It works,
  and a test proves it (a candidate that tries to rewrite an archive `.olean` is
  stopped by the sandbox, not by the pre-scan), but `landrun` — comparator's own
  answer — is Linux-only, and what stands in for it here is a shim that does not
  isolate.
- **The correctness of the Lean kernel is an assumption**, as it is for anyone
  using Lean.
- **Mathlib's cache comes from the network.**
- **The faithfulness of a formalisation cannot be verified.** If a Lean statement
  does not capture the conjecture it names, proving it proves nothing about the
  conjecture. The archive says so itself, and the A105020 note is an example of
  what auditing a single statement takes.

## Licence and attribution

This repository is released under the **Apache License 2.0** — the same licence as
formal-conjectures, Lean and Mathlib, which is what the Lean files here derive
from. See [LICENSE](LICENSE), and [NOTICE](NOTICE) for the file-by-file
attribution, which in summary is:

- [**formal-conjectures**](https://github.com/google-deepmind/formal-conjectures),
  Google DeepMind — Apache 2.0. The statements, the problem index and the copied
  files come from it; the archive itself is cloned, not redistributed.
- [**comparator**](https://github.com/leanprover/comparator), the Lean FRO —
  Apache 2.0. It is the judge: every verdict here is its verdict.
- [**Lean 4**](https://github.com/leanprover/lean4) and
  [**Mathlib**](https://github.com/leanprover-community/mathlib4) — Apache 2.0.
  Lean's kernel is what "verified" means in this repository.
- [**LeanOpenProblems**](https://github.com/epoch-research/LeanOpenProblems),
  Epoch AI — MIT. Their published results were read and counted, not modified.
- [**The OEIS**](https://oeis.org/) — the entries mirrored under `dati_ricerca/`
  and quoted in the note are OEIS content, under CC BY-SA 4.0.
- **Andries E. Brouwer's** [tables of bounds for binary codes](https://aeb.win.tue.nl/codes/)
  — his pages carry no licence notice, so they are not redistributed here: the
  tables and the 362 explicit codes are downloaded from his site on first use.

Parts of this repository — including some of the Lean proofs — were written with
AI assistance, and every such proof is machine-checked before it is called a
proof. Where a proof was proposed upstream, the pull request says so explicitly.
