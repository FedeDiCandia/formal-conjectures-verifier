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

---

## 5. Il loro repository, esaminato (aggiunta dell'11 settembre)

Ho clonato e letto `epoch-research/LeanOpenProblems` (il benchmark) e
`LeanOpenProblems-results` (1,6 GB di esiti per campione). Tutto quello che
segue è **MISURATO** contando i loro file, non riportato dall'articolo.

### 5.1 Quanti dei nostri 1241 aperti sono nel loro benchmark

| | |
|---|---|
| nostri aperti verificabili | 1241 |
| coperti dal loro benchmark | **276** |
| — per corrispondenza di nome esatto del teorema | 134 |
| — per corrispondenza di sequenza OEIS | 144 |
| **non coperti** | **965** |

Il loro benchmark è costruito su due commit dell'archivio più vecchi del
nostro: `67338a15` (20 maggio 2026) per l'insieme OEIS e `488aade2`
(22 agosto 2026) per gli Erdős. Il nostro snapshot è del 10 settembre.

Gli insiemi che hanno pubblicato:

| insieme | campioni | tentati | risolti |
|---|---|---|---|
| `oeis` | 492 | 492 | **170** |
| `erdos` | 147 | 47 | 3 |
| `erdos_autoformalized` | 20 | 20 | 2 |
| **`fc100open`** | **100** | **3** | **0** |
| `personal_corresp` | 3 | 0 | 0 |

**`fc100open` è la scoperta operativa più utile:** sono 100 problemi aperti
presi dal nostro stesso archivio, con i nostri nomi di teorema, isolati e
pronti — e li hanno **quasi mai eseguiti** (3 tentativi, 0 risolti). Di quei
100, 91 sono ancora `research open` nel nostro snapshot e 9 sono stati risolti
dall'archivio nel frattempo.

Attenzione alla composizione, che ne abbassa il valore: 48 sono problemi di
Erdős e 23 da Wikipedia, cioè la classe *famosa*, quella dove il loro tasso di
successo è del 3–8% anche spendendo **$1000 per problema** (il loro run
`erdos-ultima-alpha-1000usd`: 3 risolti su 59). Non è la classe OEIS al 30%.

### 5.2 Quali escludere perché già risolti

**Certi, corrispondenza per nome esatto — 5 problemi che Epoch ha risolto e che
il nostro archivio marca ancora `research open`:**

`Erdos1.erdos_1`, `Erdos74.erdos_74`, `Erdos126.erdos_126`,
`Erdos548.erdos_548`, `Erdos571.erdos_571`.

**Da verificare uno per uno — 48 altri**, dove combacia la *sequenza OEIS* ma
non necessariamente la congettura: le loro formalizzazioni sono indipendenti
dalle nostre e spesso riguardano un'altra affermazione sulla stessa sequenza
(hanno id come `oeis_1359_conjecture_6`, cioè la sesta congettura su A001359).
La corrispondenza per numero di sequenza è un filtro grezzo: serve a decidere
cosa leggere, non cosa escludere.

### 5.3 Il loro verificatore conviene adottarlo?

**No: è lo stesso.** Il loro `scores.json` dichiara
`"checker": "SandboxComparator"`, e il testo della verifica mostra il
medesimo flusso che usiamo noi — costruzione di `Challenge`, costruzione di
`Solution`, esportazione, confronto degli enunciati, controllo degli assiomi.
È **comparator**, lo stesso strumento.

| | loro | noi |
|---|---|---|
| confronto strutturale degli enunciati | comparator | comparator |
| controllo degli assiomi | sì | sì |
| isolamento | tre container Docker (agente, compilazione, punteggio) | `sandbox-exec` + impronta dell'archivio |
| controllo sintattico preventivo | non documentato | sì (guard, 19 costrutti) |
| modalità confutazione con sfida negata | non presente | sì |
| controllo che l'archivio non venga toccato | non documentato | sì, hash prima e dopo |

Conclusione: sul **giudizio matematico** siamo equivalenti, perché è lo stesso
comparator. Sull'**isolamento** loro sono più forti (Docker separa l'agente dal
punteggio; noi abbiamo `sandbox-exec`, che Apple dichiara deprecato). Non c'è
motivo di adottare il loro codice; c'è motivo di prendere in prestito l'idea
del container separato, se un giorno il sistema girasse su Linux.

### 5.4 Gli strumenti che davano al modello, in ordine di importanza

1. **Budget per problema alto e 72 ore di orologio.** È la leva con effetto
   misurato: 30% a $50, 44–57% a $200. Noi avevamo $1,64 e 20 iterazioni.
2. **Un terminale libero e un filesystem persistente.** Il modello scriveva
   file, invocava `lake` da sé, teneva i risultati fra un passo e l'altro. Il
   nostro `run_python` gira in una cartella temporanea **distrutta a ogni
   chiamata**: un programma di ricerca non può conservare niente.
3. **SageMath.** Un sistema di algebra computazionale completo. Noi non l'abbiamo,
   e `sympy` non è un sostituto per teoria dei numeri seria.
4. **`sympy`, `mpmath`, `numpy`.** Noi: niente.
5. **`pantograph`** — interazione programmatica con Lean (stato degli obiettivi)
   invece della sola compilazione di file interi.
6. **Uno strumento che riporta tempo e budget residui**, così il modello si
   regola da sé. Noi il budget lo conosciamo ma non lo diciamo al modello.

E i due risultati **negativi**, che valgono quanto quelli positivi: dare al
modello 476 000 articoli di arXiv **non ha migliorato** il punteggio, e nemmeno
usare cicli di agente più sofisticati. Quindi l'elenco qui sopra va preso
dall'alto: capienza e strumenti di calcolo sì, intelligenza dello scaffold no.

### 5.5 Il numero che cambia la scelta del modello

Sul sottoinsieme `lite` (100 problemi), 63 hanno resistito a **tutti e tre** i
run da $50 dei tre laboratori. Su quei 63, ecco quanti ne ha risolti ciascun run
successivo — **MISURATO**:

| run | risolti dei 63 | tasso marginale |
|---|---|---|
| `oeis-open-lite-gpt6astra` | 20 | **31,7%** |
| `oeis-open-lite-fable51` | 16 | **25,4%** |
| `oeis-lite-200usd-fable` | 7 | 11,1% |
| `oeis-lite-200usd-sol` | 6 | 9,5% |
| `oeis-lite-200usd-deep-oai` | 4 | 6,3% |
| `oeis-lite-200usd-grok46` | 3 | 4,8% |
| tre run Anthropic/Google più vecchi | 0–2 | 0–3,2% |
| `oeis-open-lite-gemini31pro` | 0 | 0% |

Due letture, entrambe importanti:

- **la generazione del modello conta più del budget.** Un modello attuale
  risolve un quarto dei problemi su cui tre modelli di frontiera precedenti
  avevano fallito spendendo $50 ciascuno;
- a parità di dollari spesi ($200 per problema), **Fable 5.1 fa 53% e Fable 5
  44% contro il 29% di Opus 4.8** sullo stesso insieme. Fable costa il doppio
  per token, e quel confronto è già al netto del prezzo.

**Conseguenza operativa: il tentativo da $50 va fatto con `claude-fable-5-1`,
non con `claude-opus-5`.** Non perché Opus 5 sia scarso — non è stato misurato
su questo benchmark — ma perché su Fable 5.1 il dato c'è ed è il migliore fra i
modelli Anthropic, a parità di spesa.

---

## 6. Le tre correzioni chieste

### 6.1 Che cosa aspettarsi da un eventuale successo

L'articolo lo dice di sé: «*The conjectures covered in this work are of
uncertain mathematical significance, and most have likely received little
previous attention.*» Sta ora in cima a `docs/STATO.md`, perché è la cosa che
va capita prima di spendere: un successo qui vuol dire **una congettura vera,
aperta e verificata, che interessava al suo proponente e forse a nessun altro**.
Non è un risultato che cambia la matematica. È un risultato vero.

### 6.2 Probabilità ricalcolate sul residuo

Il 30% valeva su problemi mai attaccati. A noi conviene mirare a due insiemi:

- i **57 problemi OEIS discreti su sequenze che Epoch non ha mai messo nel
  benchmark** (mai attaccati da loro, stessa classe di quelli al 30%);
- il **residuo** dei 492, che ha già resistito a tre tentativi da $50.

Per il residuo il tasso marginale misurato con un modello attuale è **25–32%**.
Per i mai attaccati l'ancora è il 22–30% dei run completi. Su entrambi applico
uno sconto per la nostra infrastruttura più povera (niente SageMath, niente
terminale libero, niente filesystem persistente, contesto limitato): **STIMO
10–20% per tentativo**, che è la forchetta che mi hai chiesto di usare.

| | probabilità |
|---|---|
| un tentativo da $50 risolve il problema | **10–20%** (STIMATA, ancora misurata 25–32%) |
| almeno uno su tre tentativi | **27–49%** |
| almeno uno, se prima sistemiamo la capienza e usiamo Fable 5.1 | verso l'alto della forchetta |
| un problema *celebre* (Erdős, Wikipedia) | **3–8%** anche a $1000 per problema — **misurato da loro** |

L'ultima riga è la ragione per cui non spenderemo un dollaro sui problemi
famosi: non è una mia stima prudente, è il loro risultato su 59 problemi di
Erdős a mille dollari l'uno.

### 6.3 Quanto tempo di Mac serve, e se la nostra infrastruttura regge

**Conto, da dati MISURATI.** Il costo per iterazione cresce col contesto: nella
calibrazione andava da $0,02 a $0,46, con mediana $0,043 sulla prima iterazione
e punte di $0,71 a contesto grande. Prendendo $0,25 medi, **$50 sono ~200
iterazioni**. Ogni iterazione: ~20–40 s di attesa API più 30–50 s di Lean.
Quindi:

| | |
|---|---|
| un tentativo da $50 | **3,5–5 ore** di orologio |
| tre tentativi, in sequenza | 11–15 ore, cioè una notte e mezza |
| tre tentativi, due in parallelo | ~8 ore, ma le verifiche Lean si mettono in coda (4 processi al massimo) |

**La nostra infrastruttura NON regge**, e lo dico prima di spendere. Tre cose
mancano, in ordine:

1. **Il contesto.** A 200 iterazioni la conversazione supera la finestra del
   modello. Serve un riassunto periodico: senza, il tentativo muore per
   esaurimento di contesto e i $50 sono buttati. **È il blocco vero.**
2. **La persistenza.** `run_python` lavora in una cartella temporanea distrutta
   a ogni chiamata: il modello non può costruire nulla che duri, e una ricerca
   in più passi è impossibile. Serve una cartella di lavoro per problema.
3. **I tetti.** `--max-iterazioni` a 20 e il tetto per problema a $1,64 vanno
   alzati a ~300 e $50, con il controllo preventivo che già abbiamo.

Più `numpy`/`sympy` (già deciso) e — se si vuole avvicinarsi al loro
ambiente — `sage`, che su macOS si installa con Homebrew ma è grosso: lo
metterei solo se il primo tentativo mostra che serve.

**Quindi la capienza viene prima di tutto**, come avevi previsto: sono modifiche
gratuite, mezza giornata di lavoro mio, e senza di esse i $50 non sono
spendibili in modo sensato.

---

## 7. Probabilità per famiglia, e quanti problemi nostri ci appartengono

*Aggiunta dell'11 settembre, dopo aver letto i file di Epoch AI problema per
problema. Tutti i numeri di questa sezione sono **MISURATI** contando i loro
`info.json` e `scores.json`.*

### 7.1 Il tasso dipende dalla famiglia, e la differenza è di sei volte

| famiglia | tentativi misurati | risolti | tasso | tetto per problema |
|---|---|---|---|---|
| **OEIS** (congetture su successioni, poco studiate) | 492 × 3 run | 147 / 129 / 109 | **29,9% / 26,2% / 22,2%** | $50 |
| **OEIS**, modelli attuali | 100 | 53 (Fable 5.1) / 57 (GPT-6 astra) | **53% / 57%** | $200 |
| **Erdős** (problemi con un nome e una storia) | 59 + 38 | 2 + 2 | **5,1% / 7,4%** | **$1000** |
| Erdős autoformalizzati | 17 + 9 | 1 + 1 | 5,9% / 11,1% | $1000 |
| `fc100open` (misto, dal nostro archivio) | 3 | 0 | 0% (intervallo 0–63%: **non dice niente**) | $300–1000 |

La riga da ricordare: **mille dollari per problema sui problemi di Erdős danno
il 5%; cinquanta dollari sulle congetture OEIS danno il 30%.** Non è il budget
che fa la differenza, è la famiglia.

### 7.2 Quanti dei nostri aperti appartengono a quella famiglia

| famiglia | aperti verificabili | elementari | mai nel benchmark di Epoch |
|---|---|---|---|
| Erdős | 488 | 196 | 157 |
| Wikipedia (celebri) | 251 | 165 | 151 |
| **OEIS** | **209** | **183** | **54** |
| articoli (arXiv, Paper) | 114 | 90 | 80 |
| Green's open problems | 83 | 43 | 41 |
| Millennium | 14 | 11 | 10 |
| WOWII (generate da un programma) | 9 | 9 | 9 |

- **La famiglia dove il 30% misurato si applica davvero: 54 problemi.** Sono le
  congetture OEIS del nostro archivio, elementari, che Epoch non ha mai messo nel
  suo benchmark.
- Allargando a «oscuro ed elementare, non celebre, mai toccato da loro» —
  articoli, MathOverflow, WOWII, varie — si arriva a **186**.
- I 488 di Erdős e i 251 da Wikipedia restano fuori: là il tasso misurato è il
  5%, e a mille dollari per problema.

**Conseguenza operativa:** la riserva di bersagli buoni è di 54 problemi, non di
1188. È poca, e questo mette un tetto naturale alla spesa sensata: esaurita
quella famiglia, il denaro successivo comprerebbe tentativi su famiglie dove la
misura dice 5%.

---

## 8. Tre da $50 o due da $75? Nessuno dei due

*Domanda di Federico, e la risposta viene dai loro dati.*

Il numero che ribalta la questione: **il costo mediano di un tentativo RIUSCITO
è $3,55** (Fable 5.1; $3,97 Opus 4.8; $1,84 GPT-6 astra). Quando funziona,
funziona subito. Il tetto non è quello che si spende per un successo: è quello
che si butta su un fallimento.

Quindi un «tetto da $50» non costa $50 per tentativo. Costa in media **$30,89**,
perché i successi si fermano prima (MISURATO sul run Fable 5.1). Con $195:

| tetto per problema | p(successo) | spesa media per tentativo | tentativi con $195 | successi attesi |
|---|---|---|---|---|
| $2 | 22% | $1,71 | 114 | **25,1** |
| $5 | 29% | $3,93 | 50 | 14,4 |
| $15 | 38% | $10,64 | 18 | 7,0 |
| $25 | 41% | $16,71 | 12 | 4,8 |
| **$50** | 48% | $30,89 | **6,3** | **3,0** |
| $75 | 49% | $43,81 | 4,5 | 2,2 |
| $200 | 53% | $103,01 | 1,9 | 1,0 |

Tutti **MISURATI** sul run `oeis-open-lite-fable51` (100 problemi, 53 risolti):
per ogni tetto ho contato quanti successi sarebbero arrivati entro quel tetto e
quanto si sarebbe speso in tutto.

**La curva scende in modo monotono.** Tre tentativi da $50 sono meglio di due da
$75, ma entrambi sono peggio di venti da $15 e molto peggio di cinquanta da $5.
La ragione è aritmetica: il tetto alto compra solo la coda dei successi costosi
(dal 48% al 53%, cinque punti) al prezzo di tre quarti dei tentativi.

**Due avvertenze, perché il 25,1 della prima riga non è una promessa.**

1. **Lo sconto di trasferimento.** Quel 22% è misurato sulle *loro*
   formalizzazioni, in un ambiente con SageMath e terminale libero. Le nostre
   sono scritte da altri e il nostro ambiente è più povero. **STIMO che il nostro
   tasso sia la metà del loro**, quindi dai 25 attesi si scende verso 10–12. È
   una stima, e il primo lotto di tentativi la misura.
2. **I successi da pochi centesimi sono sospetti.** Fra i loro 22 successi sotto
   $2, la mediana è di 52 righe di Lean utili — lavoro vero, non una riga — ma il
   più economico di tutti ($0,06, 17 righe) è proprio l'artefatto `C = 0`. Quindi
   ogni successo a basso costo va passato dal protocollo della fase 7 prima di
   chiamarlo risultato. Il 40% dei loro successi sono confutazioni, e le
   confutazioni a buon mercato sono il posto dove si annidano le formalizzazioni
   sbagliate.

**Il piano che ne segue è una scala, non tre affondi:** molti tentativi a tetto
basso sui 54 problemi della famiglia buona, poi si rialza il tetto **solo** sui
problemi che a tetto basso hanno mostrato di essere a un passo. È la stessa
logica del setaccio che avevi bocciato, con una differenza che conta: qui il
tasso di successo per tentativo non è una mia congettura al 2%, è il 22–53%
misurato da altri sulla stessa famiglia di problemi.

---

## 9. Fable 5.1: prezzi verificati, e la prova che funziona

### 9.1 I prezzi sono giusti nel nostro calcolo del budget

Verificati sulla pagina ufficiale
([platform.claude.com](https://platform.claude.com/docs/en/about-claude/pricing))
l'11 settembre 2026:

| | ingresso | cache 5m | cache 1h | lettura cache | uscita |
|---|---|---|---|---|---|
| Fable 5.1 | $10 | $12,50 | $20 | **$0,25** | $50 |
| Opus 5 | $5 | $6,25 | $10 | $0,50 | $25 |

Corrispondono esattamente a `agent/costi.py`. Il punto delicato è la lettura
dalla cache: **0,025x** su Fable 5.1 e Mythos 5.1, **0,1x** su tutti gli altri.
La documentazione lo dice in una nota a piè di tabella, ed è la ragione per cui
nel nostro codice i prezzi stanno in forma assoluta e non come moltiplicatori.

**Conseguenza contro l'intuito:** Fable 5.1 costa il doppio per token, ma la sua
lettura dalla cache costa la *metà* in valore assoluto. Su un tentativo lungo la
cache è la voce più grossa — MISURATO da Epoch: 36,9 milioni di token letti
dalla cache contro 685 mila in uscita — quindi il rapporto vero è **1,45x**, non
2x.

**Controprova esterna del nostro calcolo:** con quel profilo di token il nostro
`costi.py` dà **$50,00**; Epoch ha pagato **$50,0049**. È la verifica più forte
che abbiamo sul codice del budget, perché viene da una fattura di qualcun altro.
Ora è un test (`tests/test_costi.py`).

### 9.2 La prova a costo quasi zero

`WilsonPrime.not_isWilsonPrime_seven`, dimostrazione nascosta, tetto $0,60:

| | Fable 5.1 | Opus 5 (calibrazione) |
|---|---|---|
| esito | **RISOLTO** | RISOLTO |
| iterazioni | 1 | 1 |
| costo | **$0,0792** | $0,0148 |

Tutta la catena funziona con Fable 5.1: streaming, ragionamento adattivo,
`effort`, strumenti, conteggio del budget. Su una chiamata sola costa cinque
volte Opus 5, perché non c'è nessuna cache da rileggere e il vantaggio di Fable
sta tutto là: il divario si chiude quando la conversazione si allunga.

**Spesa di questa prova: $0,0792.** Residuo: ~$194,8.

---

## 10. La scala: passaggi successivi sugli stessi 54 problemi

*Progettata sui costi misurati del run `oeis-open-lite-fable51` (100 problemi,
53 risolti): per ogni tetto ho contato quanti successi arrivano entro quel tetto
e quanto si spende in tutto.*

### 10.1 I due numeri che determinano la forma della scala

**MISURATO** — quanti dei successi arrivano presto:

| tetto | problemi risolti entro quel tetto | quota di TUTTI i successi | spesa media per tentativo |
|---|---|---|---|
| $0,50 | 12% | 23% | $0,47 |
| **$2** | **22%** | **42%** | **$1,71** |
| $5 | 29% | 55% | $3,93 |
| $10 | 33% | 62% | $7,39 |
| $25 | 41% | 77% | $16,71 |
| $50 | 48% | 91% | $30,89 |
| $200 | 53% | 100% | $103,01 |

**MISURATO** — e quanto rende insistere su chi non è caduto subito:

| si passa da | a | nuovi successi | tasso condizionato |
|---|---|---|---|
| $0 | $1 | 15 su 100 | 15,0% |
| $1 | $2 | 7 su 85 | 8,2% |
| $2 | $5 | 7 su 78 | 9,0% |
| $5 | $10 | 4 su 71 | 5,6% |
| $10 | $25 | 8 su 67 | 11,9% |
| $25 | $50 | 7 su 59 | 11,9% |
| $50 | $200 | 5 su 52 | 9,6% |

Il tasso condizionato resta intorno al 10% a ogni fascia: **insistere rende
sempre un po', e mai molto.** Per questo la scala deve selezionare: il valore
non sta nell'insistere, sta nell'insistere *solo dove serve*.

### 10.2 Il criterio di promozione, meccanico

> **Passa al giro successivo il problema su cui l'agente ha consegnato almeno un
> candidato che COMBACIA con l'enunciato e ha fallito sulla dimostrazione.**

Nel rapporto dell'agente: fra le nature delle verifiche compare
`errore_tecnico` o `buco_o_assioma`. Vuol dire che il modello ha capito che cosa
dimostrare, ha scritto un file che il verificatore riconosce come «lo stesso
teorema», e si è fermato sulla prova.

Non passa chi ha solo `esplorazione` (non è mai arrivato a consegnare) o
`enunciato_sbagliato` (non ha riprodotto l'enunciato): là il problema non è il
budget. Lo applica `scripts/promossi.py`, e sulla calibrazione dà la divisione
giusta: passa `JacobianConjecture` (un candidato consegnato, fallito sulla
prova), non passa `GraphConjecture65` (zero candidati consegnati).

### 10.3 La scala consigliata

Ipotesi dichiarate: **sconto di trasferimento 0,5** (il nostro tasso è la metà
del loro, STIMATO); **un terzo dei falliti viene promosso** (STIMATO, dalla
calibrazione: 1 su 2); **il terzo promosso vale il doppio** (STIMATO).

| giro | tetto | problemi | spesa | successi attesi |
|---|---|---|---|---|
| **0. lotto di prova** | $2 | 10 | **$17** | 1,1 |
| **1. resto del primo giro** | $2 | 44 | **$75** | 4,8 |
| **2. affondo sui promossi** | $10 | ~16 | **$99** | 2,3 |
| **totale** | | | **$191** | **8,2** |

Il giro 0 non è un giro in più: è il primo giro fermato dopo dieci problemi, per
misurare lo sconto di trasferimento **prima** di spendere il resto. Costa $17 e
risponde alla domanda che nessun dato esterno può risolvere.

**Punti di verifica, dichiarati adesso:**

- dopo il **giro 0**: se i dieci problemi danno **zero** successi e **zero**
  promossi, si ferma tutto. Con lo sconto 0,5 ne attendiamo 1,1: zero su dieci
  non è impossibile (probabilità ~31% se il tasso vero è 11%), ma insieme a zero
  promossi vuol dire che l'agente non arriva nemmeno a consegnare, e allora il
  problema è l'infrastruttura, non il budget;
- dopo il **giro 1**: si ricalcola lo sconto sui 54 e si decide il tetto del
  giro 2 con i numeri veri invece delle mie stime;
- **riserva intoccabile: $4**, perché verificare un eventuale ritrovamento con
  `verify.py` costa zero dollari ma formalizzarlo può costarne qualcuno.

### 10.4 Perché non più giri

Ho provato tutte le scale da uno a quattro giri con i tetti fra $0,50 e $75. La
migliore a tre giri rende 7,65 successi attesi, quella a due 8,20. La ragione è
nella prima tabella: **il primo giro da $2 cattura il 42% di tutti i successi
possibili a qualunque prezzo.** Aggiungere gradini sposta poco e costa molto,
perché ogni giro ricomincia da zero.

Se invece il giro nuovo potesse **riprendere il lavoro** del precedente —
passargli il candidato migliore e gli errori di Lean invece di ripartire da
capo — la scala a due giri passerebbe da 7,65 a 8,20 successi attesi. È un
miglioramento reale ma modesto: **non è una precondizione**, e non lo costruisco
prima di aver misurato il giro 0.

### 10.5 Di quei successi, quanti sarebbero veri

Domanda giusta da farsi prima di festeggiare. Dei 22 successi sotto $2 nei loro
dati, la mediana è **52 righe di Lean utili** — lavoro vero. Ma il più economico
di tutti ($0,06, 17 righe) è l'artefatto `C = 0`. Quindi su ~6 successi attesi
nel primo giro, **ne aspetto 1 che sia un difetto di formalizzazione e non un
risultato**, e ognuno dei sei passa dal protocollo della fase 7 prima di essere
chiamato in qualunque modo.
