import FormalConjectures.Util.ProblemImports

namespace JugglerConjecture

noncomputable def jugglerStep (n : ℕ) : ℕ :=
  if Even n then ⌊(n : ℝ) ^ (1/2 : ℝ)⌋₊ else ⌊(n : ℝ) ^ (3/2 : ℝ)⌋₊

@[category test, AMS 11]
theorem jugglerStep_36 : jugglerStep 36 = 6 := by
  sorry

end JugglerConjecture
