import FormalConjecturesUtil

open Filter Topology

namespace Erdos1000

def phiSeq (n : ℕ → ℕ) (k : ℕ) : ℕ :=
  ((Finset.Icc 1 (n k)).filter fun m => ∀ j < k, ¬ (n k / Nat.gcd m (n k)) ∣ n j).card

noncomputable def phiAvg (n : ℕ → ℕ) (N : ℕ) : ℝ :=
  (∑ k ∈ Finset.range N, (phiSeq n k : ℝ) / (n k : ℝ)) / (N : ℝ)

/-- (enunciato della PR #5837) It is trivial that $\phi_A(k)\geq \phi(n_k)$. -/
@[category research solved, AMS 11]
theorem erdos_1000.variants.totient_le (n : ℕ → ℕ) (hn : StrictMono n) (hn0 : 0 < n 0)
    (k : ℕ) :
    (n k).totient ≤ phiSeq n k := by
  sorry

end Erdos1000
