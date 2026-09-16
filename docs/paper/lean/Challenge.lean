import FormalConjectures.OEIS.«105020»
import FormalConjectures.Wikipedia.GoldbachConjecture

/-!
# Challenge: OEIS A105020 and the binary Goldbach conjecture

Statements only; every proof is `sorry`. comparator checks that the solution proves
exactly these statements. `triangularNumber`, `antidiagonalIndex`, `a`,
`OeisA105020.conjecture` and `GoldbachConjecture.goldbach` are the repository's own.
-/

namespace A105020Goldbach

open OeisA105020

/-- Index decomposition: every index is `T c + k` with `k ≤ c`, ... -/
theorem exists_index_decomposition (N : ℕ) :
    ∃ c k, k ≤ c ∧ N = triangularNumber c + k := by
  sorry

/-- Index decomposition: ... in exactly one way, ... -/
theorem index_decomposition_unique {c k c' k' : ℕ} (hk : k ≤ c) (hk' : k' ≤ c')
    (h : triangularNumber c + k = triangularNumber c' + k') : c = c' ∧ k = k' := by
  sorry

/-- Index decomposition: ... and then `c` is the antidiagonal index. -/
theorem antidiagonalIndex_triangularNumber_add {c k : ℕ} (hk : k ≤ c) :
    antidiagonalIndex (triangularNumber c + k) = c := by
  sorry

/-- Closed form: `a (T c + k) = (k + 1)(2c + 1 − k)` for `k ≤ c`. -/
theorem a_triangularNumber_add {c k : ℕ} (hk : k ≤ c) :
    a (triangularNumber c + k) = (k + 1) * (2 * c + 1 - k) := by
  sorry

/-- Closed form: `a(N) = d (2s − d)` with `s = c + 1` and `d = k + 1`. -/
theorem a_eq_d_mul {c k : ℕ} (hk : k ≤ c) :
    a (triangularNumber c + k) = (k + 1) * (2 * (c + 1) - (k + 1)) := by
  sorry

/-- Closed form: `a (T n) = 2n + 1`. -/
theorem a_triangularNumber (n : ℕ) : a (triangularNumber n) = 2 * n + 1 := by
  sorry

/-- Values and factorizations: the indices where `a` takes a given value. -/
theorem a_eq_iff_exists_factorization (N v : ℕ) :
    a N = v ↔ ∃ d e, 1 ≤ d ∧ d ≤ e ∧ d % 2 = e % 2 ∧ v = d * e ∧
      N = triangularNumber ((d + e) / 2 - 1) + (d - 1) := by
  sorry

/-- Index lemma: the hypotheses of the conjecture force the canonical indices. -/
theorem hypotheses_force_canonical_indices {n i j : ℕ} (hn : 1 ≤ n)
    (hi : a i = 2 * n + 1) (hj : a j = 2 * n + 3) (hij : j = i + n + 1) :
    i = triangularNumber n ∧ j = triangularNumber (n + 1) := by
  sorry

/-- Main theorem: the equivalence between the two repository statements. -/
theorem conjecture_iff_goldbach :
    (type_of% @OeisA105020.conjecture) ↔ (type_of% @GoldbachConjecture.goldbach) := by
  sorry

end A105020Goldbach
