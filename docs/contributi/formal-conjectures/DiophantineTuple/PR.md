# Bozza — NON inviata

Destinatari: i manutentori di google-deepmind/formal-conjectures.
Da fare prima, a mano (CONTRIBUTING.md): firmare il Google CLA; aprire la issue qui sotto;
fare il fork, creare il ramo, applicare `proofs.patch`, `lake build`; poi aprire la PR
collegata alla issue.

---

## Issue

**Title:** Prove `isDiophantineTuple_of_subset` and `noIntegralDiophantineFiveTuple_of_hasUniqueExtensionOfForall`

Both statements in `FormalConjectures/Wikipedia/DiophantineTuple.lean` are `textbook` results
whose proofs are short (the second one's docstring already sketches the argument), and both are
currently `sorry`. I plan to open a PR filling them in, with a 1-line and a 26-line proof. No
statement, definition or category changes.

---

## Pull request

**Branch:** `prove-diophantine-tuple-textbook`

**Title:** feat(Wikipedia/DiophantineTuple): prove two textbook statements

**Body:**

Closes #<issue>.

Fills the `sorry` in two `textbook` statements of `FormalConjectures/Wikipedia/DiophantineTuple.lean`:

- `isDiophantineTuple_of_subset` (1 line): both conditions of `IsDiophantineTuple` are
  pointwise, so they restrict to subsets.
- `noIntegralDiophantineFiveTuple_of_hasUniqueExtensionOfForall` (26 lines): this is the argument
  in the docstring. Order a 5-tuple as `g 0 < … < g 4` with `Finset.orderEmbOfFin`; the triple
  `{g 0, g 1, g 2}` is Diophantine by `isDiophantineTuple_of_subset`, and unique extension applied
  to `{g 0, g 1, g 2, g 3}` and `{g 0, g 1, g 2, g 4}` gives `g 3 = g 4`, contradicting strict
  monotonicity.

No statements, definitions, categories or imports change, and no `formal_proof` attribute is
added: the proofs live in the file, and since #4962 an in-repository proof carries no
`formal_proof` annotation (as for `erdos_316` and `erdos_399`).

**Checks.**
- `#print axioms` for both theorems: `[propext, Classical.choice, Quot.sound]`.
- Both proofs were also checked with [comparator](https://github.com/leanprover/comparator)
  against the unmodified statements at commit `0a8b856c`, and the file is unchanged on `main`
  since then.
- I searched for existing formalizations before opening this: no open or closed PR mentions
  these declarations, and I found no proof in the external Lean repositories linked from the
  archive.

**AI assistance.** Following the Mathlib convention on AI use: the proof of the second theorem
was produced by an AI model (Claude Opus 5, Anthropic) in an automated attempt, then checked as
above. I have read and understood the proof.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
