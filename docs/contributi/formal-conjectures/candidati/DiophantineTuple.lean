import FormalConjecturesUtil

namespace DiophantineTuple

variable {R : Type*} [Semiring R]

def IsDiophantineTuple (s : Finset R) : Prop :=
  (∀ x ∈ s, x ≠ 0) ∧
  ∀ x ∈ s, ∀ y ∈ s, x ≠ y → IsSquare (x * y + 1)

abbrev IsIntegralDiophantineTuple (s : Finset ℕ) : Prop := IsDiophantineTuple (R := ℕ) s

abbrev NoIntegralDiophantineFiveTuple := ¬∃ t, IsIntegralDiophantineTuple t ∧ t.card = 5

def regularExtension (a b c : ℕ) : ℕ :=
  a + b + c + 2 * a * b * c + 2 * Nat.sqrt ((a * b + 1) * (a * c + 1) * (b * c + 1))

def HasUniqueExtension (a b c : ℕ) : Prop :=
  (IsIntegralDiophantineTuple { a, b, c }) ∧
  ∀ d : ℕ, (IsIntegralDiophantineTuple { a, b, c, d }) → max a (max b c) < d →
    d = regularExtension a b c

abbrev HasUniqueExtensionOfForall :=
  ∀ a b c : ℕ, ({a, b, c} : Finset ℕ).card = 3 → IsIntegralDiophantineTuple {a, b, c} →
    HasUniqueExtension a b c

theorem isDiophantineTuple_of_subset (s t : Finset R) (h1 : IsDiophantineTuple t)
    (h2 : s ⊆ t) : IsDiophantineTuple s :=
  ⟨fun x hx => h1.1 x (h2 hx), fun x hx y hy hxy => h1.2 x (h2 hx) y (h2 hy) hxy⟩

@[category textbook, AMS 11]
theorem noIntegralDiophantineFiveTuple_of_hasUniqueExtensionOfForall :
    HasUniqueExtensionOfForall → NoIntegralDiophantineFiveTuple := by
  rintro h ⟨t, ht, hcard⟩
  set g := t.orderEmbOfFin hcard with hg
  have hm : StrictMono g := (t.orderEmbOfFin hcard).strictMono
  have hmem : ∀ i, g i ∈ t := fun i => t.orderEmbOfFin_mem hcard i
  have h01 : g 0 < g 1 := hm (by decide)
  have h12 : g 1 < g 2 := hm (by decide)
  have h23 : g 2 < g 3 := hm (by decide)
  have h34 : g 3 < g 4 := hm (by decide)
  have hs3 : ({g 0, g 1, g 2} : Finset ℕ) ⊆ t := by
    simp [Finset.insert_subset_iff, hmem]
  have hs4 : ({g 0, g 1, g 2, g 3} : Finset ℕ) ⊆ t := by
    simp [Finset.insert_subset_iff, hmem]
  have hs4' : ({g 0, g 1, g 2, g 4} : Finset ℕ) ⊆ t := by
    simp [Finset.insert_subset_iff, hmem]
  have hc3 : ({g 0, g 1, g 2} : Finset ℕ).card = 3 :=
    Finset.card_eq_three.mpr ⟨_, _, _, h01.ne, (h01.trans h12).ne, h12.ne, rfl⟩
  obtain ⟨-, hu⟩ := h (g 0) (g 1) (g 2) hc3 (isDiophantineTuple_of_subset (R := ℕ) _ _ ht hs3)
  have e1 : g 3 = regularExtension (g 0) (g 1) (g 2) := by
    refine hu _ (isDiophantineTuple_of_subset (R := ℕ) _ _ ht hs4) ?_
    simp only [max_eq_right h12.le]
    omega
  have e2 : g 4 = regularExtension (g 0) (g 1) (g 2) := by
    refine hu _ (isDiophantineTuple_of_subset (R := ℕ) _ _ ht hs4') ?_
    simp only [max_eq_right h12.le]
    omega
  omega

end DiophantineTuple
