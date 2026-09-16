import FormalConjectures.OEIS.«105020»
import FormalConjectures.Wikipedia.GoldbachConjecture

/-!
# Sfida: A105020 e Goldbach

The statements to be verified, and nothing else. Every proof is `sorry`: the
verifier checks that the candidate proves **exactly these**. The two statements
definizioni `triangularNumber`, `antidiagonalIndex`, `a` e i due enunciati
`OeisA105020.conjecture` and `GoldbachConjecture.goldbach` are the archive's,
not rewritten.
-/

namespace A105020Goldbach

open OeisA105020

/-- Every index is `T c + k` with `k ≤ c`. -/
theorem parametrizzazione (N : ℕ) : ∃ c k, k ≤ c ∧ N = triangularNumber c + k := by
  sorry

/-- … and in only one way. -/
theorem parametrizzazione_unica {c k c' k' : ℕ} (hk : k ≤ c) (hk' : k' ≤ c')
    (h : triangularNumber c + k = triangularNumber c' + k') : c = c' ∧ k = k' := by
  sorry

/-- `a(N) = d (2s − d)` with `s = c + 1`, `d = k + 1`. -/
theorem formula_ds {c k : ℕ} (hk : k ≤ c) :
    a (triangularNumber c + k) = (k + 1) * (2 * (c + 1) - (k + 1)) := by
  sorry

/-- The conjecture's hypotheses force the canonical indices. -/
theorem coppie_canoniche {n i j : ℕ} (hn : 1 ≤ n) (hi : a i = 2 * n + 1)
    (hj : a j = 2 * n + 3) (hij : j = i + n + 1) :
    i = triangularNumber n ∧ j = triangularNumber (n + 1) := by
  sorry

/-- L'equivalenza fra i due enunciati dell'archivio. -/
theorem equivalenza_goldbach :
    (type_of% @OeisA105020.conjecture) ↔ (type_of% @GoldbachConjecture.goldbach) := by
  sorry

end A105020Goldbach
