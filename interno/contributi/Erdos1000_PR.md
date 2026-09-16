# Bozza — NON inviata

Destinatari: i manutentori di google-deepmind/formal-conjectures.

**Aggiornamento del 13 settembre 2026, 23:00 UTC.** La PR #5837 è stata **unita** alle 16:44 UTC
(approvata da mo271, senza commenti). Su `main` (commit `5cba0ffd`) `phiSeq` usa ora «non divide» e
`totient_le` ha l'ipotesi `hn0 : 0 < n 0`; il teorema è ancora `sorry` e nessuna issue o PR ne
propone una prova. Il commento che avevo preparato per la #5837 non serve più: la strada è una
issue e una PR nuove, come per `DiophantineTuple`.

Controlli sulla prova adattata:
- accettata dal verificatore (comparator) contro l'enunciato e la definizione della #5837,
  identici carattere per carattere a quelli ora su `main`;
- inserita nel file vero di `main` (`1000_main.lean`), compila con Lean v4.33.1 e la stessa
  Mathlib di `main`; `#print axioms`: `[propext, Classical.choice, Quot.sound]`; restano solo i 4
  avvisi `sorry` degli altri enunciati del file;
- `totient_le_main.patch` (+35 −1) si applica al file di `main`.

La vecchia `totient_le.patch` (enunciato precedente alla #5837) non si applica più.

---

## Issue

**Title:** Prove `erdos_1000.variants.totient_le`

I would like to contribute a Lean 4 proof for `Erdos1000.erdos_1000.variants.totient_le` in
`FormalConjectures/ErdosProblems/1000.lean`, which is currently `sorry`.

The proof is short (35 lines) and elementary: sending each residue `a` coprime to `n k` to itself
(and `0` to `n k`) injects them into the set counted by `phiSeq n k`, since a coprime residue has
reduced denominator `n k`, which does not divide any earlier `n j` because
`0 < n 0 ≤ n j < n k`. This is the step that uses the hypothesis `hn0` added in #5837.

The proof is verified: the Lean kernel accepts it, `#print axioms` reports only `propext`,
`Classical.choice` and `Quot.sound`, and the file compiles against the current `main` without new
warnings.

May I be assigned this issue?

---

## Pull request

**Branch:** `prove-erdos-1000-totient-le`

**Title:** feat(ErdosProblems/1000): prove `erdos_1000.variants.totient_le`

**Body:**

Closes #<issue>.

Fills the `sorry` in `erdos_1000.variants.totient_le` ("It is trivial that
$\phi_A(k)\geq \phi(n_k)$"), for the statement introduced in #5837. The map sending `a` to itself,
and `0` to `n k`, injects the residues coprime to `n k` into the set counted by `phiSeq n k`: a
coprime residue has reduced denominator `n k`, and `n k ∤ n j` for `j < k` because
`0 < n 0 ≤ n j < n k`. 35 lines, no new imports; statement, definitions and category unchanged, and
no `formal_proof` attribute, since the proof lives in the file (#4962).

**Checks.** `#print axioms`: `[propext, Classical.choice, Quot.sound]`; also checked with
comparator against the statement. No issue or PR proves this declaration; the external proofs of
Erdős 1000 (plby/lean-proofs, Jayyhk/erdos-lean) prove the main statement, not this variant.

**AI assistance.** The proof was produced with AI assistance (Claude Opus 5, Anthropic) and
verified by machine as above. <!-- Federico: aggiungere «I have read and understood the proof»
solo se è vero; altrimenti lasciare così. -->

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---

## Prova (da incollare nel file, al posto di `sorry`)

```lean
theorem erdos_1000.variants.totient_le (n : ℕ → ℕ) (hn : StrictMono n) (hn0 : 0 < n 0)
    (k : ℕ) :
    (n k).totient ≤ phiSeq n k := by
  rw [Nat.totient, phiSeq]
  apply Finset.card_le_card_of_injOn (fun a => if a = 0 then n k else a)
  · intro a ha
    simp only [Finset.mem_coe, Finset.mem_filter, Finset.mem_range] at ha ⊢
    obtain ⟨ha1, ha2⟩ := ha
    have hgcd : Nat.gcd (if a = 0 then n k else a) (n k) = 1 := by
      by_cases h : a = 0
      · subst h
        have : n k = 1 := by simpa [Nat.coprime_zero_right] using ha2
        simp [this]
      · simp only [h, if_false]
        rw [Nat.gcd_comm]; exact ha2
    have hpos : 0 < n k := lt_of_le_of_lt (Nat.zero_le a) ha1
    have hmem : 1 ≤ (if a = 0 then n k else a) ∧ (if a = 0 then n k else a) ≤ n k := by
      by_cases h : a = 0
      · subst h
        rw [if_pos rfl]
        omega
      · rw [if_neg h]
        omega
    simp only [Finset.mem_Icc]
    refine ⟨hmem, ?_⟩
    intro j hj
    rw [hgcd, Nat.div_one]
    exact Nat.not_dvd_of_pos_of_lt (hn0.trans_le (hn.monotone (Nat.zero_le j))) (hn hj)
  · intro a ha b hb hab
    simp only [Finset.mem_coe, Finset.mem_filter, Finset.mem_range] at ha hb
    simp only at hab
    by_cases h1 : a = 0 <;> by_cases h2 : b = 0
    · simp [h1, h2]
    · have : n k = 1 := by simpa [h1, Nat.coprime_zero_right] using ha.2
      omega
    · have : n k = 1 := by simpa [h2, Nat.coprime_zero_right] using hb.2
      omega
    · simpa [h1, h2] using hab
```
