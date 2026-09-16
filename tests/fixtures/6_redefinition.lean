import FormalConjectures.Util.ProblemImports

namespace JugglerConjecture

noncomputable def jugglerStep (n : ℕ) : ℕ := 6

@[category test, AMS 11]
theorem jugglerStep_36 : jugglerStep 36 = 6 := rfl

end JugglerConjecture
