# How the `formal-conjectures` archive works

A summary of the `README.md`, `CONTRIBUTING.md` and `AGENTS.md` of the tag
`bench-v1-lean4.27.0` (commit `7a41db3d`, 6 May 2026).

`CONTRIBUTING.md` contains nothing technical: it covers the contributor licence
agreement, code review, and how labels are managed on GitHub.

---

## 1. What the archive is

It is a collection of **statements** of mathematical conjectures, written in
Lean 4 on top of Mathlib. The key point: almost none of the statements has a
proof. In place of the proof there is the word `sorry`, which in Lean means
"the proof is missing here, take it on trust and carry on".

A typical file looks like this:

```lean
/-- Is every even integer greater than 2 a sum of two primes? -/
@[category research open, AMS 11]
theorem goldbach :
    answer(sorry) ↔ ∀ n : ℕ, 2 < n → Even n → ∃ p q, Prime p ∧ Prime q ∧ n = p + q := by
  sorry
```

The system has to replace that final `sorry` with a real proof. The verifier
exists to decide whether the replacement is honest.

An important rule of the archive: long proofs (beyond 25–50 lines) are **not**
accepted into it; they are linked from an external repository through the
`formal_proof` attribute. This is an archive of *problems*, not of *solutions*.

---

## 2. The `category` attribute — what kind of problem it is

A mandatory label on every theorem. It says what genus of statement this is. It
has no logical effect: it is pure classification, and it is exactly what one
needs in order to choose problems.

| Label | Meaning |
|---|---|
| `@[category research open]` | An **open** research problem: no solution accepted by the mathematical community. |
| `@[category research solved]` | A **solved** research problem: an informal proof exists and is accepted by experts (not necessarily formalised). |
| `@[category textbook]` | A textbook exercise (secondary school, undergraduate, graduate). |
| `@[category API]` | A statement that builds the basic theory around a new definition. |
| `@[category test]` | A sanity check, a kind of unit test that a definition behaves as intended. |

Note that `research solved` means "mathematicians know how to solve it", **not**
"a formal proof exists in Lean". The distinction matters a great deal here: it is
the `research solved` and `textbook` problems on which it makes sense to measure
an agent, because an answer exists.

The source is `FormalConjectures/Util/Attributes/Basic.lean`, which defines the
type `Category` with constructors `textbook`, `research (open|solved)`, `test`
and `API`. There is also a mandatory `@[AMS n]` attribute for the subject area
(11 = number theory, 5 = combinatorics, and so on).

---

## 3. The `formal_proof` attribute — where the formal proof lives

It records the **existence and the location** of a formal proof. It is
independent of `category` and can be used with any of them.

Syntax: `@[formal_proof using <kind> at "<link>"]`, where `<kind>` is one of:

| Value | Meaning |
|---|---|
| `formal_conjectures` | Proved formally **inside this archive**; the link points at the commit that fills the `sorry`. |
| `lean4` | Proved in Lean 4 **elsewhere** (Mathlib, or another repository). |
| `other_system` | Proved in **another formal system** (Rocq/Coq, Isabelle, Lean 3, HOL…). |

A `formal_proof` on a `research open` problem triggers a linter warning: an open
problem should not have a proof.

**Why this matters here:** a theorem carrying `formal_proof` is a problem for
which a formal proof is known to exist. Those are the ideal candidates for
calibrating an agent, because it is reasonable to expect them to be solvable.

Since PR #4962 (18 August 2026) a linter also warns when a theorem tagged
`formal_proof` has a proof other than `sorry`: the attribute is for proofs that
live *elsewhere*. A proof written inside the archive's own file carries no
`formal_proof` attribute at all.

---

## 4. The `answer( )` elaborator — the subtlest point

### What it is for

Some mathematical questions are not "true or false" but "what is the value of
X?". The Hadwiger–Nelson problem, for instance, asks for the minimum number of
colours needed to colour the plane; it cannot be formalised without already
knowing the answer. `answer( )` is a placeholder marking **the place where the
answer goes**:

```lean
@[category research open]
theorem HadwigerNelsonProblem :
    UnitDistancePlaneGraph.chromaticNumber = answer(sorry) := by
  sorry
```

So a statement of this kind has **two different holes**:

- `answer(sorry)` — we do not know **what the answer is** (a hole in the statement);
- `:= by sorry` — we do not know **how to prove it** (a hole in the proof).

They are holes of different natures. Filling the second is work Lean can check on
its own. Filling the first takes mathematical judgement: as the source file puts
it, *"this is a job for human mathematicians, not for Lean alone"*.

### The recommended style for yes/no questions

When the informal problem is a question ("Does P hold?"), the convention is

```lean
/-- Does P hold? -/
theorem myConjecture : answer(sorry) ↔ P := by
  sorry
```

so that the "Does … hold?" corresponds to the `answer(sorry)`. If the problem is
settled, `answer(sorry)` becomes `answer(True)` or `answer(False)`.

### How it actually works (from `FormalConjectures/Util/Answer.lean`)

This is the technical detail that matters most to a verifier. `answer( )` has
**three modes**, controlled by the option `google.answer`:

| Mode | Behaviour |
|---|---|
| `always_true` (**default**) | If the argument is `sorry` and the expected type is a proposition (`Prop`), `answer(sorry)` becomes **`True`**. |
| `postpone` | Postpones elaboration of the term; the `sorry` stays a `sorry`. |
| `with_auxiliary` | Creates a separate auxiliary definition named `<theoremName>._answer` holding that value. |

The consequence of the default mode is surprising, and very useful:

> `answer(sorry) ↔ P` elaborates as `True ↔ P`.

And `True ↔ P` is logically equivalent to `P`. So **for yes/no problems the
default mode removes the hole in the statement entirely**: whoever proves the
theorem really is proving `P`, with no way round it. That is exactly what a
verifier wants.

The problem remains for answers that are **not** propositions (numbers, sets,
…): there `answer(sorry)` stays a genuine `sorry` **inside the statement**. A
statement containing `sorry` cannot be proved honestly — any proof of it would
depend on the axiom `sorryAx`. The verifier must notice this and say so, rather
than pass over it.

### The mode does not depend only on the option: it depends on who compiled

*This applies to the `main` branch, not to the `bench-v1` tag.*

The `lakefile.toml` on `main` declares **two libraries that compile the same
files into the same build directory**:

| library | glob | `google.answer` |
|---|---|---|
| `FormalConjectures` | `FormalConjectures.+` | default (`always_true`) |
| `FormalConjecturesAnswerPostpone` | `FormalConjectures.+` | `postpone` |

The `.olean` files land in the same place, so **the last build command wins**,
and the elaborated statement of an `answer(sorry)` problem changes accordingly:

```
lake build FormalConjectures       ->  True ↔ P       (no sorry)
lake build <a single module>       ->  sorryAx ↔ P    (hasSorry: true)
```

This is not a guess: it can be read off `.lake/build/ir/<module>.setup.json`,
which records the options the module was actually compiled with.

For a judge this is intolerable: the same candidate is accepted or rejected
depending on how the archive happened to be built a moment earlier. In our
snapshot the second library is **disabled** (`scripts/setup_snapshot_main.sh`
redoes this if the snapshot is regenerated), so the semantics is always
`always_true` — the one that makes yes/no problems genuinely provable.

### The warning to keep in mind

Both the archive's README and comparator's documentation warn about the same
thing: **supplying a term inside `answer( )` and proving the statement is not the
same as solving the problem.** If the question is "which natural numbers satisfy
P?", one can answer `{n | P n}` and prove it by reflexivity: formally
unimpeachable, mathematically empty.

So for problems with a **non-propositional** `answer( )` hole, an automatic
verifier can guarantee formal correctness but **not** that the answer means
anything. It has to say so.

---

## 5. Other rules that matter here

- Benchmark problems are declared with `theorem` or `lemma`.
- `sorry` is allowed in `FormalConjectures/` (those are statements without
  proofs) but **forbidden** in `FormalConjecturesForMathlib/`.
- `native_decide` is discouraged everywhere and forbidden in
  `FormalConjecturesForMathlib/`. Here it is always rejected: it leans on the
  compiler rather than the kernel — see [the verifier](02-the-verifier.md).
- Problem files import only `FormalConjectures.Util.ProblemImports`.
- Each problem lives in its own file; variants live in the same file under dotted
  names, e.g. `main_conjecture.variants.special_case`.
- The tags `bench-v{N}-lean4.{X}.{Y}` are **immutable**: corrections to faulty
  formalisations go into `v{N+1}`, never inside an existing tag. That is what
  makes the benchmark reproducible.
