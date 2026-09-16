# Selecting the problems for calibration

**Snapshot:** `external/fc-main`, commit `0a8b856c` of `main`, Lean 4.33.1.
**Training cutoff assumed:** May 2026 (declared for `claude-opus-5`).

A problem enters this list only if it satisfies **all** of these:

1. the archive supplies a proof of it;
2. that proof uses only `propext`, `Classical.choice`, `Quot.sound`;
3. that proof, extracted and compiled on its own, is **accepted by `verify.py`**
   on the same snapshot — this is the check that counts, the other two are
   necessary but not sufficient;
4. the statement has no `answer( )` holes.

### How many of the archive's own proofs actually pass

Three passes, each with its log:

| pass | snapshot | candidates | accepted |
|---|---|---|---|
| 1 | `bench-v1` | 23 | 17 ([log](data/verify_bench_v1_23.txt)) |
| 2 | `main` | 6 easy ones | 5 ([log](data/archive_proofs_test_tier.json)) |
| 3 | `main` | the 13 medium and hard candidates | **13** ([log](data/verify_main_13.txt)) |

On the `main` snapshot: **19 candidates, 18 accepted**. The one rejection,
`DiophantineTuple.gibbs_6_tuple`, has a `sorry` in a declaration the target uses:
rightly rejected.

`GottschalkSurjunctivity.isSurjunctive_of_finite` had been discarded as "not
extractable": that was a defect in the extractor (a docstring line beginning with
"endomorphism" was read as an `end`). Fixed; it is now **accepted**.

One operational note worth writing down: in an earlier pass, run while other jobs
were touching the same archive, `SidorenkoConjecture.sidorenko_conjecture.variants.star`
came out REJECTED; in the clean pass it is ACCEPTED. If someone modifies the
archive while the verifier is working, the verifier notices and refuses — it
fails on the right side — but it means **a verification must not be run in
parallel with other work on the same archive**, or you read rejections that have
nothing to do with the proof.

---

## The eleven problems chosen

### Easy (1–3 lines of proof)

| date | lines | risk | problem | kind |
|---|---|---|---|---|
| 2026-09-09 | 1 | LOW | `WieferichMirimanoffPrime.isMirimanoffPrime_and_not_isWieferichPrime_1006003` | a concrete instance at a large prime |
| 2026-08-10 | 2 | LOW | `WilsonPrime.not_isWilsonPrime_seven` | a concrete instance |
| 2026-08-20 | 2 | LOW | `DiophantineTuple.fermat_4_tuple` | **example**: Fermat's quadruple `{1,3,8,120}` is Diophantine |
| 2026-08-15 | 3 | LOW | `ClaudesCycles.not_hasHamiltonianArcDecomposition_one` | **counterexample** |

### Medium (10 lines)

| date | lines | risk | problem |
|---|---|---|---|
| 2026-07-28 | 10 | LOW | `JacobianConjecture.jacobian_conjecture` |
| 2026-08-29 | 10 | LOW | `VizingConjecture.vizing_conjecture.variants.dominationNumber_eq_one` |
| 2026-06-08 | 10 | UNCERTAIN | `SidorenkoConjecture.sidorenko_tree_subsingleton` |

### Hard (15–34 lines)

| date | lines | risk | problem |
|---|---|---|---|
| 2026-07-02 | 15 | LOW | `DeGiorgi.DeGiorgi_one` |
| 2026-08-06 | 16 | LOW | `WrittenOnTheWallII.GraphConjecture65.conjecture65` |
| 2026-08-23 | 20 | LOW ⚠️ | `UnionClosed.union_closed.variants.singleton_mem` |
| 2026-08-29 | 34 | LOW | `SidorenkoConjecture.sidorenko_conjecture.variants.non_bipartite_necessary` (**counterexample**: the triangle is not a Sidorenko graph) |

⚠️ `UnionClosed…singleton_mem` carries a caveat: the theorem already existed in
`bench-v1`, dated 2025-08-04, and the proof was **rewritten**. The recent date is
the rewrite's, not the result's: the model may know the earlier version. It is
the one case where "LOW" should be taken with a pinch of salt.

---

## Memorisation risk

| | |
|---|---|
| LOW (proof added after June 2026) | 10 |
| UNCERTAIN (May–June 2026) | 1 |
| HIGH | 0 |

By comparison, on the `bench-v1` tag **all 17** candidates were high risk, because
the tag is dated 6 May 2026 and the cutoff is May 2026. The snapshot from `main`
was not an optional improvement: it was the precondition for a calibration that
measures the ability to prove rather than the ability to remember.

---

## How the date is measured

With `git log -S` on the longest, most distinctive line of the proof: it finds the
first commit that introduced it into the file. It is not infallible — a rewritten
proof looks more recent than the idea is, which is exactly the `UnionClosed` case
— but it is a measurement, not a guess.

---

## The two rejections, and why

| problem | reason |
|---|---|
| `GottschalkSurjunctivity.isSurjunctive_of_finite` | the extractor cannot isolate the declaration (`unexpected identifier; expected command`) |
| `DiophantineTuple.gibbs_6_tuple` | a `sorry` remains in a declaration the target uses |

---

## Result of the calibration

Total spend **$2.9834** against a hard limit of $15. Model `claude-opus-5`,
effort `medium`, at most 20 iterations per problem.

| level | problem | outcome | iterations | verifications | cost |
|---|---|---|---|---|---|
| easy | `WieferichMirimanoffPrime.isMirimanoffPrime_and_not_isWieferichPrime_1006003` | **solved** | 8 | 1 | $0.1485 |
| easy | `WilsonPrime.not_isWilsonPrime_seven` | **solved** | 1 | 1 | $0.0148 |
| easy | `DiophantineTuple.fermat_4_tuple` | **solved** | 2 | 1 | $0.0497 |
| easy | `ClaudesCycles.not_hasHamiltonianArcDecomposition_one` | **solved** | 1 | 1 | $0.0565 |
| medium | `JacobianConjecture.jacobian_conjecture` | not solved | 20 | 1 | $0.6886 |
| medium | `VizingConjecture.vizing_conjecture.variants.dominationNumber_eq_one` | **solved** | 3 | 1 | $0.0662 |
| medium | `SidorenkoConjecture.sidorenko_tree_subsingleton` | **solved** | 3 | 1 | $0.1639 |
| hard | `DeGiorgi.DeGiorgi_one` | **solved** | 6 | 1 | $0.2572 |
| hard | `WrittenOnTheWallII.GraphConjecture65.conjecture65` | not solved | 13 | 0 | $1.2486 |
| hard | `UnionClosed.union_closed.variants.singleton_mem` | **solved** | 4 | 3 | $0.1524 |
| hard | `SidorenkoConjecture.sidorenko_conjecture.variants.non_bipartite_necessary` | **solved** | 3 | 1 | $0.1370 |

**9 out of 11**: 4 of 4 among the `test` problems, 5 of 7 among the conjecture
variants (`research solved`). The second number is the one that counts.

**Correction (11 September).** One of the two failures was described wrongly at
first, and auditing the reports made it clear: `GraphConjecture65` did **not**
stop because it could not do it, it stopped on our own budget check, at 76% of
its cap ($1.2486 of $1.6444). The check reserved the worst-case cost of the next
call and so refused to proceed with a third of the cap still available. Fixed on
11 September (the stopping threshold went from 6000 to 2000 output tokens): with
the fix that attempt would have had more calls, and we do not know how it would
have gone. It counts as an **indeterminate outcome**, not as a failure of the
model.

So the right reading of the calibration is: 9 solved out of 11, **one real
failure** (`JacobianConjecture`, which ran out of its 20 iterations) and **one
indeterminate**.

Neither failure is systemic. On `JacobianConjecture.jacobian_conjecture` the model
had the right strategy — a known counterexample — and got stuck on the Lean
engineering (`MvPolynomial`, `pderiv`) after 20 iterations. On
`WrittenOnTheWallII.GraphConjecture65.conjecture65` it was building the 17-vertex
graph of the known counterexample when the problem's cap ran out, with 12
explorations and no verification submitted.

The cost model built on these numbers is in [the cost model](06-cost-model.md);
the raw data in [data/calibration_full.json](data/calibration_full.json).
