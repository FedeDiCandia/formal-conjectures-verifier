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

### Quante dimostrazioni d'archivio passano davvero

Tre passate, ognuna con il suo registro:

| passata | snapshot | candidati | accettate |
|---|---|---|---|
| 1 | `bench-v1` | 23 | 17 ([registro](dati/verifica_bench_v1_23.txt)) |
| 2 | `main` | 6 di livello facile | 5 ([registro](dati/prove_archivio_test_tier.json)) |
| 3 | `main` | i 13 candidati medi e difficili | **13** ([registro](dati/verifica_main_13.txt)) |

Sullo snapshot `main`: **19 candidati, 18 accettati**. L'unico rifiutato,
`DiophantineTuple.gibbs_6_tuple`, ha un `sorry` in una dichiarazione che il
bersaglio usa: giusto che venga rifiutato.

`GottschalkSurjunctivity.isSurjunctive_of_finite` era stato scartato come «non
estraibile»: era un difetto dell'estrattore (una riga di docstring che comincia
con «endomorphism» veniva letta come un `end`). Corretto; ora viene **accettato**.

Una nota operativa che vale la pena scrivere: in una passata precedente,
lanciata mentre altri lavori toccavano lo stesso archivio,
`SidorenkoConjecture.sidorenko_conjecture.variants.star` risultava RIFIUTATO;
nella passata pulita e' ACCETTATO. Il verificatore, se qualcuno modifica
l'archivio mentre lui lavora, se ne accorge e rifiuta — fallisce dalla parte
giusta — ma questo vuol dire che **una verifica non va lanciata in parallelo ad
altri lavori sullo stesso archivio**, altrimenti si leggono rifiuti che non
riguardano la dimostrazione.

---

## Gli undici problemi scelti

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

---

## Esito della calibrazione (eseguita)

Spesa totale **$2.9834** su un limite rigido di $15. Modello `claude-opus-5`, effort `medium`, al massimo 20 iterazioni per problema.

| livello | problema | esito | iterazioni | verifiche | costo |
|---|---|---|---|---|---|
| facile | `WieferichMirimanoffPrime.isMirimanoffPrime_and_not_isWieferichPrime_1006003` | **risolto** | 8 | 1 | $0.1485 |
| facile | `WilsonPrime.not_isWilsonPrime_seven` | **risolto** | 1 | 1 | $0.0148 |
| facile | `DiophantineTuple.fermat_4_tuple` | **risolto** | 2 | 1 | $0.0497 |
| facile | `ClaudesCycles.not_hasHamiltonianArcDecomposition_one` | **risolto** | 1 | 1 | $0.0565 |
| medio | `JacobianConjecture.jacobian_conjecture` | non risolto | 20 | 1 | $0.6886 |
| medio | `VizingConjecture.vizing_conjecture.variants.dominationNumber_eq_one` | **risolto** | 3 | 1 | $0.0662 |
| medio | `SidorenkoConjecture.sidorenko_tree_subsingleton` | **risolto** | 3 | 1 | $0.1639 |
| difficile | `DeGiorgi.DeGiorgi_one` | **risolto** | 6 | 1 | $0.2572 |
| difficile | `WrittenOnTheWallII.GraphConjecture65.conjecture65` | non risolto | 13 | 0 | $1.2486 |
| difficile | `UnionClosed.union_closed.variants.singleton_mem` | **risolto** | 4 | 3 | $0.1524 |
| difficile | `SidorenkoConjecture.sidorenko_conjecture.variants.non_bipartite_necessary` | **risolto** | 3 | 1 | $0.1370 |

**9 su 11**: 4 su 4 fra i problemi di categoria `test`, 5 su 7 fra le varianti di congetture (`research solved`). Il numero che conta e' il secondo.

I due fallimenti non sono di sistema. Su `JacobianConjecture.jacobian_conjecture` il modello aveva la strategia giusta — un controesempio noto — e si e' fermato sull'ingegneria Lean (`MvPolynomial`, `pderiv`) dopo 20 iterazioni. Su `WrittenOnTheWallII.GraphConjecture65.conjecture65` stava costruendo il grafo su 17 vertici del controesempio noto ed e' finito il tetto di spesa del problema, con 12 esplorazioni e zero verifiche consegnate.

Il modello dei costi costruito su questi numeri sta in [docs/06-modello-costi.md](06-modello-costi.md); i dati grezzi in [docs/dati/calibrazione_completa.json](dati/calibrazione_completa.json).
