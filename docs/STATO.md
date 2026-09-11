# Stato del progetto

*Ultimo aggiornamento: 2026-09-10, sessione autonoma in corso.*

---

## Riepilogo rapido

Il sistema è completo nelle sue tre parti: ambiente Lean, verificatore, agente.
La parte solida è il **verificatore**. L'agente è stato collaudato solo
parzialmente, e la calibrazione vera non è ancora stata eseguita.

| componente | stato |
|---|---|
| Ambiente (Lean 4.27.0, archivio `bench-v1`, comparator) | ✅ funzionante |
| Verificatore (`verify.py`) | ✅ 58 test passanti |
| Sandbox + controllo integrità archivio | ✅ collaudati |
| Strumenti dell'agente (`lean_explore`, `lean_check`, `run_python`) | ✅ |
| Sfide negate (`--confutazione`) | ✅ |
| Calibrazione dell'agente | ⏳ non eseguita |
| Snapshot post-cutoff da `main` | ⏳ in preparazione |

---

## Domande per Federico

*(nessuna al momento)*

---


## Fase 2 — verifica delle dimostrazioni d'archivio

Un problema puo' entrare nella calibrazione solo se la dimostrazione che
l'archivio stesso fornisce, estratta e compilata da sola, viene **accettata**
da `verify.py`. Il solo controllo sugli assiomi non basta: dice che la prova
non usa scorciatoie, non che arrivi in fondo al verificatore.

**Esito misurato: 17 su 23 accettate** (con le ultime correzioni
all'estrattore ci si attende 20; le due di Kurepa ora compilano).

| righe di prova | categoria | teorema |
|---|---|---|
| 1 | textbook | `Conway99Graph.completeGraphIsClique` |
| 2 | research solved | `UnionClosed.union_closed.variants.univ_card_two` |
| 2 | research solved | `EquationalTheories_677_255.Equation255_not_implies_Equation677` |
| 4 | textbook | `CarmichaelTotient.carmichealTotientFor_odd` |
| 4 | textbook | `Conway99Graph.completeGraph_cliqueSet` |
| 6 | research solved | `EulerSumOfPowers.eulers_sum_of_powers_conjecture.false_for_k4` |
| 6 | research solved | `EulerSumOfPowers.eulers_sum_of_powers_conjecture.false_for_k5` |
| 9 | textbook | `AgohGiuga.squarefree_of_isCarmichael` |
| 10 | research solved | `SumOfThreeCubes.isSumOfThreeCubesRat_any` |
| 11 | textbook | `DedekindNumber.exists_minimal_true_subset` |
| 11 | textbook | `DedekindNumber.toSperner_fromSperner` |
| 15 | textbook | `DedekindNumber.fromSperner_toSperner` |
| 20 | research solved | `UnionClosed.union_closed.variants.singleton_mem` |
| 23 | textbook | `BealConjecture.flt_of_beal_conjecture` |
| 25 | research solved | `InvariantSubspaceProblem.Invariant_subspace_problem_non_separable` |
| 39 | textbook | `AgohGiuga.korselts_criterion` |
| 46 | research solved | `UnionClosed.union_closed.variants.sharpness` |

**Rifiutate e perché:**

| teorema | motivo |
|---|---|
| `Oppermann.oppermann_implies_legendre` | l'enunciato usa `type_of% oppermann_conjecture`, che è un teorema con `sorry`: non estraibile, e non è un difetto nostro |
| `CategoryDocstringLinter.*` (2) | sono banchi di prova del linter dell'archivio (`#guard_msgs`), non matematica: da escludere per costruzione |
| `Kurepa.*` (2) | erano difetti dell'estrattore, ora corretti |
| `EquationalTheories...Finite` | idem |

Nel percorso sono stati trovati **sei difetti dell'estrattore**, tutti emersi
solo perché si è verificato davvero invece di fidarsi del controllo sugli
assiomi. Sono documentati nei messaggi di commit.

---

## Ritrovamenti

*(nessuno al momento)*

---

## Ricerche in corso

*(nessuna al momento)*

