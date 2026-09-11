# Lettura dei candidati: dove abbiamo un vantaggio reale

*11 settembre 2026. Nessuna spesa API. Le fonti consultate sono i docstring
dell'archivio (che citano i commenti OEIS), il repository pubblico di Epoch AI e
ricerche in rete in sola lettura. OEIS risponde 403 alle richieste automatiche,
quindi i suoi commenti li ho letti attraverso l'archivio.*

**Il risultato è in buona parte negativo, e va detto prima del resto:** i
problemi che sembravano avere una frontiera ridicola non sono quasi mai
inesplorati. Sono studiati più di quanto la loro oscurità suggerisca.

---

## 1. I candidati morti, e perché

| problema | perché esce |
|---|---|
| `OeisA232174` (Sun, «x+ny e x²+ny² primi») | **premio di $200** offerto dall'autore, e un articolo del 2026 ([arXiv:2602.08286](https://arxiv.org/pdf/2602.08286)) che ottiene risultati parziali con il crivello di Richert. Chi offre soldi ha già provato |
| `OeisA103151` | è la congettura di Levy/Lemoine travestita («più forte di Goldbach» dice il docstring): verificata fino a soglie enormi |
| `OeisA104320` (zeri di 2ⁿ in base 3) | è un problema di Erdős, verificato molto lontano |
| `OeisA064169` | **già risolto da Epoch AI** (run `oeis-full-50usd`): il nostro archivio lo marca ancora `research open` |
| `OeisA185895` | **già risolto da Epoch AI** (18 tentativi, uno riuscito) |
| `OeisA011545` (cifre di π) | i termini crescono come 10ⁿ: nessun calcolo avvicina un quadrato |
| `OeisA069923`, `A038771`, `A002326`, `A002426`, `A072200` | nel benchmark di Epoch, hanno **resistito a tre tentativi da $50** di tre laboratori diversi. Non sono inesplorati: sono il residuo |
| `Erdos1074` (numeri EHS, frontiera 2¹⁰) | la frontiera bassa non è disattenzione: i numeri EHS crescono in modo che il calcolo non segue |
| tutti gli enunciati con `Set.Infinite`, `sInf`, `Nat.nth` | un controesempio non è un caso singolo, oppure per verificarlo in Lean servirebbe contare nel kernel tutti i termini precedenti |

Due di questi meritano un'annotazione a parte, perché sono **etichette scadute**
da segnalare agli autori dell'archivio: `OeisA064169.conjecture` e
`OeisA185895.conjecture1` sono stati risolti e pubblicati, e da noi risultano
aperti. Insieme ai cinque problemi di Erdős già trovati (1, 74, 126, 548, 571)
fanno **sette segnalazioni pronte**.

---

## 2. La lista corta: dove il vantaggio è reale

Criteri, tutti necessari: la congettura è **falsificabile da un caso singolo**;
il caso singolo è **verificabile in Lean** senza `native_decide`; il costo per
caso è **misurato**, non stimato; e non risulta una ricerca sistematica
pubblicata.

### 2.1 `OeisA109909.conjecture` (e `A109908`, che è equivalente) — **in esecuzione**

> Per ogni $n > 3$ esiste $1 \le k < n$ con $k(n-k) - 1$ primo.
> (Congettura di A. Murthy, 2005.)

| | |
|---|---|
| velocità **MISURATA** | **157 000 valori di n al secondo** su un core, a n ≈ 10⁶ |
| perché è così veloce | il primo $k$ funziona quasi sempre: non serve esplorare |
| dove arriva una notte | 10⁹ su un core in 1,8 ore; 10¹⁰ con dieci core |
| verificato da noi | nessun controesempio fino a n = 4,4 milioni dopo 45 secondi |
| se si trova un controesempio | è un singolo $n$, e per $n$ moderato la confutazione si verifica anche in Lean: bisogna mostrare che per ogni $k \le n/2$ il numero $k(n-k)-1$ è composto, cioè ~n/2 controlli di primalità su numeri ≤ n²/4 |
| stato noto | citata nella raccolta di Zhi-Wei Sun ([arXiv:1211.1588](https://arxiv.org/abs/1211.1588)) e in Niu–Zhang 2024. **La frontiera pubblicata non l'ho trovata**: la nostra la stabiliamo noi |
| mai nel benchmark di Epoch | sì (MISURATO sul loro `samples.jsonl`) |

È il migliore dei candidati e sta girando: `./avvia.sh stato` per vederlo.

### 2.2 `OeisA108569.conjecture` — elementare, nessuna letteratura trovata

> I termini $k$ con $\varphi(k) = \varphi(k + \varphi(k))$ sono tutti pari,
> tranne il primo.

| | |
|---|---|
| velocità **MISURATA** | 27 000 k/s con `sympy.totient`; con un crivello sarebbe ~100 volte tanto |
| verificato da noi | fino a k = 300 000: 238 termini, l'unico dispari è k = 1 |
| il problema | l'enunciato dell'archivio parla del **k-esimo termine** (`Nat.nth`), quindi per confutarlo in Lean servirebbe contare nel kernel tutti i termini precedenti. Con un k grande non è praticabile |
| verdetto | ricerca sensata, verifica in Lean incerta: **seconda priorità** |

### 2.3 `OeisA239957.conjecture` (Sun) — cheap, già spinto un po'

> Ogni primo $p$ ha una radice primitiva della forma $k^2+1$ minore di $p$.

Verificato da noi fino a p = 200 000, nessun controesempio (pochi secondi).
Sta nella raccolta di Sun, quindi qualcuno ci ha guardato. **Terza priorità.**

### 2.4 Le nove congetture «Written on the Wall II» — l'unico filone strutturalmente diverso

Sono congetture **prodotte da un programma** sui grafi. L'archivio ne contiene
146: **39 risolte, 9 ancora aperte** — e almeno due delle risolte lo sono state
per confutazione. Una enumerazione esaustiva dei grafi connessi fino a 10
vertici (11,7 milioni) le chiude o le conferma tutte insieme.

Non è ancora attrezzata: servirebbe un enumeratore di grafi non isomorfi
(`nauty`/`geng`, non installato). **Costo: mezza giornata di lavoro mio, zero
dollari.** È il filone con il rapporto migliore fra sforzo e probabilità, dopo
il primo.

---

## 3. Perché la lista è così corta

Il conto delle frontiere basse nei docstring ne aveva promessi ventisette. Ne
restano quattro. La ragione è che **«oscuro» e «non attaccato» non sono la
stessa cosa**: le congetture OEIS con un enunciato pulito e citabile finiscono
nella raccolta di Zhi-Wei Sun, e quella raccolta è letta. Quelle che nessuno ha
guardato hanno enunciati disordinati — e su quelli il ritrovamento probabile non
è un teorema, è un **difetto di formalizzazione**.

Per questo la caccia più promettente adesso non è il calcolo bruto: è la sonda
degli artefatti, che sta passando tutti i 1188 candidati con undici tattiche a
costo zero (`scripts/sonda_artefatti.py`). L'idea viene dai file di Epoch: fra
le loro soluzioni accettate ci sono enunciati chiusi con `exact ⟨0, by simp⟩`,
perché dicevano «esiste C tale che...» e con C = 0 erano veri per niente.

---

## 4. Il bersaglio per il tentativo da $50, e perché non l'ho ancora lanciato

**Candidato in testa:** `OeisA109909.conjecture` (Murthy). Motivi:
mai toccato da Epoch (misurato); enunciato elementare in due righe; il modello
può calcolare con `sympy` nella cartella di lavoro che ora gli sopravvive fra
le chiamate; e se la ricerca locale trova un controesempio, formalizzarlo è il
tipo di lavoro Lean che la calibrazione ha misurato come facile ($0,01–0,06,
una o due iterazioni).

**Ma non lo lancerei adesso, e la ragione è che spendere ora vuol dire spendere
senza un'informazione che sta arrivando gratis.** Due cose sono in corso:

1. la **sonda degli artefatti** su tutti i 1188 candidati (~2 ore). Se segnala
   un enunciato che cede a una tattica banale, quello diventa il bersaglio: è
   un risultato quasi certo invece di una scommessa al 10–20%;
2. la **ricerca di Murthy** fino a 10⁹ (~2 ore). Se trova un controesempio, il
   tentativo da $50 cambia natura: non «risolvi questa congettura» ma
   «formalizza questa confutazione», che è il lavoro in cui l'agente riesce.

Su una congettura di tipo Goldbach come quella di Murthy, va detto chiaramente:
**una dimostrazione non è alla portata di nessuno, modello o umano.** Il valore
del tentativo sta quasi tutto nel ramo «confutazione», e quel ramo dipende dalla
ricerca locale, non dal budget. Spendere $50 prima di sapere come è andata la
ricerca è la stessa specie di errore del setaccio: comprare tentativi invece di
informazione.
