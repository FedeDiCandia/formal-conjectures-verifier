Closes #5992.

Fills the `sorry` in two `textbook` statements of `FormalConjectures/Wikipedia/DiophantineTuple.lean`:

- `isDiophantineTuple_of_subset` (1 line): both conditions of `IsDiophantineTuple` are pointwise, so they restrict to subsets.
- `noIntegralDiophantineFiveTuple_of_hasUniqueExtensionOfForall` (26 lines): the argument in the docstring. Order a 5-tuple as `g 0 < … < g 4` with `Finset.orderEmbOfFin`; the triple `{g 0, g 1, g 2}` is Diophantine by `isDiophantineTuple_of_subset`, and unique extension applied to `{g 0, g 1, g 2, g 3}` and `{g 0, g 1, g 2, g 4}` gives `g 3 = g 4`, contradicting strict monotonicity.

No statements, definitions, categories or imports change, and no `formal_proof` attribute is added: since #4962 an in-repository proof carries none (as for `erdos_316` and `erdos_399`).

**Checks.** `#print axioms` for both theorems: `[propext, Classical.choice, Quot.sound]`. Both proofs were also checked with [comparator](https://github.com/leanprover/comparator) against the unmodified statements, and `lake build FormalConjectures.Wikipedia.DiophantineTuple` succeeds on current `main` with no new warnings.

**AI assistance.** Both proofs were produced with AI assistance (Claude Opus 5, Anthropic) and verified by machine as above.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
