#!/usr/bin/env python3
"""Generate lean/MeaningChecks.lean from lean/Challenge.lean.

Section 1 of the output restates every challenge statement as a `Prop`, extracted
from the challenge text rather than copied by hand, and prints it with full names.
The remaining sections check the meaning of the two repository statements and of
the definitions they use.
"""
import re
from pathlib import Path

PUB = Path(__file__).resolve().parent.parent
challenge = (PUB / "lean" / "Challenge.lean").read_text(encoding="utf-8")

defs, names = [], []
for m in re.finditer(r"theorem\s+(\S+)(.*?):=\s*by", challenge, re.S):
    name, signature = m.group(1), m.group(2)
    depth, cut = 0, None
    for i, ch in enumerate(signature):
        if ch in "([{⟨":
            depth += 1
        elif ch in ")]}⟩":
            depth -= 1
        elif ch == ":" and depth == 0:
            cut = i
            break
    binders = signature[:cut].strip()
    statement = " ".join(signature[cut + 1:].split())
    body = f"∀ {binders}, {statement}" if binders else statement
    defs.append(f"def P_{name} : Prop := {body}")
    names.append(name)

text = f'''import FormalConjectures.OEIS.«105020»
import FormalConjectures.Wikipedia.GoldbachConjecture

/-!
# Meaning checks for the A105020 / Goldbach challenge

comparator certifies that `Solution.lean` proves exactly the statements of
`Challenge.lean`. This file checks that those statements mean what the note says.
Every declaration must compile, and the `#print axioms` lines at the end must report
only standard axioms.

Section 1 is generated from `Challenge.lean` by `make_meaning_checks.py`.
-/

namespace A105020Goldbach.MeaningChecks

open OeisA105020

/-! ## 1. The challenge statements, printed with full names -/

{chr(10).join(defs)}

end A105020Goldbach.MeaningChecks

set_option pp.fullNames true in
set_option pp.numericTypes true in
{(chr(10) + "set_option pp.fullNames true in" + chr(10) + "set_option pp.numericTypes true in" + chr(10)).join(f"#print A105020Goldbach.MeaningChecks.P_{n}" for n in names)}

namespace A105020Goldbach.MeaningChecks

open OeisA105020

/-! ## 2. The two repository statements, as elaborated -/

/-- The Goldbach side is definitionally `True ↔ P`: `answer(sorry)` has become `True`,
not `False`, and not a `sorry` (see the axioms printed at the end). -/
theorem goldbach_statement_elaborates :
    (type_of% @GoldbachConjecture.goldbach) =
      (True ↔ ∀ n : ℕ, 2 < n → Even n → ∃ p q, Prime p ∧ Prime q ∧ n = p + q) := rfl

/-- The conjecture side is definitionally the statement in
`FormalConjectures/OEIS/105020.lean`. -/
theorem conjecture_statement_elaborates :
    (type_of% @OeisA105020.conjecture) =
      (∀ (n i j : ℕ), 1 ≤ n → a i = 2 * n + 1 → a j = 2 * n + 3 → j = i + n + 1 →
        ∃ k, i < k ∧ k < j ∧ (a k).IsSemiprime) := rfl

/-! ## 3. Primes, evenness and semiprimes have their usual meaning -/

theorem prime_iff_nat_prime (p : ℕ) : Prime p ↔ Nat.Prime p := Nat.prime_iff.symm

theorem even_iff_exists_add (m : ℕ) : Even m ↔ ∃ r, m = r + r := Iff.rfl

theorem isSemiprime_iff (m : ℕ) :
    m.IsSemiprime ↔ m ≠ 0 ∧ ArithmeticFunction.cardFactors m = 2 := Iff.rfl

/-! ## 4. The definitions agree with `T c` and with the OEIS b-file (offset 0) -/

theorem triangularNumber_values :
    triangularNumber 0 = 0 ∧ triangularNumber 1 = 1 ∧ triangularNumber 2 = 3 ∧
      triangularNumber 3 = 6 ∧ triangularNumber 4 = 10 := by
  decide

theorem a_values_match_b_file :
    a 0 = 1 ∧ a 1 = 3 ∧ a 2 = 4 ∧ a 3 = 5 ∧ a 4 = 8 ∧ a 5 = 9 ∧
      a 6 = 7 ∧ a 7 = 12 ∧ a 8 = 15 ∧ a 9 = 16 ∧ a 10 = 9 ∧ a 11 = 16 := by
  unfold a antidiagonalIndex triangularNumber
  simp only [Nat.choose_two_right]
  norm_num

/-! ## 5. Hiebl's example under the current offset

The example in the OEIS comment (n = 3) names a(7) = 7, a(8) = 12, a(9) = 15,
a(10) = 16 and a(11) = 9, that is, offset 1. With the entry's current offset 0, which
the repository also uses, the same terms are a(6), ..., a(10): the indices are
i = 6 = T 3 and j = 10 = T 4, and j = i + 3 + 1. -/
theorem hiebl_example_at_offset_zero :
    a 6 = 2 * 3 + 1 ∧ a 7 = 12 ∧ a 8 = 15 ∧ a 9 = 16 ∧ a 10 = 2 * 3 + 3 ∧
      triangularNumber 3 = 6 ∧ triangularNumber 4 = 10 := by
  unfold a antidiagonalIndex triangularNumber
  simp only [Nat.choose_two_right]
  norm_num

/-! ## 6. The hypotheses of the index lemma are satisfiable, so the lemma is not vacuous -/

theorem index_lemma_hypotheses_satisfiable :
    1 ≤ 3 ∧ a (triangularNumber 3) = 2 * 3 + 1 ∧ a (triangularNumber 4) = 2 * 3 + 3 ∧
      triangularNumber 4 = triangularNumber 3 + 3 + 1 := by
  have h3 : triangularNumber 3 = 6 := by decide
  have h4 : triangularNumber 4 = 10 := by decide
  rw [h3, h4]
  unfold a antidiagonalIndex triangularNumber
  simp only [Nat.choose_two_right]
  norm_num

end A105020Goldbach.MeaningChecks

#print axioms A105020Goldbach.MeaningChecks.goldbach_statement_elaborates
#print axioms A105020Goldbach.MeaningChecks.conjecture_statement_elaborates
#print axioms A105020Goldbach.MeaningChecks.prime_iff_nat_prime
#print axioms A105020Goldbach.MeaningChecks.even_iff_exists_add
#print axioms A105020Goldbach.MeaningChecks.isSemiprime_iff
#print axioms A105020Goldbach.MeaningChecks.triangularNumber_values
#print axioms A105020Goldbach.MeaningChecks.a_values_match_b_file
#print axioms A105020Goldbach.MeaningChecks.hiebl_example_at_offset_zero
#print axioms A105020Goldbach.MeaningChecks.index_lemma_hypotheses_satisfiable
'''
(PUB / "lean" / "MeaningChecks.lean").write_text(text, encoding="utf-8")
print(f"wrote lean/MeaningChecks.lean ({len(names)} challenge statements)")
