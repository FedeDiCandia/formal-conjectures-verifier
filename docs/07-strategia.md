# Strategia: come arrivare a risolvere un problema aperto

*Scritto l'11 settembre 2026, prima di spendere il budget residuo di ~$195.*

**In una riga:** il presupposto «non esistono problemi aperti facili» è
**falso per una classe precisa e numerosa**, e qualcuno l'ha già misurato:
un modello con gli strumenti giusti e **$50 per problema** ne risolve il
**30%**. Noi stavamo spendendo **$0,97** per problema. L'errore non era la
strategia: era l'ordine di grandezza.

---

## 1. Dove il ragionamento non regge

### 1.1 «Sono aperti perché matematici forti hanno fallito» — vero per i famosi, falso per la maggioranza

L'archivio non contiene 1241 congetture celebri. Contiene, **MISURATO** sullo
snapshot `main`:

| fonte | aperti verificabili |
|---|---|
| Erdős (erdosproblems.com) | 488 |
| Wikipedia | 251 |
| **OEIS** | **209** |
| Green's open problems | 83 |
| articoli | 80 + 34 (arXiv) |
| Written on the Wall II (congetture generate da un programma) | 9 |
| altro | ~87 |

I 209 problemi OEIS non sono Riemann. Sono cose come «ogni intero $n > 1$ si
scrive come somma di due quadrati, una potenza di 3 e una potenza di 5»
(A303656, di Zhi-Wei Sun). Nessun matematico forte ci ha provato sul serio:
sono stati **proposti da una persona sola, spesso l'autore della sequenza, e
mai più guardati**. È una classe di problemi genuinamente aperti *e*
genuinamente poco attaccati. Sono due cose diverse, e il ragionamento le
confondeva.

Prova ulteriore, **MISURATA** sui docstring dell'archivio: 27 problemi aperti
dichiarano da soli fin dove è stato spinto il calcolo. Alcune di quelle
frontiere sono minuscole:

| problema | frontiera dichiarata |
|---|---|
| `OeisA69923.conjecture` | controllato fino a **n = 250** |
| `OeisA38771.conjecture2` | vero per i **primi 133 termini** |
| `Erdos1074...EHSNumbers` | Hardy e Subbarao calcolarono fino a **2¹⁰ = 1024** |
| `OeisA185895.conjecture1` | controllato fino a **n = 1225** |
| `OeisA2326.conjecture2` | nessun controesempio per k, p fino a **1000** |
| `OeisA64169.conjecture` | controllato fino a **20 000** |
| `OeisA2426.conjecture` | verificato fino a 8·10⁵ |
| `OeisA105210` | fino a 10⁸ |

Un problema «verificato fino a n = 250» non è un problema su cui si sono
arenati i grandi laboratori. È un problema che **nessuno ha mai preso in
mano**. (Con una trappola, che dichiaro subito: spesso la frontiera è bassa
perché i termini crescono in fretta e calcolarne uno costa; non sempre, ma
va controllato caso per caso — è il lavoro di lettura della fase 2.)

### 1.2 «Il collo di bottiglia è l'ingegneria Lean» — vero, ma solo per una parte

**MISURATO** sulla calibrazione: i due fallimenti (`JacobianConjecture`,
`GraphConjecture65`) avevano la strategia matematica giusta e si sono fermati
sull'ingegneria Lean. Ma sono `n = 2`, ed erano **entrambi problemi in cui la
matematica era già nota** (un controesempio pubblicato). Su quelli il collo di
bottiglia è la formalizzazione, per definizione: non c'era niente da scoprire.

Su un problema davvero aperto il collo di bottiglia è la matematica. La
conclusione corretta è più stretta di quella che avevamo scritto:

> quando la matematica è nota, il limite è Lean; quando non lo è, il limite è
> la matematica. Sapere quale dei due stiamo comprando è la decisione
> strategica.

### 1.3 «Il nostro unico vantaggio è il calcolo massiccio» — il nostro calcolo non è massiccio

**MISURATO**: 84 candidati al secondo su un core, ~1000/s usando dieci core.
Una notte sono ~3·10⁷ candidati. È **niente** rispetto a chiunque abbia un
cluster, e infatti la ricerca sui numeri di Euclide ha coperto i primi sotto
3 milioni e poi è finita.

Il vantaggio vero non è la potenza: è la **selezione**. Possiamo permetterci di
spendere una notte su un problema che a nessun altro interessa. È un vantaggio
di attenzione, non di FLOPS, e va usato di conseguenza — su problemi dove la
frontiera nota è ridicola, non dove è a 10¹⁸.

### 1.4 «I grandi laboratori setacciano gli stessi problemi» — lo fanno, e il risultato è pubblico

Qui il ragionamento è giusto nella premessa e sbagliato nella conclusione.
**Epoch AI** ha pubblicato ad agosto 2026 *OEIS Open: Language Models and
Mathematical Conjectures* ([arXiv:2608.11941](https://arxiv.org/abs/2608.11941)),
e il suo benchmark è costruito **anche sui dati di formal-conjectures**, i
sottoinsiemi `{erdos, fc100open, oeis}`: gli stessi problemi che abbiamo noi.

I numeri, **MISURATI da loro**:

| | |
|---|---|
| congetture aperte OEIS nel corpus di partenza | **2649** |
| formalizzate in Lean nel benchmark | 492 |
| risolte da Claude Opus 4.8 con **$50 per problema** | **147 (30%)** |
| risolte da Claude Fable 5 sul sottoinsieme da 100, con **$200 per problema** | **44%** |
| Gemini 3.5 Flash | 22–29% |
| dare al modello 476 000 articoli di arXiv | **non ha migliorato il punteggio** |
| usare cicli di agente più sofisticati | **non ha migliorato il punteggio** |

Strumenti che avevano: bash, un editor, Lean 4 con Mathlib, **SageMath**,
Python con sympy/mpmath/numpy, e 72 ore di orologio per problema.

Tre conseguenze, tutte importanti:

1. **Risolvere una congettura aperta di questo tipo è dimostrabilmente
   possibile e costa decine di dollari, non migliaia.** Loro l'hanno fatto 147
   volte.
2. **Il 70% è rimasto irrisolto.** Il setaccio dei laboratori non prende tutto:
   lascia un residuo enorme.
3. **Noi spendevamo 50 volte troppo poco per problema.** La calibrazione aveva
   tetto $1,64 e 20 iterazioni. Loro $50 e 72 ore. Con quel tetto non
   avremmo risolto nessuno dei 147: ci saremmo fermati all'iterazione 20 con la
   strategia giusta in mano, esattamente come è successo su `JacobianConjecture`.

E c'è un rovescio da mettere in conto: **le 147 più facili sono già state
prese**, e chi arriva dopo pesca in un residuo più duro. Per questo il primo
lavoro gratuito è confrontare la loro lista di risultati con i nostri 1241
aperti.

---

## 2. Tutte le strade, con prezzi e probabilità

I costi sono **MISURATI** dove indicato; le probabilità sono **STIMATE** da me,
con il ragionamento accanto. «Successo» significa: un problema genuinamente
aperto risolto e accettato dal nostro verificatore.

### A. Congetture OEIS/oscure, con budget per problema alto (la strada di Epoch)

- **Sfrutta:** che sono aperte per disattenzione, non per difficoltà; e che il
  costo per problema è l'unica leva che si è dimostrata efficace.
- **Costa:** $50 per tentativo, ~2–4 ore di Mac ciascuno. Con $195: **3 tentativi
  seri** più una riserva.
- **Probabilità (STIMATA): 35–50%** di almeno un successo con tre tentativi.
  Parto dal 30% misurato per tentativo, e sconto per due motivi: il residuo è
  più duro di quello che hanno affrontato loro, e il nostro agente è più povero
  del loro (niente SageMath, niente bash libero, contesto limitato).
- **Come sappiamo presto che non funziona:** al primo tentativo si guarda se il
  modello arriva a produrre Lean che compila e a chiudere sotto-lemmi. Se dopo
  $50 non ha mai compilato niente di non banale, il problema non è il budget.

### B. Ricerca di controesempi oltre frontiere ridicole

- **Sfrutta:** le 27 frontiere dichiarate nei docstring, alcune a n = 250.
- **Costa:** ~$0 di API (il modello scrive il programma: $2–5 in tutto), notti
  di Mac.
- **Probabilità (STIMATA): 10–20%** di almeno un controesempio su ~8 problemi
  ben scelti. Bassa perché una frontiera bassa spesso *significa* che i termini
  costano; ma non sempre, e il costo per provarci è quasi zero.
- **Come sappiamo presto:** se il programma validato su valori noti non supera
  la frontiera pubblicata entro una notte, il problema esce dalla lista.

### C. Formalizzazioni sbagliate (la domanda 3a)

- **Sfrutta:** che 1241 enunciati scritti da molti contributori contengono
  quasi certamente errori di traduzione dalla fonte originale.
- **Costa:** gratis (lettura mia) più eventuali verifiche Lean.
- **Probabilità (STIMATA): 50–70%** di trovarne almeno uno in 455 letture. È un
  *prior*, non una misura: la nostra sonda automatica ne ha trovati **0 su 30**,
  ma cercava con tattiche, e un errore di fedeltà si trova **leggendo**, non
  con `plausible`.
- **Attenzione, ed è il punto che conta:** un enunciato sbagliato e falso si
  può confutare in Lean, e il risultato *sembra* la soluzione di un problema
  aperto. Non lo è. Il protocollo della fase 7 esiste per questo.
- **Valore reale:** alto per l'archivio, nullo per il tuo obiettivo dichiarato.

### D. Etichette «aperte» scadute

- **Sfrutta:** che erdosproblems.com e OEIS si aggiornano e l'archivio no.
  Epoch ha già risolto 147 congetture: molte sono ancora marcate `research open`
  nel nostro snapshot.
- **Costa:** gratis.
- **Probabilità: ~certa** di trovarne parecchie.
- **Valore:** serve a **non** sprecare soldi su problemi già risolti. È
  igiene, non risultato. Da fare per prima.

### E. Portare in Lean dimostrazioni formali esistenti

- **Sfrutta:** i **439 problemi** marcati `research solved` che hanno un link a
  una dimostrazione formale in un altro sistema (**MISURATO**).
- **Costa:** $2–10 per problema.
- **Probabilità: alta** (50–70% per tentativo, STIMATA, sulla base del 5 su 7
  misurato su problemi simili).
- **Valore:** contributo vero all'archivio, zero novità matematica. Non è il
  tuo obiettivo.

### F. Migliorare gli strumenti invece di comprare tentativi (domanda 3d)

Qui ho una misura esterna che contraddice l'intuito: **dare al modello 476 000
articoli e cicli di agente più sofisticati non ha migliorato il punteggio**,
mentre alzare il budget da $50 a $200 lo ha portato dal 30% al 44%.

Quindi: **niente lavoro di raffinamento**. Ma tre carenze nostre non sono
raffinamenti, sono capienza mancante, e vanno colmate perché senza quelle non
possiamo nemmeno *spendere* $50 su un problema:

1. **Il tetto di 20 iterazioni e la finestra di contesto.** Un tentativo da $50
   sono ~100–150 iterazioni: serve gestire il contesto che cresce (riassunto
   periodico) o il tentativo muore per esaurimento di contesto, non di idee.
2. **`numpy` e `sympy` in `run_python`** (domanda 3, già decisa): loro avevano
   anche SageMath.
3. **Un indice locale di Mathlib** per cercare lemmi per nome e per tipo, senza
   spendere iterazioni a tentoni.

Costo: gratuito (lavoro mio). Tempo: qualche ora. **Va fatto prima di spendere.**

### G. Modelli locali gratis sul Mac (domanda 3c)

- Su 24 GB girano modelli da 7–30 miliardi di parametri. I dimostratori
  specializzati (DeepSeek-Prover, Kimina, Goedel) sono tarati su problemi da
  olimpiade, non sull'API di Mathlib per problemi di ricerca.
- Il dato di Epoch che pesa: perfino **Gemini 3.5 Flash**, un modello di
  frontiera economico, si ferma al 22–29%. Un modello locale da 7B sta ordini
  di grandezza sotto.
- **Probabilità di un successo per questa via: ~1%.** Non zero perché è gratis
  e si può lasciar macinare, ma il rapporto fra il tempo che costerebbe
  attrezzarlo e quello che rende è pessimo.
- **Uso sensato, se mai:** far generare a un modello locale migliaia di
  candidati per una ricerca combinatoria (non dimostrazioni). Bassa priorità.

### H. Non spendere niente (domanda 3e)

- Tutto il lavoro gratuito (D, C, B, F) resta possibile e produce risultati
  reali per l'archivio.
- **Probabilità di raggiungere il tuo obiettivo: molto bassa, 3–8%** — quasi
  solo attraverso B, la ricerca di controesempi.
- È la scelta giusta *se* dopo i punti di verifica qui sotto la strada A si
  rivela chiusa.

### I. Problemi esistenziali: trovare un testimone

- **MISURATO:** 211 aperti sono della forma «esiste X tale che...», 49 su
  oggetti discreti. Per questi un solo oggetto esplicito risolve il problema, e
  verificarlo in Lean è il caso facile misurato nella calibrazione (istanze
  concrete chiuse con `decide`/`norm_num`, $0,01–0,06 l'una).
- **Sfrutta:** che cercare un oggetto è calcolo, e verificarlo è banale. È la
  forma dove il nostro Mac e il nostro verificatore rendono di più.
- **Costo:** come B. **Probabilità (STIMATA): 5–10%**, inclusa in B.
- Da usare come **criterio di selezione dentro A e B**, non come strada a sé.

### J. Le 9 congetture generate da un programma (Written on the Wall II)

- **MISURATO:** l'archivio contiene 146 teoremi WOWII: **39 risolti, 9 ancora
  aperti**. Sono congetture prodotte da un programma sui grafi, e almeno due
  delle risolte lo sono state **per confutazione** (`GraphConjecture65`, con un
  controesempio su 17 vertici).
- Sono aperte perché nessuno le ha guardate, non perché siano profonde.
  Un'enumerazione esaustiva dei grafi connessi fino a 10 vertici (11,7 milioni,
  fattibile in una notte con il programma giusto) le chiude o le conferma.
- **Probabilità (STIMATA): 15–25%** che almeno una delle 9 cada con
  un'enumerazione fino a 10–11 vertici. Il precedente dei 17 vertici avverte
  che i controesempi possono stare più in là della nostra portata.
- **Costo:** $2–5 di API per i programmi, una o due notti di Mac.

---

## 3. La strategia che consiglio

**Obiettivo dichiarato: un problema genuinamente aperto, risolto e verificato.**
La strada con la probabilità più alta è **A**, con **B+J** in parallelo perché
costano quasi nulla e usano il Mac mentre l'agente lavora.

### Ordine, con i soldi

| passo | costo | quando fermarsi |
|---|---|---|
| **0. Igiene (gratis)** — scaricare i risultati di Epoch e togliere dai bersagli tutto ciò che hanno già risolto; controllare su OEIS/erdosproblems lo stato attuale dei candidati | $0 | — |
| **1. Capienza (gratis)** — riassunto del contesto per tentativi lunghi, `numpy`/`sympy` in `run_python`, indice locale di Mathlib | $0 | se dopo mezza giornata l'agente non regge 100 iterazioni, si ripiega su tentativi da $15 |
| **2. Lettura (gratis)** — per i ~40 candidati migliori: fonte originale, frontiera verificata, esiste una ricerca sistematica? Scarto tutto ciò che è sopra 10¹² | $0 | — |
| **3. Ricerche locali (quasi gratis)** — B, I e J: programmi con checkpoint sui problemi a frontiera bassa e sulle 9 WOWII | ~$5 | se in tre notti nessuna ricerca supera la frontiera pubblicata, si chiude il filone |
| **4. Primo tentativo profondo** — $50 su **un solo** problema, scelto dalla lettura | $50 | **punto di verifica**: se non ha mai prodotto Lean che compila e chiude un sotto-lemma, il problema non è il budget: fermarsi e ripensare |
| **5. Secondo e terzo tentativo** — $50 ciascuno, su problemi diversi, solo se il punto 4 ha mostrato progresso reale | $100 | se dopo tre tentativi nessun risultato, **fermarsi** |
| **riserva** | **~$40** | serve a formalizzare e verificare un eventuale risultato, e a ritentare una volta il problema più promettente |

### Che cosa NON spendere

- **Niente setaccio**: la tua correzione era giusta, e ora c'è la misura di
  Epoch a dirci perché — non conta quanti problemi tocchi, conta quanto spendi
  su ciascuno.
- **Niente sui problemi celebri.** Erdős 366, Goldbach, Collatz: zero dollari.
- **Niente sui 1550 «risolti ma non formalizzati»**, per quanto siano il modo
  più sicuro di ottenere un risultato: non è il tuo obiettivo.
- **Niente su modelli locali** oltre a una prova a costo zero.
- **I ~$40 di riserva restano fermi** finché non c'è qualcosa da verificare.
  Se la strada A fallisce ai punti 4–5, quei soldi **non vanno spesi**: la
  prossima mossa sarebbe aspettare un modello migliore, che costa zero.

---

## 4. Le probabilità, senza addolcirle

| esito | probabilità (STIMATA) |
|---|---|
| almeno un problema genuinamente aperto risolto e verificato, con questo piano | **35–50%** |
| ...ma di significato matematico incerto, del tipo «congettura OEIS che interessa al suo proponente» | **quasi certo, se succede** |
| un problema aperto *celebre* risolto | **< 0,1%** |
| almeno una formalizzazione sbagliata trovata e documentata | 50–70% |
| almeno un controesempio oltre una frontiera pubblicata | 10–20% |
| finire con niente di pubblicabile | 20–30% |

Il 35–50% è molto più alto del 0,3% che avevo stimato ieri. La differenza non
è ottimismo: è che ieri non conoscevo il risultato di Epoch e stimavo la
probabilità di risolvere *un problema aperto medio dell'archivio* con *un
tentativo da un dollaro*. Sono due domande diverse e le risposte differiscono
di due ordini di grandezza. Sbagliavo io, e il numero nuovo è appoggiato a una
misura vera fatta da altri sugli stessi problemi.

**Il risultato realistico migliore, se la strada A non dà frutti:** un pacchetto
di lavoro onesto e verificabile — le etichette scadute segnalate agli autori
dell'archivio, una o due formalizzazioni sbagliate documentate con il confronto
fra enunciato Lean e fonte, e le frontiere computazionali di alcuni problemi
oscuri spinte più in là di quanto sia mai stato pubblicato, con i programmi e i
checkpoint a disposizione di chi verrà dopo. Non è risolvere un problema
aperto. È il tipo di contributo che rende l'archivio migliore, e costa zero.

**La cosa che mi preoccupa di più:** non che falliamo, ma che si prenda per
successo qualcosa che non lo è. Tre modi in cui può succedere, tutti già visti
in questo progetto: una formalizzazione sbagliata confutata (sembra una
scoperta), un'etichetta scaduta (il problema era già risolto in letteratura), e
`plausible` che lascia un `sorry` e fa compilare il file. Il verificatore ferma
il terzo. Per i primi due serve il protocollo, e serve applicarlo **prima** di
dire a qualcuno che abbiamo risolto qualcosa.
