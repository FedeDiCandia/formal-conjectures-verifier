Closes #5993.

Fills the `sorry` in `erdos_1000.variants.totient_le` ("It is trivial that $\phi_A(k)\geq \phi(n_k)$"), for the statement introduced in #5837. The map sending `a` to itself, and `0` to `n k`, injects the residues coprime to `n k` into the set counted by `phiSeq n k`: a coprime residue has reduced denominator `n k`, and `n k ∤ n j` for `j < k` because `0 < n 0 ≤ n j < n k` (this is where `hn0` is used). 35 lines, no new imports; statement, definitions and category unchanged, and no `formal_proof` attribute, since the proof lives in the file (#4962).

**Checks.** `#print axioms`: `[propext, Classical.choice, Quot.sound]`. Also checked with [comparator](https://github.com/leanprover/comparator) against the statement, and `lake build FormalConjectures.ErdosProblems.«1000»` succeeds on current `main` with no new warnings.

**AI assistance.** The proof was produced with AI assistance (Claude Opus 5, Anthropic) and verified by machine as above.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
