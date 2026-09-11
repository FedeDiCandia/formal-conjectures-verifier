# Stato del progetto

*Aggiornato: 2026-09-10, sessione autonoma.*

---

## Riepilogo in cinque minuti

Il sistema ha tre parti: **ambiente Lean**, **verificatore**, **agente**.
La parte solida è il verificatore, ed è quella su cui vale la pena fidarsi.
L'agente è stato provato solo parzialmente e la calibrazione vera non è ancora
stata eseguita.

| componente | stato |
|---|---|
| Ambiente Lean 4.27.0 + archivio `bench-v1` + comparator | ✅ funzionante |
| Verificatore `verify.py` | ✅ 58 test, tutti passanti |
| Sandbox della compilazione + controllo integrità archivio | ✅ collaudati, con controprova |
| Strumenti dell'agente (`lean_explore`, `lean_check`, `run_python`) | ✅ |
| Sfide negate (`--confutazione`) per i 107 problemi aperti con `answer(sorry)` | ✅ |
| Infrastruttura per ricerche lunghe (checkpoint, ripresa, isolamento) | ✅ 8 test |
| Programmi di ricerca di controesempi | ✅ scritti e collaudati su valori noti |
| Snapshot post-cutoff da `main` | ⏳ in compilazione |
| Calibrazione dell'agente | ⏳ non ancora eseguita |

### Cosa è stato fatto in questa sessione

1. **`lean_explore`**, strumento separato dal giudizio. Nel primo collaudo
   l'agente aveva speso 9 verifiche su 9 per ispezionare Mathlib, non per
   consegnare dimostrazioni — e ci riusciva solo provocando errori di tipo di
   proposito. Ora `#print`, `#check` ed `exact?` funzionano, in 9 secondi
   invece di 33.
2. **Verifica vera delle dimostrazioni d'archivio**: non basta che gli assiomi
   siano puliti, la dimostrazione deve passare `verify.py`. Sei difetti
   dell'estrattore trovati solo perché si è provato davvero.
3. **Ambiente di calcolo** con numpy, sympy, numba, e infrastruttura per
   ricerche lunghe che riprendono dopo un'interruzione.
4. **Tre programmi di ricerca** di controesempi, ciascuno con un blocco di
   collaudo su valori noti.
5. **`avvia.sh`**, comando unico per i lavori lunghi.
6. **Protocollo per i ritrovamenti** ([docs/04](04-protocollo-ritrovamenti.md)).

### Le due cose più importanti da sapere

**Il benchmark è anteriore all'addestramento del modello.** Il tag
`bench-v1-lean4.27.0` è del 6 maggio 2026; il taglio di addestramento dichiarato
per `claude-opus-5` è maggio 2026. Tutte e 17 le dimostrazioni utilizzabili per
la calibrazione sono quindi ad **alto rischio di memorizzazione**. Su `main` ci
sono 548 file di problemi aggiunti dopo giugno 2026: è da lì che deve venire una
calibrazione onesta, ed è il motivo dello snapshot in preparazione.

**Un problema "risolto nell'archivio" non è detto sia risolvibile qui.** Delle
619 dimostrazioni complete dell'archivio, 109 usano assiomi che il verificatore
rifiuta: 95 con `decide +native`, 17 che dipendono da `sorryAx` tramite un
lemma. Fra queste c'erano due dei tre problemi che avevo scelto per il primo
test dell'agente — il test misurava qualcosa che non poteva riuscire.

---

## Domande per Federico

**1. Snapshot da `main`: quale commit?**
Ho scelto `0a8b856c` (10 settembre 2026), fisso. Se preferisci un altro punto,
basta cambiare `COMMIT_MAIN` in `scripts/setup_snapshot_main.sh`. Ho scelto il
più recente disponibile perché massimizza i problemi post-taglio.
*Ho proceduto con questa scelta perché è reversibile e non distruttiva.*

**2. Le ricerche di controesempi sui problemi già verificati fino a soglie
enormi vanno tentate lo stesso?**
Per Erdős 366 il limite noto è 10²², per Goldbach e Legendre 4×10¹⁸: una ricerca
a forza bruta non può avvicinarsi. Ho preferito **non** metterli in coda e
concentrarmi sui problemi con limiti noti bassi o assenti. Se preferisci
tentarli comunque per completezza, dimmelo.

---

## Ritrovamenti

*(nessuno finora)*

I collaudi brevi delle tre ricerche non hanno prodotto nulla, come atteso:
- numeri di Euclide: nessun `p` con `p²` divisore, fino a `p` = 303;
- iterazione di sigma: nessuna orbita anomala, fino a `n` = 2000;
- Erdős 396: nessun `n` per `k ≥ 2` fino a `n` = 2000 — è un **indizio**, non un
  controesempio (la forma "per ogni k esiste n" non si confuta con un calcolo).

---

## Ricerche in corso

| lavoro | stato |
|---|---|
| snapshot da `main` (Lean 4.33.1, cache, compilazione) | in corso, log in `runs/snapshot_main.log` |
| caccia ai controesempi | preparata, **non ancora lanciata**: il computer è occupato dallo snapshot |

---

## Fase 2 — verifica delle dimostrazioni d'archivio

Un problema può entrare nella calibrazione solo se la dimostrazione che
l'archivio stesso fornisce, estratta e compilata da sola, viene **accettata** da
`verify.py`.

**Esito misurato: 17 su 23 accettate.**

| righe di prova | livello | categoria | teorema |
|---|---|---|---|
| 1 | facile | textbook | `Conway99Graph.completeGraphIsClique` |
| 2 | facile | research solved | `UnionClosed.union_closed.variants.univ_card_two` |
| 2 | facile | research solved | `EquationalTheories_677_255.Equation255_not_implies_Equation677` |
| 4 | medio | textbook | `CarmichaelTotient.carmichealTotientFor_odd` |
| 4 | medio | textbook | `Conway99Graph.completeGraph_cliqueSet` |
| 6 | medio | research solved | `EulerSumOfPowers...false_for_k4` |
| 6 | medio | research solved | `EulerSumOfPowers...false_for_k5` |
| 9 | medio | textbook | `AgohGiuga.squarefree_of_isCarmichael` |
| 10 | medio | research solved | `SumOfThreeCubes.isSumOfThreeCubesRat_any` |
| 11 | medio | textbook | `DedekindNumber.exists_minimal_true_subset` |
| 11 | medio | textbook | `DedekindNumber.toSperner_fromSperner` |
| 15 | difficile | textbook | `DedekindNumber.fromSperner_toSperner` |
| 20 | difficile | research solved | `UnionClosed...singleton_mem` |
| 23 | difficile | textbook | `BealConjecture.flt_of_beal_conjecture` |
| 25 | difficile | research solved | `InvariantSubspaceProblem...non_separable` |
| 39 | difficile | textbook | `AgohGiuga.korselts_criterion` |
| 46 | difficile | research solved | `UnionClosed...sharpness` |

**Rifiutate e perché:**

| teorema | motivo |
|---|---|
| `Oppermann.oppermann_implies_legendre` | l'enunciato usa `type_of%` su un teorema con `sorry`: non estraibile. Non è un difetto nostro |
| `CategoryDocstringLinter.*` (2) | sono banchi di prova del linter dell'archivio, non matematica |
| `Kurepa.*` (2), `EquationalTheories...Finite` | erano difetti dell'estrattore, corretti dopo questa misura |

---

## Numeri dell'archivio

| | bench-v1 | main (`0a8b856c`) |
|---|---|---|
| file di problemi | 691 | 1268 |
| di cui OEIS | 21 | **227** |
| di cui Erdős | 410 | 671 |
| file aggiunti dopo giugno 2026 | — | 548 (302 con almeno una dimostrazione) |

Problemi aperti verificabili in bench-v1: **911** su 1029 (gli altri 118 chiedono
un valore, non un sì/no, e non sono verificabili in modo onesto).
Di questi, **554** sono formalizzati con `answer(sorry)` proposizionale, quindi
l'archivio ha già stabilito che la risposta è "sì" e la modalità
`--confutazione` permette di attaccare l'altro verso.
