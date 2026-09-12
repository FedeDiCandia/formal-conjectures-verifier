import FormalConjectures.OEIS.«105020»
import FormalConjectures.Wikipedia.GoldbachConjecture

/-!
# OEIS A105020 and the binary Goldbach conjecture

Proof that `OeisA105020.conjecture` is equivalent to `GoldbachConjecture.goldbach`,
both taken verbatim from the formal-conjectures repository via `type_of%`.
Definitions used: `OeisA105020.a`, `triangularNumber`, `antidiagonalIndex`.
-/

namespace A105020Goldbach

open OeisA105020

/-- `2 · T c = c (c + 1)`. -/
lemma two_mul_triangularNumber (c : ℕ) : 2 * triangularNumber c = c * (c + 1) := by
  have h2 : 2 ∣ (c + 1) * c := by
    have := Nat.even_mul_succ_self c
    rw [Nat.mul_comm] at this
    exact even_iff_two_dvd.mp this
  unfold triangularNumber
  rw [Nat.choose_two_right, Nat.add_sub_cancel, Nat.mul_div_cancel' h2, Nat.mul_comm]

lemma triangularNumber_succ (n : ℕ) : triangularNumber (n + 1) = triangularNumber n + (n + 1) := by
  have h1 := two_mul_triangularNumber n
  have h2 := two_mul_triangularNumber (n + 1)
  have h3 : (n + 1) * (n + 1 + 1) = n * (n + 1) + 2 * (n + 1) := by ring
  omega

/-- Every index lies between `T c` and `T c + c`, where `c` is its antidiagonal. -/
lemma triangularNumber_le_and_le (N : ℕ) :
    triangularNumber (antidiagonalIndex N) ≤ N ∧
      N ≤ triangularNumber (antidiagonalIndex N) + antidiagonalIndex N := by
  have h1 := Nat.sqrt_le (8 * N + 1)
  have h2 := Nat.lt_succ_sqrt (8 * N + 1)
  have ht : 1 ≤ Nat.sqrt (8 * N + 1) := Nat.le_sqrt.mpr (by omega)
  have hc : antidiagonalIndex N = (Nat.sqrt (8 * N + 1) - 1) / 2 := rfl
  set t := Nat.sqrt (8 * N + 1) with ht_def
  set c := antidiagonalIndex N with hc_def
  have hT := two_mul_triangularNumber c
  have hlo : 2 * c + 1 ≤ t := by omega
  have hhi : t ≤ 2 * c + 2 := by omega
  simp only [Nat.succ_eq_add_one] at h2
  constructor
  · nlinarith
  · nlinarith

/-- The indices on antidiagonal `c` are `T c + k` with `k ≤ c`. -/
lemma antidiagonalIndex_triangularNumber_add {c k : ℕ} (hk : k ≤ c) :
    antidiagonalIndex (triangularNumber c + k) = c := by
  have hT := two_mul_triangularNumber c
  have hlo : 2 * c + 1 ≤ Nat.sqrt (8 * (triangularNumber c + k) + 1) := by
    rw [Nat.le_sqrt]; nlinarith
  have hhi : Nat.sqrt (8 * (triangularNumber c + k) + 1) < 2 * c + 3 := by
    rw [Nat.sqrt_lt]; nlinarith
  show (Nat.sqrt (8 * (triangularNumber c + k) + 1) - 1) / 2 = c
  omega

/-- Closed form: `a (T c + k) = (k + 1)(2c + 1 − k)` for `k ≤ c`. -/
theorem a_triangularNumber_add {c k : ℕ} (hk : k ≤ c) :
    a (triangularNumber c + k) = (k + 1) * (2 * c + 1 - k) := by
  simp only [a]
  rw [antidiagonalIndex_triangularNumber_add hk, Nat.add_sub_cancel_left]
  obtain ⟨m, rfl⟩ := Nat.exists_eq_add_of_le hk
  have e1 : k + m - k = m := by omega
  have e2 : 2 * (k + m) + 1 - k = k + 2 * m + 1 := by omega
  rw [e1, e2]
  have e3 : (k + m + 1) ^ 2 = m ^ 2 + (k + 1) * (k + 2 * m + 1) := by ring
  rw [e3, Nat.add_sub_cancel_left]

/-- **Index decomposition**, existence: every `N` is `T c + k` with `k ≤ c`. -/
theorem exists_index_decomposition (N : ℕ) : ∃ c k, k ≤ c ∧ N = triangularNumber c + k := by
  obtain ⟨h1, h2⟩ := triangularNumber_le_and_le N
  exact ⟨antidiagonalIndex N, N - triangularNumber (antidiagonalIndex N), by omega, by omega⟩

/-- **Index decomposition**, uniqueness. -/
theorem index_decomposition_unique {c k c' k' : ℕ} (hk : k ≤ c) (hk' : k' ≤ c')
    (h : triangularNumber c + k = triangularNumber c' + k') : c = c' ∧ k = k' := by
  have e : c = c' := by rw [← antidiagonalIndex_triangularNumber_add hk, h, antidiagonalIndex_triangularNumber_add hk']
  subst e
  exact ⟨rfl, by omega⟩

/-- **The formula `a(N) = d (2s − d)`**, with `s = c + 1` and `d = k + 1`. -/
theorem a_eq_d_mul {c k : ℕ} (hk : k ≤ c) :
    a (triangularNumber c + k) = (k + 1) * (2 * (c + 1) - (k + 1)) := by
  rw [a_triangularNumber_add hk]
  congr 1
  omega

lemma a_triangularNumber (n : ℕ) : a (triangularNumber n) = 2 * n + 1 := by
  simpa using a_triangularNumber_add (Nat.zero_le n)

/-- **Index lemma**: the hypotheses of the conjecture force the canonical indices. -/
theorem hypotheses_force_canonical_indices {n i j : ℕ} (hn : 1 ≤ n) (hi : a i = 2 * n + 1)
    (hj : a j = 2 * n + 3) (hij : j = i + n + 1) :
    i = triangularNumber n ∧ j = triangularNumber (n + 1) := by
  obtain ⟨c, k, hk, rfl⟩ := exists_index_decomposition i
  obtain ⟨c', k', hk', rfl⟩ := exists_index_decomposition j
  obtain ⟨m, rfl⟩ := Nat.exists_eq_add_of_le hk
  obtain ⟨m', rfl⟩ := Nat.exists_eq_add_of_le hk'
  rw [a_triangularNumber_add hk] at hi
  rw [a_triangularNumber_add hk'] at hj
  have e1 : 2 * (k + m) + 1 - k = k + 2 * m + 1 := by omega
  have e2 : 2 * (k' + m') + 1 - k' = k' + 2 * m' + 1 := by omega
  rw [e1] at hi
  rw [e2] at hj
  have hkm : 1 ≤ k + m := by
    rcases Nat.eq_zero_or_pos (k + m) with h | h
    · have hk0 : k = 0 := by omega
      have hm0 : m = 0 := by omega
      rw [hk0, hm0] at hi
      norm_num at hi
      omega
    · exact h
  have t1 := two_mul_triangularNumber (k + m)
  have t2 := two_mul_triangularNumber (k' + m')
  have Hi : ((k : ℤ) + 1) * (k + 2 * m + 1) = 2 * n + 1 := by exact_mod_cast hi
  have Hj : ((k' : ℤ) + 1) * (k' + 2 * m' + 1) = 2 * n + 3 := by exact_mod_cast hj
  have Hij : (triangularNumber (k' + m') : ℤ) + k' =
      (triangularNumber (k + m) : ℤ) + k + n + 1 := by exact_mod_cast hij
  have T1 : 2 * (triangularNumber (k + m) : ℤ) = ((k : ℤ) + m) * (k + m + 1) := by
    exact_mod_cast t1
  have T2 : 2 * (triangularNumber (k' + m') : ℤ) = ((k' : ℤ) + m') * (k' + m' + 1) := by
    exact_mod_cast t2
  -- (F) and (E) of the written proof, with r = m, r' = m', d = k + 1, d' = k' + 1
  have F : (m' : ℤ) * m' + k' = ((k : ℤ) + m) * (k + m + 1) + 2 * k + m' := by
    linear_combination 2 * Hij - T2 + T1 - Hj
  have E : ((k' : ℤ) + 1) * (k' + 2 * m' + 1) = ((k : ℤ) + 1) * (k + 2 * m + 1) + 2 := by
    linear_combination Hj - Hi
  have hk0' : (0 : ℤ) ≤ k := by positivity
  have hm0' : (0 : ℤ) ≤ m := by positivity
  have hk'0 : (0 : ℤ) ≤ k' := by positivity
  have hm'0 : (0 : ℤ) ≤ m' := by positivity
  have hkmZ : (1 : ℤ) ≤ k + m := by exact_mod_cast hkm
  have hk_zero : k = 0 := by
    rcases lt_trichotomy m' (k + m + 1) with h | h | h
    · -- case r' ≤ s − 1: impossible
      exfalso
      have hle : (m' : ℤ) ≤ k + m := by
        have : m' ≤ k + m := by omega
        exact_mod_cast this
      have hprod : (0 : ℤ) ≤ ((k : ℤ) + m - m') * (k + m + m' - 1) :=
        mul_nonneg (by linarith) (by linarith)
      have hexp : ((k : ℤ) + m - m') * (k + m + m' - 1)
          = ((k : ℤ) + m) * (k + m + 1) - m' * m' - 2 * (k + m) + m' := by ring
      have hk'ge : (4 * k + 2 * m : ℤ) ≤ k' := by linarith
      have h1 : (4 * k + 2 * m + 1 : ℤ) ≤ k' + 1 := by linarith
      have h2 : (k' + 1 : ℤ) ≤ k' + 2 * m' + 1 := by linarith
      have hsq : (4 * k + 2 * m + 1 : ℤ) * (4 * k + 2 * m + 1)
          ≤ ((k' : ℤ) + 1) * (k' + 2 * m' + 1) :=
        mul_le_mul h1 (h1.trans h2) (by linarith) (by linarith)
      have hsq2 : ((k : ℤ) + m) * 1 ≤ (k + m) * (k + m) :=
        mul_le_mul_of_nonneg_left hkmZ (by linarith)
      have hkk : (0 : ℤ) ≤ k * k := mul_nonneg hk0' hk0'
      have hkm' : (0 : ℤ) ≤ k * m := mul_nonneg hk0' hm0'
      linarith
    · -- case r' = s: forces d = 1
      have hZ : (m' : ℤ) = k + m + 1 := by exact_mod_cast h
      rw [hZ] at F E
      have hk'2 : (k' : ℤ) = 2 * k := by linear_combination F
      rw [hk'2] at E
      have hprod : (k : ℤ) * (7 * k + 2 * m + 8) = 0 := by linear_combination E
      have hpos : (0 : ℤ) ≤ k * (7 * k + 2 * m) := mul_nonneg hk0' (by linarith)
      have hsplit : (k : ℤ) * (7 * k + 2 * m + 8) = k * (7 * k + 2 * m) + 8 * k := by ring
      have hk0 : (k : ℤ) = 0 := by linarith
      exact_mod_cast hk0
    · -- case r' ≥ s + 1: impossible
      exfalso
      have hge : (k : ℤ) + m + 2 ≤ m' := by
        have : k + m + 2 ≤ m' := by omega
        exact_mod_cast this
      have hprod : (0 : ℤ) ≤ ((m' : ℤ) - (k + m + 2)) * (m' + k + m + 1) :=
        mul_nonneg (by linarith) (by linarith)
      have hexp : ((m' : ℤ) - (k + m + 2)) * (m' + k + m + 1)
          = m' * m' - m' - ((k : ℤ) + m) * (k + m + 1) - 2 * (k + m + 1) := by ring
      linarith
  subst hk_zero
  have hmn : m = n := by
    norm_num at hi
    omega
  subst hmn
  constructor
  · simp
  · rw [triangularNumber_succ]
    simp only [Nat.zero_add, Nat.add_zero] at hij
    omega

/-- If `p * q` is a semiprime and `p, q ≥ 2`, then both factors are prime. -/
lemma primes_of_semiprime_mul {p q : ℕ} (hp : 2 ≤ p) (hq : 2 ≤ q)
    (h : (p * q).IsSemiprime) : p.Prime ∧ q.Prime := by
  obtain ⟨_, h2⟩ := h
  rw [ArithmeticFunction.cardFactors_mul (by omega) (by omega)] at h2
  have hp1 : ArithmeticFunction.cardFactors p ≠ 0 := by
    rw [Ne, ArithmeticFunction.cardFactors_eq_zero_iff_eq_zero_or_one]; omega
  have hq1 : ArithmeticFunction.cardFactors q ≠ 0 := by
    rw [Ne, ArithmeticFunction.cardFactors_eq_zero_iff_eq_zero_or_one]; omega
  exact ⟨ArithmeticFunction.cardFactors_eq_one_iff_prime.mp (by omega),
    ArithmeticFunction.cardFactors_eq_one_iff_prime.mp (by omega)⟩

/-- **The equivalence**, between the two repository statements taken verbatim. -/
theorem conjecture_iff_goldbach :
    (type_of% @OeisA105020.conjecture) ↔ (type_of% @GoldbachConjecture.goldbach) := by
  show (∀ (n i j : ℕ), 1 ≤ n → a i = 2 * n + 1 → a j = 2 * n + 3 → j = i + n + 1 →
      ∃ k, i < k ∧ k < j ∧ (a k).IsSemiprime) ↔
    (True ↔ ∀ n : ℕ, 2 < n → Even n → ∃ p q, Prime p ∧ Prime q ∧ n = p + q)
  rw [true_iff]
  constructor
  · intro H m hm hev
    obtain ⟨r, hr⟩ := hev
    obtain ⟨n, rfl⟩ : ∃ n, m = 2 * n + 2 := ⟨r - 1, by omega⟩
    have hn : 1 ≤ n := by omega
    obtain ⟨k, hk1, hk2, hsp⟩ := H n (triangularNumber n) (triangularNumber (n + 1)) hn
      (a_triangularNumber n) (a_triangularNumber (n + 1)) (triangularNumber_succ n)
    rw [triangularNumber_succ] at hk2
    obtain ⟨κ, rfl⟩ := Nat.exists_eq_add_of_lt hk1
    have hκ : κ + 1 ≤ n := by omega
    rw [show triangularNumber n + κ + 1 = triangularNumber n + (κ + 1) by omega,
      a_triangularNumber_add hκ] at hsp
    have hq : 2 * n + 1 - (κ + 1) = 2 * n - κ := by omega
    rw [hq] at hsp
    obtain ⟨hp', hq'⟩ := primes_of_semiprime_mul (by omega) (by omega) hsp
    exact ⟨κ + 1 + 1, 2 * n - κ, Nat.prime_iff.mp hp', Nat.prime_iff.mp hq', by omega⟩
  · intro G n i j hn hi hj hij
    obtain ⟨rfl, rfl⟩ := hypotheses_force_canonical_indices hn hi hj hij
    obtain ⟨p, q, hp, hq, hpq⟩ := G (2 * n + 2) (by omega) ⟨n + 1, by ring⟩
    rw [← Nat.prime_iff] at hp hq
    wlog hle : p ≤ q generalizing p q
    · exact this q p hq hp (by omega) (by omega)
    have hp2 := hp.two_le
    refine ⟨triangularNumber n + (p - 1), by omega, ?_, ?_⟩
    · rw [triangularNumber_succ]; omega
    · rw [a_triangularNumber_add (by omega)]
      have e : 2 * n + 1 - (p - 1) = q := by omega
      rw [e, show p - 1 + 1 = p by omega]
      exact Nat.Prime.mul_isAlmostPrime_two hp hq

end A105020Goldbach

