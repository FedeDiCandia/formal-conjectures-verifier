# Proofs prepared for the formal-conjectures archive

Four proofs in three files, each accepted by the verifier: the statement is the
archive's own, the proof depends only on `propext`, `Classical.choice` and
`Quot.sound`, and `lake build` of the module it belongs to succeeds with no new
warnings.

| directory | theorems | proof lines | state |
|---|---|---|---|
| `DiophantineTuple/` | `isDiophantineTuple_of_subset`, `noIntegralDiophantineFiveTuple_of_hasUniqueExtensionOfForall` | 1 and 26 | issue [#5992](https://github.com/google-deepmind/formal-conjectures/issues/5992) open and assigned; pull request prepared, text in `pr_body.md`, patch in `proofs.patch` |
| `Erdos1000/` | `erdos_1000.variants.totient_le` | 35 | issue [#5993](https://github.com/google-deepmind/formal-conjectures/issues/5993) open and assigned; pull request prepared, patch in `totient_le_main.patch`, rebuilt for the statement that PR #5837 introduced on 13 September |

Two further proofs from the same campaign have no pull request drafted yet:
`Erdos1148…weaker` (57 lines, above CONTRIBUTING.md's 25–50 line guidance, so it
may belong in an external repository) and `ComplexityTheory.coP_eq_P` (11 lines
plus two short lemmas, in a file that has since moved on `main`).

`candidates/` holds the self-contained files that were submitted to the verifier.
The `DiophantineTuple` one uses the archive's own `isDiophantineTuple_of_subset`
in place of the auxiliary lemma the agent wrote, so that the pull request does not
introduce a duplicate.

## The `formal_proof` attribute

For a proof written **inside** the archive's file, the correct attribute is
**none**. Since PR #4962 (18 August 2026) a linter warns when a theorem carrying
`formal_proof` has a proof other than `sorry`: the attribute marks a proof that
lives *elsewhere*, on a statement that stays `sorry` in the archive. The same PR
removed the attribute from `erdos_316` and `erdos_399`, which have their proofs in
the file.

The alternative, for long proofs (CONTRIBUTING.md: beyond 25–50 lines), is to
leave the `sorry`, put the proof in a repository of one's own and add
`formal_proof using lean4 at "<stable link to a commit>"`.

## Step 0: has someone already formalised it?

Checked on 13 September 2026, and again before preparing the pull requests:

- the files on `main` are identical to the snapshot `0a8b856c`, the theorems are
  still `sorry`;
- no pull request, open or closed, mentions `noIntegralDiophantineFiveTuple` or
  `isDiophantineTuple_of_subset`;
- for `totient_le`: no pull request proves it; the external proofs of Erdős 1000
  (plby/lean-proofs, Jayyhk/erdos-lean) prove the main statement, not this
  variant. PR #5837 touched it by changing its statement, and the proof here was
  rebuilt against the merged version.

This step is free and it pays: 3 of the 13 problems attempted in the first round
turned out to be formalised already.

## Before opening anything

1. Sign the Google CLA (<https://cla.developers.google.com/>).
2. Open the issue and have it assigned.
3. Fork, branch, `git apply` the patch, `lake build`.
4. Open the pull request with the text of `pr_body.md`, linked to the issue.

Each pull request declares that the proof was produced with AI assistance and
says how it was verified.
