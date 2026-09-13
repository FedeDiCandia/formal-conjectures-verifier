# Formalizzare dimostrazioni già note: misura e proiezione

*13 settembre 2026. Il rilancio non è stato fatto: servivano $13 e sulla Console restano $12.*

Il compito: prendere dall'archivio problemi `research solved` o `textbook` la cui dimostrazione
non è formalizzata, farla formalizzare all'agente, e proporre le prove come pull request. Non è
ricerca; è un contributo che l'archivio accetta, se la prova è corta.

---

## 1. Selezione (gratis)

`scripts/scegli_formalizzazioni.py`: **1209 candidati** su 1790 problemi risolti o textbook
(esclusi quelli con prova già nell'archivio, con `native_decide`, con una prova che dipende da un
lemma con `sorry`, con `answer(sorry)`).

L'ordinamento per lunghezza dell'enunciato è stato scartato subito: metteva in cima Helfgott,
Deligne e la trascendenza di π + e. Si ordina per quello che dice la **fonte** della
dimostrazione (docstring: «easy to see», «trivial», «Proof: …») contro citazioni di articoli,
teoremi profondi, insiemi infiniti e analisi nell'enunciato. Ne escono cinque fasce:

| fascia | candidati | che cosa sono |
|---|---|---|
| A | 16 | la fonte dice che la prova è corta, niente di duro |
| B | 43 | textbook, niente di duro |
| C | 360 | risolti, nessun segnale nella fonte |
| D | 153 | dimostrazione citata da un articolo |
| E | 637 | teorema profondo, infinito o analisi, calcolo enorme |

Il lotto misurato erano i primi 20: i 16 della fascia A e 4 della B.

## 2. Misura

Opus 5, effort `low`, istruzioni «insistenti», tetto $1 per problema.

### Che cosa è andato storto, e quanto pesa

Nella notte il Mac è andato in sospensione (`pmset -g log`: *Maintenance Sleep* ogni 8–13
minuti, *Clamshell Sleep* alle 03:17). Ogni sospensione ha chiuso una connessione con l'API:
**otto interruzioni in dodici problemi**, più un crash al terzo problema prima della correzione.
Le chiamate finite normalmente duravano da 2 a 64 secondi; quelle interrotte da 11 minuti a oltre
un'ora. L'agente di quella notte addebitava ogni interruzione al suo costo massimo (circa $0,84)
**anche sul tetto del problema**: su sei problemi quell'addebito ha chiuso il tentativo da solo.
Corretto dopo (commit 9f215ca); il giro è stato fermato alle 03:26.

### I risultati, uno per uno

**Il costo** è quello delle chiamate completate, senza gli addebiti prudenziali.

| # | problema | esito | costo | verifiche | nota |
|---|---|---|---|---|---|
| 1 | `Erdos770.Nat.Prime.h_eq_add_one` | non chiuso | $0,79 | 0 | tetto esaurito esplorando la definizione di `h` |
| 2 | `Erdos770…odd_h_unbounded` | non chiuso | $0,80 | 0 | idem |
| 3 | `Erdos295.exists_k` | non chiuso | $0,83 | 0 | una sola chiamata: 32 000 token di ragionamento, nessuna conclusione |
| 4 | `DiophantineTuple.noIntegral…` | **accettato** | $0,13 | 1 | con un'interruzione, superata |
| 5 | `Erdos1148…weaker` | **indeterminato** | $0,16 | 0 | tetto consumato da un'interruzione |
| 6 | `Erdos1000…totient_le` | **accettato** | $0,48 | 4 | |
| 7 | `Erdos707…small_sidon_sets` | **indeterminato** | $0,04 | 0 | tetto consumato da un'interruzione |
| 8 | `Erdos399…cambie` | **indeterminato** | $0,10 | 1 | tetto consumato; e già dimostrata altrove (PR #5425) |
| 9 | `ComplexityTheory.coP_eq_P` | **indeterminato** | $0,21 | 0 | tetto consumato da un'interruzione |
| 10 | `Erdos1008…lower_bound` | **indeterminato** | $0,00 | 0 | due interruzioni, nessuna risposta arrivata |
| 11 | `Erdos291…steinerberger_generalization` | **indeterminato** | $0,37 | 0 | tetto consumato da un'interruzione |
| 12 | `Erdos649.erdos_649` | **accettato** | $0,24 | 2 | ma già dimostrata altrove (plby/lean-proofs) |
| 13 | `Erdos180.erdos_180` | non chiuso | $0,78 | 0 | serve un controesempio grande; già dimostrato altrove |
| 14 | `ComplexityTheory.P_subset_NP` | interrotto dallo stop | $0,17 | 0 | non contato |
| 15–20 | `Erdos1084…`, `OeisA38771…`, `RegularPrimes…37`, `CongruentNumber…1`, `OeisA3162…`, `Erdos503…` | non tentati | — | — | |

### I numeri

- **Tentativi con esito determinato: 7. Accettati: 3 (43%).**
- **Contributi validi**, cioè accettati e non già formalizzati altrove: **2 su 5** tentativi
  determinati su problemi ancora da fare (`DiophantineTuple`, `Erdos1000`). Più
  `isDiophantineTuple_of_subset`, dimostrato a mano per la pull request, che l'agente non ha
  tentato.
- **Indeterminati: 6.** Non dicono niente sull'agente e **non entrano in nessuna percentuale**.
- **Costo di un successo**, chiamate sue: da $0,13 a $0,48. **Costo di un fallimento
  determinato**: il tetto, $0,78–0,83.
- **Spesa di questo lavoro.** Chiamate completate, certe: $5,12. Sulla Console: $33 spesi in
  tutto. Se prima di questo lavoro la spesa era $26,71 ($20,53 in STATO.md più $6,18 registrati
  nella sessione), il lavoro è costato **circa $6,3**. Le chiamate interrotte sono quindi costate
  circa $1 in tutto, non i $5,80 addebitati per prudenza. È una stima: la ripartizione per giorno
  sulla Console la confermerebbe.
- **Costo per contributo valido**: circa $6,3 / 2 ≈ **$3**, con i guasti della notte dentro.

### Perché falliscono quelli determinati

| problema | ostacolo | con che certezza |
|---|---|---|
| `Erdos770` (due varianti) | probabilmente l'ingegneria Lean: `h` è un `sInf` in `ℕ∞` di un MCD su un'immagine di `Finset`; 18 esplorazioni in tutto, nessun candidato | **non determinabile**: giro lanciato con `--silenzioso`, il registro non ha i messaggi |
| `Erdos295.exists_k` | matematica: il modello cercava una costruzione di frazioni egizie con denominatori ≥ N e ha consumato 32 000 token di ragionamento in una chiamata senza arrivare a Lean | dal riassunto del ragionamento |
| `Erdos180.erdos_180` | matematica: serve un controesempio noto e grande (plby lo formalizza in otto file); il modello lo ha riconosciuto e ha detto di non poterlo scrivere col budget | dal riassunto del ragionamento |

Nessun fallimento determinato è dovuto con certezza all'API di Mathlib; due potrebbero esserlo.

## 2 bis. La fascia B letta a mano (13 settembre)

Le 43 docstring della fascia B, lette una per una insieme all'enunciato e alle definizioni che
usa. La selezione automatica le metteva tutte nella stessa fascia; lette, si dividono così.

### Da tentare dopo, in quest'ordine

| # | problema | perché | righe stimate |
|---|---|---|---|
| 1 | `Erdos261…borwein_loring` | identità finita su ℚ, senza definizioni dell'archivio: per induzione su m, $\sum_{k=n+1}^{n+m} k/2^k = (n+2)/2^n - (n+m+2)/2^{n+m}$, e con $n = 2^{m+1}-m-2$ i due lati coincidono | 20–30 |
| 2 | `Erdos261…borwein_loring_property` | segue dalla precedente: m termini $a_k = n+1+k$, distinti e ≥ 1; resta da passare dalla somma su `Ioc` a quella su `Fin m` | 20 |
| 3 | `OeisA108306.a_is_invert_transform_case` | la matrice $[[1,5],[1,2]]$ ha polinomio caratteristico $λ^2-3λ-3$, quindi $m^2 = 3m + 3I$ e le sue potenze seguono la stessa ricorrenza $a(k+2) = 3a(k+1)+3a(k)$ | 15 |
| 4 | `Jacobson.jacobson_conjecture_of_comm_ring` | Mathlib ha l'intersezione di Krull (`Ideal.iInf_pow_smul_eq_bot_of_le_jacobson`); il lavoro è far combaciare `Ring.jacobson R` con `Ideal.jacobson ⊥`. Rischio: l'API, non la matematica | 5–15 |

### Forse, dopo i primi quattro

| problema | perché | rischio |
|---|---|---|
| `OeisA38771.a_n_exists` | Dirichlet è in Mathlib (`Nat.forall_exists_prime_gt_and_eq_mod`): un primo $q \nmid Q_n$ e un primo $p ≡ Q_n \pmod{q^2}$ danno $c = p - Q_n$ multiplo di $q^2$, quindi composto | 40–60 righe con `ZMod` |
| `OeisA107247.known_prime_and_semiprimes` | puro calcolo: quadrati della successione "nonacci" fino al termine 28, e la primalità di 5 045 088 967 | lentezza del kernel |
| `OeisA63880.powerful_of_isPrimitiveTerm`, `…a_of_primitive_mul_squarefree` | argomento breve (σ e la somma dei divisori unitari sono moltiplicative), ma `usigma` è definita solo nel file e la moltiplicatività va dimostrata da zero | 50+ righe |
| `OeisA87719.a_exists` | vero perché quasi tutti i numeri hanno un fattore primo piccolo; serve un conteggio esplicito (per esempio $m = 3(2^n+3^n+3)$) | 50–80 righe di conteggi |

### Da non tentare (34)

- **Già formalizzati (2):** `DiophantineTuple.isDiophantineTuple_of_subset` (nella nostra PR);
  `Erdos649…sampaio` (plby/lean-proofs, `sampaio_counterexample`).
- **Teoremi profondi che la selezione non ha riconosciuto (20):** le cinque varianti di Poincaré
  (dimensioni 2, 4, ≥ 5, versione liscia in 3, implicazione liscia); `RegularPrimes` ×3 (la
  definizione passa dal numero di classi del campo ciclotomico; il criterio di Kummer);
  `WolstenholmePrime` ×2 (congruenze sui numeri di Bernoulli); `Mathoverflow17560` ×2 (esponenti
  reali: differenze finite o trascendenza); `Hilbert17` (polinomio di Motzkin); `MovingSofa`
  (costanti di Gerver); `Erdos1055` (classi di primi); `Erdos287` (implicazione di ricerca);
  `Mahler32`; `Green35`; `Erdos945` (equivalenza con O-grande); `Mathoverflow339137` (funzioni
  generatrici).
- **Costruzioni lunghe (9):** `CongruentNumber` 1 (discesa infinita di Fermat); `Erdos44` ×2
  (insiemi di Sidon di taglia √N); `Erdos707…singer_construction` (differenze perfette di Singer);
  `WeaklyFirstCountable` (lo spazio di Arens); i quattro sui campi quadratici (discriminanti e
  classificazione: serve l'anello degli interi di ℚ(√d)).
- **Calcoli fuori portata o prova non indicata (3):** `OeisA108301.primes_in_a` (somma delle cifre
  di $2^{2048}+1$, 617 cifre: i test dell'archivio usano già `native_decide`); `OeisA105751` (parte
  intera della parte immaginaria di un prodotto complesso); `OeisA3162.a_is_integer` (problema del
  Monthly, la fonte non indica la prova).

**In sintesi: 4 da tentare, 5 forse, 34 no.** Passo 0 fatto sui 9: nessuna pull request li cita;
quello su `sampaio` ha trovato la prova di plby.

## 3. Proiezione

**Misurato** vale solo per la fascia A, e su 7 tentativi: è un ordine di grandezza, non una stima
stretta. Il resto è **stimato**, e va letto come tale.

| fascia | candidati | tasso | da dove viene | contributi validi attesi |
|---|---|---|---|---|
| A | 16 | 40% dei tentati; ma 3 dei 16 erano già formalizzati altrove | **misurato** (2/5) | ne restano 8 da tentare: **circa 3** |
| B | 43 | 10–25% | **stimato**: textbook ma con definizioni pesanti (primi regolari, numeri congruenti, campi di numeri) | **4–10** |
| C | 360 | sotto il 5% | **stimato**: nessun segnale di prova corta, e un tetto da $1 non basta per prove di ricerca | **fino a una decina**, da trovare leggendo |
| D, E | 790 | circa zero | **stimato**: prove da articoli o teoremi profondi | **0** |

**In tutto, con questa macchina e un tetto da $1: nell'ordine di 10–20 contributi validi su 1209
candidati**, quasi tutti in A e B. Il costo cresce scendendo nelle fasce: circa $3 per contributo
in A (misurato, con i guasti), stimato $5–10 in B, molto di più in C.

### Conviene continuare? Sì, ma stretto

1. **Solo la fascia A che resta** (8 problemi) quando c'è credito: circa $6, circa 3 prove.
   È l'unica parte con un tasso misurato.
2. **La fascia B solo dopo una lettura a mano** delle 43 docstring, gratis, per togliere quelle
   con definizioni che l'agente non può maneggiare con $1.
3. **Non C, D, E** con questa configurazione: il 9 su 11 della calibrazione era su problemi con
   una prova d'archivio corta già scritta, e non si trasferisce.

Due vincoli che contano più del budget:
- **Il passo 0 prima di spendere.** 3 dei 13 problemi tentati erano già formalizzati altrove, e
  lo si scopre gratis (PR aperte, repository di prove esterne).
- **Il lavoro umano per ogni pull request**: CLA, issue, fork, e la frase sull'uso dell'IA che
  Federico deve poter firmare. Ogni contributo richiede la sua lettura.
