# Selezione dei problemi per la calibrazione

**Snapshot:** `external/fc-main`, commit `0a8b856c` del ramo `main`, Lean 4.33.1.
**Taglio di addestramento considerato:** maggio 2026 (dichiarato da `claude-opus-5`).

Un problema entra in questa lista solo se soddisfa **tutte** queste condizioni:

1. l'archivio ne fornisce una dimostrazione;
2. quella dimostrazione usa solo `propext`, `Classical.choice`, `Quot.sound`;
3. quella dimostrazione, estratta e compilata da sola, viene **accettata da
   `verify.py`** sullo stesso snapshot — è il controllo che conta, gli altri due
   sono necessari ma non sufficienti;
4. l'enunciato non ha buchi `answer( )`.

Verificate 20 dimostrazioni, **18 accettate**.

---

## I dodici problemi scelti

### Livello facile (1-3 righe di dimostrazione)

| data | righe | rischio | problema | tipo |
|---|---|---|---|---|
| 2026-09-09 | 1 | BASSO | `WieferichMirimanoffPrime.isMirimanoffPrime_and_not_isWieferichPrime_1006003` | istanza concreta su un primo grande |
| 2026-08-10 | 2 | BASSO | `WilsonPrime.not_isWilsonPrime_seven` | istanza concreta |
| 2026-08-20 | 2 | BASSO | `DiophantineTuple.fermat_4_tuple` | **esempio**: la quaterna di Fermat `{1,3,8,120}` è diofantea |
| 2026-08-15 | 3 | BASSO | `ClaudesCycles.not_hasHamiltonianArcDecomposition_one` | **controesempio** |

### Livello medio (10 righe)

| data | righe | rischio | problema |
|---|---|---|---|
| 2026-07-28 | 10 | BASSO | `JacobianConjecture.jacobian_conjecture` |
| 2026-08-29 | 10 | BASSO | `VizingConjecture.vizing_conjecture.variants.dominationNumber_eq_one` |
| 2026-06-08 | 10 | INCERTO | `SidorenkoConjecture.sidorenko_tree_subsingleton` |

### Livello difficile (15-34 righe)

| data | righe | rischio | problema |
|---|---|---|---|
| 2026-07-02 | 15 | BASSO | `DeGiorgi.DeGiorgi_one` |
| 2026-08-06 | 16 | BASSO | `WrittenOnTheWallII.GraphConjecture65.conjecture65` |
| 2026-08-23 | 20 | BASSO ⚠️ | `UnionClosed.union_closed.variants.singleton_mem` |
| 2026-08-29 | 34 | BASSO | `SidorenkoConjecture.sidorenko_conjecture.variants.non_bipartite_necessary` (**controesempio**: il triangolo non è un grafo di Sidorenko) |

⚠️ Su `UnionClosed...singleton_mem` c'è un'avvertenza: il teorema esisteva già in
`bench-v1` con data 2025-08-04, e la dimostrazione è stata **riscritta**. La data
recente riguarda la riscrittura, non il risultato: il modello potrebbe conoscere
la versione precedente. È l'unico caso in cui il rischio "BASSO" va preso con le
molle.

---

## Rischio di memorizzazione

| | |
|---|---|
| BASSO (prova aggiunta dopo giugno 2026) | 10 |
| INCERTO (maggio-giugno 2026) | 1 |
| ALTO | 0 |

Per confronto, sul tag `bench-v1` **tutti e 17** i candidati erano ad alto
rischio, perché il tag è del 6 maggio 2026 e il taglio è maggio 2026. Lo
snapshot da `main` non era un miglioramento opzionale: era la condizione
necessaria per una calibrazione che misuri la capacità di dimostrare invece
della memoria.

---

## Come si misura la data

Con `git log -S` sulla riga più lunga e distintiva della dimostrazione: si trova
il primo commit che l'ha introdotta nel file. Non è infallibile — una
dimostrazione riscritta risulta più recente di quanto sia l'idea, ed è proprio il
caso di `UnionClosed` — ma è una misura, non una supposizione.

---

## Le due rifiutate, e perché

| problema | motivo |
|---|---|
| `GottschalkSurjunctivity.isSurjunctive_of_finite` | l'estrattore non riesce a isolare la dichiarazione (`unexpected identifier; expected command`) |
| `DiophantineTuple.gibbs_6_tuple` | nel file resta un `sorry` in una dichiarazione che il bersaglio usa |
