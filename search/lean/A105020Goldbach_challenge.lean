import FormalConjectures.OEIS.«105020»
import FormalConjectures.Wikipedia.GoldbachConjecture

/-!
# Sfida: A105020 e Goldbach

Gli enunciati da verificare, e nient'altro. Ogni dimostrazione è `sorry`: il
verificatore controlla che il candidato dimostri **esattamente questi**. Le
definizioni `triangularNumber`, `antidiagonalIndex`, `a` e i due enunciati
`OeisA105020.conjecture` e `GoldbachConjecture.goldbach` sono quelli dell'archivio,
non riscritti.
-/

namespace A105020Goldbach

open OeisA105020

/-- Ogni indice è `T c + k` con `k ≤ c`. -/
theorem parametrizzazione (N : ℕ) : ∃ c k, k ≤ c ∧ N = triangularNumber c + k := by
  sorry

/-- ... e in un solo modo. -/
theorem parametrizzazione_unica {c k c' k' : ℕ} (hk : k ≤ c) (hk' : k' ≤ c')
    (h : triangularNumber c + k = triangularNumber c' + k') : c = c' ∧ k = k' := by
  sorry

/-- `a(N) = d (2s − d)` con `s = c + 1`, `d = k + 1`. -/
theorem formula_ds {c k : ℕ} (hk : k ≤ c) :
    a (triangularNumber c + k) = (k + 1) * (2 * (c + 1) - (k + 1)) := by
  sorry

/-- Le ipotesi della congettura forzano gli indici canonici. -/
theorem coppie_canoniche {n i j : ℕ} (hn : 1 ≤ n) (hi : a i = 2 * n + 1)
    (hj : a j = 2 * n + 3) (hij : j = i + n + 1) :
    i = triangularNumber n ∧ j = triangularNumber (n + 1) := by
  sorry

/-- L'equivalenza fra i due enunciati dell'archivio. -/
theorem equivalenza_goldbach :
    (type_of% @OeisA105020.conjecture) ↔ (type_of% @GoldbachConjecture.goldbach) := by
  sorry

end A105020Goldbach
