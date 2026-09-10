import FormalConjectures.Util.ProblemImports

namespace JugglerConjecture

noncomputable def jugglerStep (n : ℕ) : ℕ :=
  if Even n then ⌊(n : ℝ) ^ (1/2 : ℝ)⌋₊ else ⌊(n : ℝ) ^ (3/2 : ℝ)⌋₊

@[category test, AMS 11]
theorem jugglerStep_36 : jugglerStep 36 = 6 := by
  have h : (36 : ℕ) % 2 = 0 := by native_decide
  unfold jugglerStep
  norm_num [←Real.sqrt_eq_rpow]

end JugglerConjecture
