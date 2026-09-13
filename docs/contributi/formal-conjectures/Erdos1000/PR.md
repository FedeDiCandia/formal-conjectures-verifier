# Bozza — NON inviata

Destinatari: i manutentori di google-deepmind/formal-conjectures, e l'autore della PR #5837.

**Da decidere prima di inviare.** La PR aperta #5837 (smmercuri, 11 settembre 2026) cambia
proprio questo enunciato: `phiSeq` passa da «il denominatore ridotto è diverso da `n j`» a «non
divide `n j`», e `totient_le` riceve l'ipotesi `hn0 : 0 < n 0`. Una PR sull'enunciato attuale
entrerebbe in conflitto con la #5837 e, se questa viene unita, dimostrerebbe un enunciato che
non esiste più. Due strade:

1. **Consigliata:** non aprire una PR separata; commentare la #5837 offrendo la prova adattata
   al nuovo enunciato (`candidati/Erdos1000_dopo_PR5837.lean`, verificata a parte: vedi
   `dati_ricerca/erdos1000_dopo_pr5837_verifica.json`). Il testo del commento è qui sotto.
2. Aspettare che la #5837 sia unita o chiusa, poi aprire la PR sull'enunciato che resta.

La patch `totient_le.patch` è per l'enunciato attuale e serve solo nel caso in cui la #5837
venga chiusa senza essere unita.

---

## Commento proposto sulla PR #5837

The `sorry` in `erdos_1000.variants.totient_le` can be filled for the new statement too. The
only change from a proof of the current statement is the step showing that a residue coprime to
`n k` survives the filter: its reduced denominator is `n k`, and `n k ∤ n j` for `j < k` because
`0 < n 0 ≤ n j < n k`. That is exactly where the new hypothesis `hn0` is needed:

```lean
exact Nat.not_dvd_of_pos_of_lt (hn0.trans_le (hn.monotone (Nat.zero_le j))) (hn hj)
```

The full 35-line proof is below; happy to open it as a follow-up PR once this one is merged, if
you prefer to keep this PR to the statement fix.

<details><summary>Proof</summary>

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

</details>

The proof was produced by an AI model (Claude Opus 5, Anthropic) and checked with comparator
against the statement of this PR; `#print axioms` gives `[propext, Classical.choice, Quot.sound]`.

---

## Pull request (solo se la #5837 viene chiusa senza essere unita)

**Branch:** `prove-erdos-1000-totient-le`

**Title:** feat(ErdosProblems/1000): prove `erdos_1000.variants.totient_le`

**Body:**

Fills the `sorry` in `erdos_1000.variants.totient_le` ("It is trivial that
$\phi_A(k)\geq \phi(n_k)$"). The map sending `a` to itself, and `0` to `n k`, injects the residues
coprime to `n k` into the set counted by `phiSeq n k`: a coprime residue has reduced denominator
`n k`, which differs from every `n j` with `j < k` by strict monotonicity. 35 lines, no new
imports; statement, definitions and category unchanged, and no `formal_proof` attribute, since
the proof lives in the file (#4962).

**Checks.** `#print axioms`: `[propext, Classical.choice, Quot.sound]`; also checked with
comparator against the unmodified statement at commit `0a8b856c`. No PR proves this declaration;
the external proofs of Erdős 1000 (plby/lean-proofs, Jayyhk/erdos-lean) prove the main statement,
not this variant.

**AI assistance.** The proof was produced by an AI model (Claude Opus 5, Anthropic) in an
automated attempt, then checked as above. I have read and understood the proof.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
