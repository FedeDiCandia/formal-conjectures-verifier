# Il primo lotto della scala, e il bersaglio proposto

*11 settembre 2026. Niente è stato speso oltre i $0,0792 della prova con
Fable 5.1.*

---

## 1. I dieci problemi, e il criterio con cui sono scelti

Dai 54 della famiglia buona (congetture OEIS, elementari, mai entrate nel
benchmark di Epoch), ordinati da `scripts/scegli_lotto.py` con un punteggio
dichiarato: predicato calcolabile su un caso singolo (+30), enunciato corto
(+20), confutabile con un caso singolo (+25), nessun nome celebre nel docstring
(+15), frontiera di verifica grande dichiarata (−20).

| | problema | enunciato | punti |
|---|---|---|---|
| 1 | `OeisA34693.exists_k` | `∀ n > 1, ∃ k < n, Prime (n·k + 1)` | 90 |
| 2 | `OeisA110566.conjecture` | ogni numero dispari compare nella successione | 90 |
| 3 | `OeisA110854.conjecture` | i valori assoluti coprono 1 e i pari | 90 |
| 4 | `OeisA108569.conjecture` | tranne il primo, i termini sono tutti pari | 90 |
| 5 | `OeisA38552.odd_of_isA038552` | per classe pari, il termine è dispari | 90 |
| 6 | `OeisA5153.conjecture` | ogni dispari ≥ 3 è primo + numero pratico | 90 |
| 7 | `OeisA105720.conjecture` | `a(n)` è un quadrato solo per n = 3, 6, 4072 | 90 |
| 8 | `OeisA1146.conjecture` | caratterizzazione dei k con k⁴−1 ∣ 2ᵏ−1 | 90 |
| 9 | `OeisA357513.general_supercongruence` | supercongruenza con eccezioni finite | 80 |
| 10 | `OeisA239957.conjecture` | ogni primo ha una radice primitiva k²+1 | 75 |

Due voci portano un'avvertenza che il punteggio non ha visto, perché il
docstring non nomina nessuno: la **6** è la congettura di Margenstern sui numeri
pratici (1991), studiata; la **10** è di Zhi-Wei Sun. Restano nel lotto perché il
30% misurato da Epoch vale anche su congetture con un nome — ma non sono le
prime da cui partire.

---

## 2. Un limite strutturale che vale per tutto il lotto

**Un controesempio trovato dal calcolo non è quasi mai verificabile in Lean.**

L'ho misurato sul candidato 1. Per `∀ n > 1, ∃ k < n, Prime(n·k+1)`:

| | |
|---|---|
| velocità della ricerca | **213 000 valori di n al secondo** (MISURATO, n ≈ 10⁵) |
| nessun controesempio fino a | **5 milioni** (MISURATO, pochi secondi) |
| il k che serve, al massimo | **144** (MISURATO: la congettura non è mai «in bilico») |

Quindi un eventuale controesempio sta oltre i 5 milioni. Ma confutare
l'enunciato per un n specifico vuol dire dimostrare in Lean che **nessuno** dei
n−1 valori di k funziona: un milione di fatti di compostezza, ognuno con il suo
testimone. Il kernel non ci arriva, e un file Lean con un milione di
fattorizzazioni non è una dimostrazione che qualcuno leggerà.

**Conseguenza da tenere in mente per tutto il piano:** la strada che il nostro
verificatore può certificare è la **dimostrazione**, non la confutazione per
enumerazione. Le confutazioni certificabili sono quelle con un testimone
*piccolo* — e i testimoni piccoli esistono solo dove la congettura non è stata
verificata lontano, oppure dove la formalizzazione si discosta dalla fonte. È la
ragione per cui la sonda degli artefatti e il primo giro a tetto basso valgono
più di qualunque ricerca a forza bruta.

---

## 3. Il bersaglio proposto: `OeisA34693.exists_k`

### 3.1 Fonte

OEIS [A034693](https://oeis.org/A034693), «smallest k such that k·n + 1 is
prime». La congettura è un **commento di A. Murthy, 2001**, ripreso dal
docstring dell'archivio:

> *Conjecture: for every $n > 1$ there exists a number $k < n$ such that
> $nk + 1$ is a prime.*

**Avvertenza, e va risolta prima di spendere:** la pagina OEIS cita un articolo
del 2024 di Pengcheng Niu e Junli Zhang, *On Two Conjectures of A. Murthy*, che
riguarda proprio A034693 e A109909. Non ho potuto leggerlo (OEIS risponde 403 ai
programmi, ResearchGate chiede l'accesso). **Se quell'articolo la dimostra, il
problema non è aperto e il bersaglio passa al numero 2 del lotto.** È un
controllo da fare a mano, costa zero, e va fatto prima del primo dollaro.

### 3.2 Perché è poco studiato

- è un **commento in una voce OEIS**, non il titolo di un articolo: nasce come
  osservazione di una persona, non come problema proposto a una comunità;
- **nessun premio**, nessuna menzione nelle raccolte che i matematici leggono
  (la raccolta di Zhi-Wei Sun, arXiv:1211.1588, la cita solo di passaggio
  insieme all'altra di Murthy);
- **MISURATO**: non è mai entrata nel benchmark di Epoch AI, né per nome né per
  numero di sequenza — quindi nessuno dei tre laboratori l'ha attaccata con un
  modello di frontiera;
- tutta la letteratura che ho trovato è **un articolo del 2024**. Per confronto,
  la congettura di Goldbach ha 280 anni di tentativi.

### 3.3 Forma logica

```
∀ n : ℕ, 1 < n → ∃ k < n, Nat.Prime (n * k + 1)
```

Un esistenziale **limitato** (`k < n`) dentro un universale. Per ogni singolo
`n` l'affermazione è **decidibile** con un calcolo finito, e `decide` la chiude
in Lean per `n` piccoli. È la forma più maneggevole del lotto: 49 caratteri,
nessuna definizione ausiliaria da ricopiare, nessun `Nat.nth` da calcolare nel
kernel.

### 3.4 Che cosa dovrebbe produrre l'agente

In ordine di probabilità decrescente, secondo me:

1. **Una dimostrazione per una famiglia infinita di n** — per esempio: se `n` è
   pari, `n·k+1` è dispari per ogni k, e basta trovare un k che eviti i piccoli
   fattori; oppure un argomento con il teorema di Dirichlet sulle progressioni
   aritmetiche, che in Mathlib esiste (`Nat.setOf_prime_and_eq_mod_infinite` e
   dintorni). **Non risolverebbe il problema**, ma sarebbe un lemma vero,
   verificato, e un passo dichiarabile.
2. **Una dimostrazione completa**, se esiste una via elementare che non vedo.
   Dirichlet dà infiniti primi ≡ 1 mod n, ma non ne dà uno *sotto* n²: il salto
   fra «esistono» e «esiste con k < n» è esattamente la difficoltà, e richiede
   una stima effettiva (Linnik) che in Mathlib non c'è. **Probabilità bassa.**
3. **Una confutazione strutturale**: una classe di congruenza di n in cui
   `n·k+1` è composto per ogni `k < n`. Sarebbe un risultato vero e
   certificabile. Nessun indizio che esista, ma è la forma che l'agente dovrebbe
   cercare se la dimostrazione non va.
4. **Un rapporto onesto di fallimento** con la ragione: anche questo è un esito
   utile, e la nostra strumentazione lo registra.

Quello che **non** deve produrre: un file che compila ma dimostra un enunciato
diverso (il verificatore lo rifiuta), o una ricerca di controesempi oltre i 5
milioni (il calcolo è gratis ma il risultato non sarebbe verificabile, vedi
punto 2).

### 3.5 Come sapremo a metà tentativo che non sta funzionando

La strumentazione dell'agente registra già tutto quello che serve. Con il tetto
a $2, i segnali di arresto, **in ordine di gravità**:

| quando | segnale | che cosa significa |
|---|---|---|
| speso $0,60 (un terzo) | `verifiche == 0`, solo `esplorazioni` | non è mai arrivato a consegnare un candidato. È il modo in cui ha fallito `GraphConjecture65`: si fermerà così anche col doppio del budget |
| in qualunque momento | due verifiche di seguito con natura `enunciato_sbagliato` | non riesce a riprodurre l'enunciato: il problema è la nostra consegna del testo, non la matematica |
| speso $1,20 (due terzi) | nessun lemma ausiliario accettato | non ha costruito niente su cui appoggiarsi |
| — | natura `errore_tecnico` o `buco_o_assioma` almeno una volta | **il segnale positivo**: ha consegnato un candidato che combacia con l'enunciato e si è fermato sulla prova. Passa al giro successivo |

I primi tre li controllo io leggendo il rapporto; il quarto è il criterio
meccanico di `scripts/promossi.py`. Nessuno dei quattro richiede di indovinare:
sono nature di verifica che il verificatore assegna da sé.
