# Formalising proofs that are already known: measurement and projection

*13 September 2026.*

The task: take from the archive `research solved` or `textbook` problems whose
proof is not formalised, have the agent formalise it, and offer the proofs as pull
requests. This is not research; it is a contribution the archive accepts, provided
the proof is short.

---

## 1. Selection (free)

`scripts/select_formalisations.py` finds **1209 candidates** out of 1790 solved or
textbook problems (excluding those already proved in the archive, those using
`native_decide`, those whose proof depends on a lemma containing `sorry`, and
those with `answer(sorry)`).

Ordering by length of statement was discarded immediately: it put Helfgott,
Deligne and the transcendence of π + e at the top. The ordering instead uses what
the **source** says about the proof (docstring: "easy to see", "trivial",
"Proof: …") against citations of papers, deep theorems, infinite sets and analysis
in the statement. Five bands come out:

| band | candidates | what they are |
|---|---|---|
| A | 16 | the source says the proof is short, nothing hard in the statement |
| B | 43 | textbook, nothing hard |
| C | 360 | solved, no signal in the source |
| D | 153 | proof cited from a paper |
| E | 637 | deep theorem, infinity or analysis, huge computation |

The measured batch was the first 20: the 16 of band A and 4 of band B.

## 2. Measurement

Opus 5, effort `low`, "insistent" instructions, $1 cap per problem.

### What went wrong, and how much it weighs

Overnight the Mac went to sleep (`pmset -g log`: *Maintenance Sleep* every 8–13
minutes, *Clamshell Sleep* at 03:17). Each sleep closed a connection to the API:
**eight interruptions across twelve problems**, plus a crash on the third problem
before the fix. Calls that finished normally lasted 2 to 64 seconds; the
interrupted ones from 11 minutes to over an hour. That night's agent charged every
interruption at its maximum cost (about $0.84) **against the problem's cap too**:
on six problems that charge closed the attempt on its own. Fixed afterwards
(commit 9f215ca); the run was stopped at 03:26.

### The results, one by one

**The cost** is that of the completed calls, without the precautionary charges.

| # | problem | outcome | cost | verifications | note |
|---|---|---|---|---|---|
| 1 | `Erdos770.Nat.Prime.h_eq_add_one` | not closed | $0.79 | 0 | cap spent exploring the definition of `h` |
| 2 | `Erdos770…odd_h_unbounded` | not closed | $0.80 | 0 | likewise |
| 3 | `Erdos295.exists_k` | not closed | $0.83 | 0 | a single call: 32,000 reasoning tokens, no conclusion |
| 4 | `DiophantineTuple.noIntegral…` | **accepted** | $0.13 | 1 | one interruption, survived |
| 5 | `Erdos1148…weaker` | **indeterminate** | $0.16 | 0 | cap consumed by an interruption |
| 6 | `Erdos1000…totient_le` | **accepted** | $0.48 | 4 | |
| 7 | `Erdos707…small_sidon_sets` | **indeterminate** | $0.04 | 0 | cap consumed by an interruption |
| 8 | `Erdos399…cambie` | **indeterminate** | $0.10 | 1 | cap consumed; and already proved elsewhere (PR #5425) |
| 9 | `ComplexityTheory.coP_eq_P` | **indeterminate** | $0.21 | 0 | cap consumed by an interruption |
| 10 | `Erdos1008…lower_bound` | **indeterminate** | $0.00 | 0 | two interruptions, no answer arrived |
| 11 | `Erdos291…steinerberger_generalization` | **indeterminate** | $0.37 | 0 | cap consumed by an interruption |
| 12 | `Erdos649.erdos_649` | **accepted** | $0.24 | 2 | but already proved elsewhere (plby/lean-proofs) |
| 13 | `Erdos180.erdos_180` | not closed | $0.78 | 0 | needs a large counterexample; already proved elsewhere |
| 14 | `ComplexityTheory.P_subset_NP` | interrupted by the stop | $0.17 | 0 | not counted |

### The numbers

- **Attempts with a determinate outcome: 7. Accepted: 3 (43%).**
- **Valid contributions**, that is accepted and not already formalised elsewhere:
  **2 out of 5** determinate attempts on problems still to be done
  (`DiophantineTuple`, `Erdos1000`). Plus `isDiophantineTuple_of_subset`, proved
  by hand for the pull request, which the agent did not attempt.
- **Indeterminate: 6.** They say nothing about the agent and **enter no
  percentage**.
- **Cost of a success**, its own calls: $0.13 to $0.48. **Cost of a determinate
  failure**: the cap, $0.78–0.83.
- **Spend for this work.** Completed calls, certain: $5.12. On the Console: $33
  spent in total. If the spend before this work was $26.71, this work cost about
  **$6.3**. The interrupted calls therefore cost about $1 in all, not the $5.80
  charged for prudence.
- **Cost per valid contribution**: about $6.3 / 2 ≈ **$3**, with the night's
  failures included.

### Why the determinate failures failed

| problem | obstacle | with what certainty |
|---|---|---|
| `Erdos770` (two variants) | probably the Lean engineering: `h` is an `sInf` in `ℕ∞` of a gcd over the image of a `Finset`; 18 explorations in all, no candidate | **not determinable**: the run was launched with `--silenzioso`, so the log has no messages |
| `Erdos295.exists_k` | mathematics: the model was looking for a construction of Egyptian fractions with denominators ≥ N and spent 32,000 reasoning tokens in one call without reaching Lean | from the reasoning summary |
| `Erdos180.erdos_180` | mathematics: it needs a known, large counterexample (plby formalises it in eight files); the model recognised this and said it could not write it within the budget | from the reasoning summary |

No determinate failure is certainly due to Mathlib's API; two might be.

## 2b. Band B, read by hand (13 September)

The 43 band-B docstrings, read one at a time together with the statement and the
definitions it uses. The automatic selection put them all in one band; read, they
divide as follows.

### Worth attempting next, in this order

| # | problem | why | estimated lines |
|---|---|---|---|
| 1 | `Erdos261…borwein_loring` | a finite identity over ℚ, with no archive definitions: by induction on m, $\sum_{k=n+1}^{n+m} k/2^k = (n+2)/2^n - (n+m+2)/2^{n+m}$, and with $n = 2^{m+1}-m-2$ the two sides coincide | 20–30 |
| 2 | `Erdos261…borwein_loring_property` | follows from the previous one: m terms $a_k = n+1+k$, distinct and ≥ 1; what remains is passing from the sum over `Ioc` to the sum over `Fin m` | 20 |
| 3 | `OeisA108306.a_is_invert_transform_case` | the matrix $[[1,5],[1,2]]$ has characteristic polynomial $λ^2-3λ-3$, so $m^2 = 3m + 3I$ and its powers obey the same recurrence $a(k+2) = 3a(k+1)+3a(k)$ | 15 |
| 4 | `Jacobson.jacobson_conjecture_of_comm_ring` | Mathlib has the Krull intersection theorem (`Ideal.iInf_pow_smul_eq_bot_of_le_jacobson`); the work is matching `Ring.jacobson R` with `Ideal.jacobson ⊥`. The risk is the API, not the mathematics | 5–15 |

### Perhaps, after those four

| problem | why | risk |
|---|---|---|
| `OeisA38771.a_n_exists` | Dirichlet is in Mathlib (`Nat.forall_exists_prime_gt_and_eq_mod`): a prime $q \nmid Q_n$ and a prime $p ≡ Q_n \pmod{q^2}$ give $c = p - Q_n$ a multiple of $q^2$, hence composite | 40–60 lines with `ZMod` |
| `OeisA107247.known_prime_and_semiprimes` | pure computation: squares of the "nonacci" sequence up to term 28, and the primality of 5,045,088,967 | the kernel's slowness |
| `OeisA63880.powerful_of_isPrimitiveTerm`, `…a_of_primitive_mul_squarefree` | a short argument (σ and the sum of unitary divisors are multiplicative), but `usigma` is defined only in the file and multiplicativity has to be proved from scratch | 50+ lines |
| `OeisA87719.a_exists` | true because almost all numbers have a small prime factor; it needs an explicit count (for instance $m = 3(2^n+3^n+3)$) | 50–80 lines of counting |

### Not worth attempting (34)

- **Already formalised (2):** `DiophantineTuple.isDiophantineTuple_of_subset` (in
  our own PR); `Erdos649…sampaio` (plby/lean-proofs, `sampaio_counterexample`).
- **Deep theorems the selection did not recognise (20):** the five Poincaré
  variants (dimensions 2, 4, ≥ 5, the smooth version in 3, the smooth
  implication); `RegularPrimes` ×3 (the definition goes through the class number
  of the cyclotomic field; Kummer's criterion); `WolstenholmePrime` ×2
  (congruences on Bernoulli numbers); `Mathoverflow17560` ×2 (real exponents:
  finite differences or transcendence); `Hilbert17` (Motzkin's polynomial);
  `MovingSofa` (Gerver's constants); `Erdos1055` (classes of primes); `Erdos287`
  (a research implication); `Mahler32`; `Green35`; `Erdos945` (equivalence with
  big-O); `Mathoverflow339137` (generating functions).
- **Long constructions (9):** `CongruentNumber` 1 (Fermat's infinite descent);
  `Erdos44` ×2 (Sidon sets of size √N); `Erdos707…singer_construction` (Singer
  perfect difference sets); `WeaklyFirstCountable` (the Arens space); the four on
  quadratic fields (discriminants and classification: it needs the ring of
  integers of ℚ(√d)).
- **Computations out of reach, or no proof indicated (3):**
  `OeisA108301.primes_in_a` (digit sum of $2^{2048}+1$, 617 digits: the archive's
  own tests already use `native_decide`); `OeisA105751` (integer part of the
  imaginary part of a complex product); `OeisA3162.a_is_integer` (a Monthly
  problem whose source does not indicate the proof).

**In summary: 4 to attempt, 5 perhaps, 34 no.** Step 0 was done on the 9: no pull
request mentions them; the one on `sampaio` found plby's proof.

## 3. Projection

**Measured** applies only to band A, and over 7 attempts: an order of magnitude,
not a tight estimate. The rest is **estimated**, and should be read as such.

| band | candidates | rate | where it comes from | expected valid contributions |
|---|---|---|---|---|
| A | 16 | 40% of those attempted; but 3 of the 16 were already formalised elsewhere | **measured** (2/5) | 8 left to attempt: **about 3** |
| B | 43 | 10–25% | **estimated**: textbook but with heavy definitions (regular primes, congruent numbers, number fields) | **4–10** |
| C | 360 | under 5% | **estimated**: no signal of a short proof, and a $1 cap does not buy research proofs | **up to ten**, to be found by reading |
| D, E | 790 | about zero | **estimated**: proofs from papers, or deep theorems | **0** |

**In all, with this machine and a $1 cap: on the order of 10–20 valid
contributions out of 1209 candidates**, nearly all in A and B. The cost rises as
one goes down the bands: about $3 per contribution in A (measured, faults
included), an estimated $5–10 in B, far more in C.

### Is it worth continuing? Yes, but narrowly

1. **Only the rest of band A** (8 problems) when there is credit: about $6, about
   3 proofs. It is the only part with a measured rate.
2. **Band B only after reading the 43 docstrings by hand**, which is free, to
   remove those whose definitions the agent cannot handle on $1.
3. **Not C, D, E** in this configuration: the 9-out-of-11 of the calibration was on
   problems that already had a short archive proof written, and it does not carry
   over.

Two constraints that matter more than the budget:

- **Step 0 before spending.** 3 of the 13 problems attempted were already
  formalised elsewhere, and that is free to discover (open PRs, external proof
  repositories).
- **The human work for each pull request**: the CLA, the issue, the fork, and the
  statement about AI use that has to be one you can sign. Every contribution
  requires your own reading.

---

## 4. Band A, relaunched (13 September, afternoon)

The 7 problems left after step 0 (`Erdos1008…lower_bound` was discarded: it
follows from the external proof of the main theorem). Opus 5, effort `low`, $1
cap, $7 budget; the Mac on mains power, `caffeinate` active, **no network
interruptions**: every outcome is determinate and the cost is the real one.

| problem | outcome | cost | iterations | explorations | verifications |
|---|---|---|---|---|---|
| `Erdos1148…weaker` | **accepted** | $0.22 | 1 | 0 | 1 |
| `Erdos707…small_sidon_sets` | not closed | $0.80 | 10 | 5 | 0 |
| `ComplexityTheory.coP_eq_P` | **accepted** | $0.32 | 15 | 13 | 2 |
| `Erdos291…steinerberger_generalization` | not closed | $0.78 | 12 | 11 | 0 |
| `ComplexityTheory.P_subset_NP` | not closed | $0.78 | 18 | 17 | 0 |
| `Erdos1084…easy_upper_d2` | not closed | $0.76 | 12 | 11 | 0 |
| `Erdos503…lower_bound` | not closed | $0.57 | 5 | 4 | 0 |

- **Accepted: 2 of 7. Spend: $4.23 of $7** (70 calls), with no precautionary
  charges.
- **Cost per accepted proof: $2.11**; the two successes on their own cost $0.22
  and $0.32.
- **The 5 failures all have the same shape:** the cap spent exploring (4 to 17
  explorations), **no candidate submitted** to the verifier. The limit here is the
  $1 cap against the cost of understanding the definitions in Lean (Turing
  machines, plane geometry, Sidon sets), not a proof attempted and got wrong; but
  without candidates one cannot say more.
- **Proof lengths:** `Erdos1148…weaker` 57 lines, above CONTRIBUTING.md's 25–50
  line guidance: a PR would have to decide between including it and linking it
  from a repository of one's own; `coP_eq_P` 11 lines, plus two short auxiliary
  lemmas.

**Band A altogether** (16 candidates): 14 attempts with a determinate outcome, 5
accepted, **4 valid contributions** (`DiophantineTuple`, `Erdos1000…totient_le`,
`Erdos1148…weaker`, `coP_eq_P`) out of 12 determinate attempts on problems not
formalised elsewhere: **33%**.
