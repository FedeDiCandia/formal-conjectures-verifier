# How the verifier works

## The problem it has to solve

A language model writing Lean proofs has many ways to *look* like it has solved a
problem without having done so. The common ones:

| Trick | What it looks like |
|---|---|
| Leave a hole | `theorem goldbach : ... := by sorry` |
| Add an axiom | `axiom miracle : ...`, then use it |
| Trust the compiler | `by native_decide` instead of the kernel |
| Prove something else | a similar but weaker statement |
| Change the definitions | redefine `Prime` so that everything becomes true |
| Switch off the checks | `set_option debug.skipKernelTC true` |

None of these is necessarily bad faith: a model that "wants" to compile
successfully slides into them on its own. The verifier has to catch all of them.

---

## The basic decision: use `comparator`

The judge was not rewritten here. It is
[`comparator`](https://github.com/leanprover/comparator), written by the Lean FRO
for exactly this purpose — validating LLM-produced Lean proofs in the AIMO
competition.

In outline, it:

1. Compiles the **Challenge** module (the archive's original file, untouched).
2. Exports it to a textual format with `lean4export`. It never reads compiled
   `.olean` files: those are memory-mapped and would be an attack surface.
3. Repeats compilation and export for the **Solution** module (the candidate).
4. **Compares the statements** of the requested theorems, and with them every
   declaration the statement depends on. The comparison is on the exported
   syntax tree, not on the text of the file.
5. **Checks the axioms** the proof depends on.
6. **Replays everything through the Lean kernel**, rebuilding the environment
   from scratch.

Step 6 is the decisive one: any trick played at *elaboration* time (macros,
options, tactics) is undone, because in the end the proof term has to pass the
kernel, which is a few thousand lines of code and knows none of those shortcuts.

Step 4 answers both "is the theorem's type identical to the original?" and "does
it redefine the archive's definitions?" — the same question from two sides. A
statement about a redefined `Prime` is not the same statement, however identical
the text.

### How strict the comparison is

Stricter than necessary, which is fine. Tried on a simple case:

```lean
-- original
theorem todo1 : 2 + 2 = 4
-- candidate
theorem todo1 : 2 + 2 = 5 - 1
```

`5 - 1` is *definitionally* equal to `4` (Lean reduces it on its own) and a proof
of the second is a proof of the first. comparator **rejects it anyway**: it wants
the statement to agree as a structure, not merely in meaning.

The practical consequence: **the candidate must reproduce the statement exactly
as it appears in the archive.** That is a reasonable demand, and the agent has to
be told about it.

---

## Architecture: Challenge and Solution are separate modules

```
Challenge = FormalConjectures/ErdosProblems/10.lean   <- the archive, untouched
Solution  = FormalConjectures/_Judge/S0.lean          <- the candidate
```

The candidate file **cannot import the problem's module**: it would declare a
name that already exists and would not compile. So it has to repeat everything it
needs — including any auxiliary `def`s from the original file. And that is
exactly where step 4 bites: if the candidate rewrites one of those `def`s
differently, comparator notices.

The archive is left unchanged: all that is added is a new file in a dedicated
subdirectory, deleted when the verification ends.

---

## What is added around it

### 1. Isolating the compilation (`sandbox.py`)

To judge, comparator has to **compile** the candidate file. Compiling a Lean file
means executing arbitrary code. On Linux comparator isolates compilation with
`landrun`; on macOS `landrun` does not exist.

Verification therefore runs inside `sandbox-exec`, the macOS kernel's isolation
mechanism — deprecated by Apple, but working:

| | |
|---|---|
| network | **denied** |
| writing | **only** the three directories a verification actually touches (measured: the sources of the temporary module and the two branches of `.lake/build` that concern it) plus temporary files |
| reading | denied on `.ssh`, `.aws`, `.gnupg`, the Anthropic credentials and `.env` |

Tested with a candidate that uses `#eval` and `IO.FS.writeFile` to rewrite one of
the archive's `.olean` files. The hostile code itself reports

```
sabotage prevented: operation not permitted (error code: 1)
```

and the file stays byte-for-byte identical. The test includes the **control**:
without the sandbox the same write succeeds — otherwise we would not have shown
that it is the sandbox that stops it.

### 2. Checking the archive's integrity (`fingerprint.py`)

comparator's README lists among its assumptions (number 2) that one must not have
compiled potentially hostile files, since they could have altered the compiled
files the statement is read from. Here verifications run one after another in the
same directory: that assumption has to be **checked**, not taken on trust.

Before and after every verification a fingerprint is taken:

- the **5378 files of the archive** (786 `.olean` plus sources, 126 MB) hashed by
  content, one by one, so that one can say *which* file changed;
- the **111 232 files of Mathlib and its dependencies** (6.8 GB, too many to
  hash) by metadata: path, size, timestamp to the nanosecond.

It costs 0.75 seconds per fingerprint. If anything changed, the verification
returns `ERROR`, not a verdict: a comparison against an altered statement would
mean nothing.

Why **both** defences are needed: comparator exports the Challenge *before*
compiling the Solution, so sabotage would not corrupt the verification in
progress but the ones after it. And the fingerprint does not trust the isolation
mechanism, which Apple has deprecated and which is a different thing on Linux.

### 3. The syntactic pre-scan (`guard.py`)

It reads the file *before* compiling it and rejects constructs that an honest
proof does not need.

This is not what makes the verifier trustworthy — it is a textual filter, and a
textual filter can always be worked around. The real guarantees stay with
comparator and the sandbox. That is why the tests check the layers separately:
that the guard blocks a file, **and** that comparator rejects the same file with
the guard switched off.

The first trial with the agent revealed that **19 constructs were getting
through**. The list now comes from the Lean 4.27 sources
(`Elab/BuiltinCommand.lean`, the `@[builtin_command_elab ...]` declarations) and
from a census of the Mathlib attributes that register executable code:

- commands: `run_meta`, `#eval!`, `simproc`, `register_simp_attr`,
  `declare_syntax_cat`, `notation3`, `meta`, …
- attributes: `@[simproc]`, `@[tactic]`, `@[command_elab]`, `@[term_elab]`,
  `@[norm_num]`, `@[positivity]`, `@[delab]`, `@[init]`, …
- **a structural check** on metaprogramming types (`MetaM`, `CoreM`, `TacticM`,
  `IO`, `Expr`, `Syntax`…): instead of chasing commands one at a time, it rejects
  a file that *speaks the language* of metaprogramming. This is what catches the
  constructs nobody thought of.

Two bugs fixed along the way: `#eval!` slipped through because the exclamation
mark counted as an identifier character in the check, and `meta` was stripped as
a modifier *before* the check, which made `meta def` invisible.

It also found `decide +native`, the new syntax for `native_decide`: it leaves the
same axiom, `Lean.ofReduceBool`. This is not hypothetical — **87 proofs in the
archive use it**, and the verifier rejects them, rightly. An important
consequence: *a problem "already solved in the archive" is not necessarily
solvable under these rules.*

Against false alarms there is a test that applies every new rule to the **674
real problem files** of the archive: the only thing that fires is `+native`,
which is a true positive.

### 4. The treatment of `answer( )`

As explained in [the archive's conventions](01-the-archive.md), the default
option `google.answer = always_true` turns `answer(sorry)` into `True` when the
expected type is `Prop`. For yes/no questions, then, the hole in the statement
**does not exist**: `answer(sorry) ↔ P` is `True ↔ P`, and whoever proves it
proves `P`. No special handling needed.

What remains are the problems whose answer is **not** a proposition (a number, a
set). There the statement really does contain a `sorry`, and the verifier:

- recognises them in advance (the index's `statementHasSorry` field);
- **does not reject them**: it returns the dedicated verdict `NOT_VERIFIABLE`,
  explaining that the problem asks one to *supply an answer*, not merely to
  prove;
- remembers that even with the hole filled, **formal verification is not
  enough**: a tautological answer would pass while being mathematically empty.
  Both the archive's README and comparator's say so explicitly.

Confusing these two cases would be the easiest way to build a system that
"solves" open problems without solving anything.

#### Negated challenges

There is a third case, and it is the most interesting. **563 still-open problems**
of the benchmark tag (634 on the `main` snapshot) are formalised with a
propositional `answer(sorry)`, so the statement Lean sees is
`True ↔ P`: the assertion that the answer is **yes**.

If for one of them the right answer were **no**, the theorem as written would be
false and unprovable. Whoever found the refutation would have no way to have it
verified: they would have to change the statement to `answer(False) ↔ P`, and the
verifier would reject it — rightly, because that is a different statement.

So `verifier/negation.py` generates a second, **trusted** challenge: the same
archive file with `answer(sorry)` replaced by `answer(False)` in the target
theorem's declaration only. Every open problem therefore has two:

| mode | statement | meaning |
|---|---|---|
| `strict` (default) | `True ↔ P` | the answer is yes — the archive's statement |
| `refutation` | `False ↔ P` | the answer is no, i.e. `¬P` |

The essential point is **who generates** that file: we do, mechanically, from the
archive's source. It is not written by whoever proposes the proof — otherwise
they could put anything in it.

Usage:

```bash
./.venv/bin/python verifier/verify.py THEOREM_NAME file.lean --refute
```

How all this is tested without solving an open problem: comparator compares the
**statements** before checking the **axioms**. A candidate whose proof is left as
`sorry` is therefore rejected for `sorryAx` if the statement matches, and for
"statements do not match" if it differs. The reason for the rejection tells you
whether the statements agree, and four combinations suffice to show that the two
challenges are distinct statements and that both work.

### 5. Timeouts and parallelism

Every verification runs under a time limit. When it expires the **whole process
tree** is killed (`comparator` launches `lake`, which launches `lean`): killing
only the parent would leave the children burning CPU.

Parallelism is bounded by a queue of N slots (`FCS_MAX_PARALLEL`). Each
verification takes a slot and uses its own module name (`S0`, `S1`, …), so two
simultaneous verifications do not overwrite each other's files.

---

## What the verifier does NOT guarantee

Set out explicitly:

1. **Isolation on macOS uses `sandbox-exec`, which Apple has deprecated.** It
   works and the tests show it, but it is not a mechanism Apple commits to. On
   Linux the right route is to install the real `landrun` and point `FCS_LANDRUN`
   at it. This is why the fingerprint check exists regardless: it does not trust
   the sandbox.
2. **The fingerprint uses metadata for Mathlib, not content.** Path, size and
   timestamp to the nanosecond: a modification preserving all three would slip
   through. Hashing 6.8 GB on every verification was not practical. The archive's
   own files, which are what the statement is read from, *are* hashed by content.
3. **The correctness of the Lean kernel is an assumption.** comparator can use
   independent external kernels (`external_kernels`) to reduce even this; that is
   not done here yet.
4. **Mathlib's cache is downloaded from the internet.** If that cache contained
   altered definitions, the whole argument collapses. This is the standard
   assumption of anyone using `lake exe cache get`.
5. **The faithfulness of a formalisation cannot be verified.** If the Lean
   statement in the archive does not capture the informal conjecture, a correct
   proof of that statement proves nothing about the conjecture. That is a limit
   of the archive, not of this system, and the archive says so openly.
6. **The guard is a textual filter, and textual filters get worked around.** The
   structural check on metaprogramming types raises the bar a long way, but the
   real defence against code execution is the sandbox, and against logical
   shortcuts it is comparator.
7. **The reference statement depends on how the archive was compiled.** On `main`
   there were two libraries compiling the same files into the same directory with
   different options: the elaborated statement of an `answer(sorry)` problem
   changed according to the last build command. The snapshot now disables the
   surplus library, but the principle stands: **the judge is exactly as reliable
   as the determinism with which the archive is built.** If upstream adds another
   one some day, the same check has to be redone — it can be read off
   `.lake/build/ir/<module>.setup.json`, which records the options the module was
   actually compiled with.
8. **A verification run alongside other work on the same archive can fail for
   reasons that have nothing to do with the candidate.** The fingerprint notices
   and refuses — it fails on the right side — but the refusal is not informative.
   Verifications should be run on their own.
9. **A verified refutation is not an accepted refutation.** The `refutation` mode
   guarantees that `¬P` has been proved correctly, not that the formalisation of
   `P` is faithful to the original conjecture. A result of that kind needs human
   review before anyone believes it.
