# What to do about a finding

To be applied **before** telling anyone that something has been found, and before
believing it.

The reason is simple: in this field, an easy counterexample to a famous problem
almost always means that **the formalisation does not say what it appears to
say**, not that the problem has fallen. The problems in this archive have been
open for decades and many have been checked by computer to enormous thresholds.
If our program finds a counterexample in ten minutes, by far the likeliest
hypothesis is that the mistake is ours.

The protocol is there to find out which case it is, in the order that rules out
the likeliest hypotheses first.

---

## Step 0 — BEFORE attempting: look for the reduction to a known problem

*Added 12 September 2026, after learning it the expensive way.*

This step comes **before** everything else, and before spending a cent on an
attempt. It costs about **fifty cents** and one API call.

**What to ask.** Send the problem to a model, low effort, no tools, with this
request: *do not prove it — tell me which known problem it reduces to, or which
known problem implies it.* The phase-D prompt (`scripts/informal.py`) already
does this as a side effect, since it asks for a proof and accepts "this cannot be
done, and here is why" as an honest answer.

**What to look for in the answer.** If the model **names** a famous problem —
Goldbach, Lemoine, Legendre, Sierpiński, Dickson, Lehmer, Collatz, one of Sun's
conjectures — the attempt **is not made**. Not because the model is right, but
because checking costs a minute of reading an OEIS entry, against tens of dollars
of attempt.

**The next check is free, and it is in the source.** OEIS entries very often say
what they are, in a comment nobody reads:

| problem | the line that was already in the entry |
|---|---|
| A103151 | *"This is a stronger conjecture than the Goldbach conjecture"* |
| A110835 | *"Sierpinski's conjecture (1958) is precisely that a(n) >= n for all n"* |
| A105020 | *"A 'Goldbach Conjecture' for this sequence"* |
| A357513 | *"This conjecture is now proved; see Links"* (and the archive still marked it open) |

**What not doing it cost.** Three rounds of attempts, 139 API calls, about twenty
dollars, and a zero that we attributed first to the budget, then to the
instructions, then to the model. None of the three. We were asking for Goldbach.

**So, for each problem, in this order:**

1. ask for the reduction (half a dollar);
2. read *all* the comments on the OEIS entry or the original source (free);
3. if a famous name appears, or "now proved", or a cash prize — **discard it**;
4. only what survives those three steps deserves an attempt.

---

## The commonest case, and how to recognise it at once

**An open statement that falls to a trivial tactic is not a solved problem. It
is, almost certainly, a faulty formalisation.**

By "trivial tactic" we mean `simp`, `decide`, `norm_num`, `omega`, `trivial`,
`aesop`, or a witness like `exact ⟨0, by simp⟩`. If one of these closes a problem
that mathematicians have been stuck on, the reasonable hypothesis is not that the
tactic is brilliant: it is that the Lean statement says something weaker, vacuous,
or simply different from the source.

This is not cautious speculation: it is documented in the public results of Epoch
AI's OEIS Open benchmark. Among their solutions **accepted by the verifier**:

- `A211420_general_divisibility_conjecture`, proved with `exact ⟨0, fun n => by simp⟩`.
  The statement said "there exists $C$ such that for every $n$, … divides
  $C \cdot a(n)$": with $C = 0$ it is true for nothing, since everything divides
  zero. That was not the mathematical conjecture;
- `A262403_conjecture_ii_distinctness`, refuted because $\pi(T_0) = \pi(T_1) = 0$:
  injectivity fails on two boundary cases.

Both are verified, correct, and **not mathematical results**: they are defects in
the translation into Lean.

### What to do instead

A statement of this kind **does not become the target of a serious attempt**.
Paying for a model to "solve" a vacuous statement is buying a confirmation of a
defect. Instead:

1. classify it as **suspect**, not as a finding;
2. compare the Lean statement **line by line** with the original source — step 2
   of this protocol, which here becomes the *first* step;
3. prepare a **report for the archive's authors**, with: the name of the theorem,
   the tactic that closes it, the text of the source, and the precise point where
   the translation diverges (a quantifier, an allowed $C = 0$, ℕ's truncated
   subtraction, an `sInf` over an empty set evaluating to 0, a boundary case
   $n = 0$ or $n = 1$);
4. the report is **not published** without approval: it stays a draft.

The value of these cases is real but of a different kind: it makes the archive
sounder, and it should be told for what it is.

---

## Step 1 — Re-check with an independent program

**What to do:** rewrite the check from scratch, without looking at the program
that produced the finding, preferably with a different strategy (if the first used
modular arithmetic, the second should use explicit integers; if the first used a
library, the second should avoid it).

**Why:** a programming error repeats identically if you reread the same code. It
does not repeat if the code is written again.

**Criterion:** if the two programs disagree, the finding **lapses**. Which one is
wrong still has to be worked out, but in the meantime there is no finding.

---

## Step 2 — Compare the formalisation with the source

**What to do:** read the archive's Lean statement beside the original statement of
the problem (the docstring always links the source) and ask, line by line, whether
they say the same thing. Watch particularly for:

| trap | example |
|---|---|
| quantifier over a larger set than intended | `∀ n : ℕ` where the source says "for every positive integer" and `n = 0` is degenerate |
| a missing hypothesis | the source requires the set to be infinite, the formalisation does not |
| direction of an inequality | `≤` in place of `<` |
| a different convention | in Mathlib `Nat.Prime 1` is false, elsewhere sometimes not; subtraction of naturals truncates at zero |
| `answer(sorry)` becoming `True` | the archive asserts the answer is "yes": see [the archive's conventions](01-the-archive.md) |

**Why:** this is the commonest case by a distance. The archive says so in its own
README: *"Subtle inaccuracies can arise where the formal statement might not
perfectly capture the nuances of the original conjecture."*

**Criterion:** if the Lean statement is weaker than the original, or has lost a
hypothesis, the case is **FAULTY FORMALISATION**. That is still a useful result,
worth reporting to the archive — but it is not the solution of an open problem.

---

## Step 3 — Find out the state of the problem

> **Before using a result you have found cited, check that it is about OUR
> parameters.** *Added 12 September 2026.* For D(27,5,2) the value v = 27 appears
> as a "possible exception" in three different problems — packings with λ = 2,
> directed packings with λ = 1, ordinary packings with λ = 1 — and only the last
> is ours. The first search result was the one with λ = 2. A citation without an
> identified primary source, with its parameters checked one by one (λ, t,
> directed or not, k), is evidence of nothing.

**What to do:** search online (reading only) for the problem by name and by
number, and establish:

- up to what threshold it has already been checked by computer;
- whether the case found is already known in the literature;
- whether partial results exist that exclude precisely that case.

**Why:** most of these problems have been sifted by people with more time and
bigger machines. If a counterexample lies below a threshold others have already
checked, **it is not a counterexample**: it is our mistake, and step 1 or step 2
has to explain it.

**Criterion:** if the case is below the verified threshold, go back to step 1. If
it is already in the literature, the case is **ALREADY KNOWN**.

---

## Step 4 — Verify in Lean

**What to do:** write the Lean proof of the counterexample and submit it to the
verifier.

- If the problem is `∃ x, P x`, prove the statement **as it stands**:
  ```bash
  ./.venv/bin/python verifier/verify.py NAME file.lean
  ```
- If the problem is `True ↔ ∀ n, P n` and we have a counterexample, prove the
  **negated challenge**:
  ```bash
  ./.venv/bin/python verifier/verify.py NAME file.lean --confutazione
  ```

**Why:** until there is a proof the verifier accepts, there is nothing. A number
that looks like a counterexample is not a counterexample until Lean confirms it.

**Criterion:** if the verifier accepts, and steps 1–3 have been passed, the case
is a **NEW CANDIDATE**.

---

## It applies when the proof SUCCEEDS, too

The protocol was written with counterexamples in mind, but it is needed just the
same — and forgotten more easily — when the agent **proves** something.

The case to watch for is **identities**. Many OEIS entries present as a
"conjecture" an identity that has been known in the literature for years,
sometimes decades, simply because whoever wrote the comment did not look for it,
or because the proof sits inside a paper that treats it in greater generality. An
example of the species: "it is conjectured that
$\binom{6n-2}{2n} / (2\binom{4n-1}{2n}) = A005156(n+1)/A005156(n)$" — where
A005156 counts vertically symmetric alternating sign matrices, and product
formulas for those families are the subject of published papers.

An identity the agent proves **is** a theorem checked by the Lean kernel. It is
not necessarily a **new result**, and the difference has to be settled before
telling anyone.

### What to do before calling it a result

1. **Search the literature for the identity**, not for the conjecture: the text of
   the OEIS comment may be unique while the mathematical content is known. Search
   for the formula, the names of the sequences involved, and the technical terms
   that appear in the proof the agent found.
2. **Read the entry's references**: often the formula is already among the
   `FORMULA` or `REFERENCES` lines of the entry itself, in which case the
   "conjecture" was only a comment someone added.
3. **Look at the proof**: if it comes down to unfolding definitions and
   simplifying, the claim was a rewriting, not a problem. That is a useful outcome
   — the archive ought to know — but it is not new mathematics.
4. Only if those three steps find nothing does the result go to human review as a
   **new candidate**, with the same caution as a counterexample.

---

## The classifications

| outcome | meaning | what to do with it |
|---|---|---|
| **SUSPECT** | a trivial tactic closes the statement, or closes its negation on a boundary case | not a finding: go to step 2 and prepare the report. **Do not spend money on these statements** |
| **FAULTY FORMALISATION** | the Lean statement does not capture the original problem | report it to the archive; it is not new mathematics |
| **ALREADY KNOWN** | the fact is in the literature — this applies to proved identities, not only to counterexamples | note it; it confirms the system works |
| **NEW CANDIDATE** | it has passed all four steps | **it is still not a result.** It needs to be read by a mathematician competent in the area. The verifier guarantees that the Lean proof is correct, not that the Lean statement is the conjecture |

---

## What NOT to do

- Do not publish, do not open an issue, do not write to anyone before completing
  all four steps **and** having a person read the result.
- Do not skip step 1 because "the program is simple". Simple programs are wrong as
  often as the rest.
- Do not treat Lean's verification as sufficient on its own: Lean guarantees that
  the proof is correct *with respect to the statement as written*. If the
  statement is wrong, a correct proof is worth nothing.
