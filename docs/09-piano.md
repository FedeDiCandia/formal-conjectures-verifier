# Piano, ripensato da zero

*12 settembre 2026. Scritto dopo aver messo da parte tutte le decisioni
precedenti. L'obiettivo è uno: **risolvere un problema matematico non ancora
risolto**, verificato da qualcosa che non sia il nostro giudizio. Tutto il resto
è mezzo.*

---

## 0. Che cosa vuol dire «risolvere», per la strada A

**Va messo per scritto e resta scritto, perché è la differenza fra un risultato
vero e un risultato malinteso.**

La strada scelta non chiude una congettura. Non produce un teorema, non dimostra
che qualcosa è vero per ogni *n*, non risponde a una domanda che qualcuno ha posto
come domanda. Produce **un oggetto che batte un record pubblicato**: un codice con
più parole di quelle che si sapevano costruire, una matrice con determinante più
grande, un cammino più lungo. Il valore esatto resta ignoto anche dopo: si è solo
spostato in alto il limite inferiore, e il limite superiore resta dov'era.

In pratica, la differenza fra le due cose:

|  | chiudere una congettura | migliorare un limite (strada A) |
|---|---|---|
| che cosa si produce | una dimostrazione | un oggetto finito |
| che cosa resta dopo | la domanda è chiusa per sempre | la domanda è ancora aperta, il divario è più stretto |
| chi verifica | un referee, o un dimostratore formale | un programma di venti righe, e chiunque può rifarlo |
| come si chiama | teorema | record |
| si può sbagliare in silenzio | sì, ed è la norma | no: l'oggetto c'è o non c'è |

**È un risultato vero.** Le tabelle di questi limiti sono mantenute, citate e
usate; un miglioramento è pubblicabile, e a volte è stato pubblicato da
dilettanti. Ma se l'obiettivo è «risolvere un problema aperto» nel senso in cui lo
intenderebbe un matematico — *questa congettura è vera* — **la strada A non ci
arriva, e nessuna delle strade disponibili ci arriva con questi mezzi.** La strada
A è la cosa migliore raggiungibile, non la cosa chiesta. Tenerlo presente evita
l'errore che ho già visto in questo progetto cinque volte: chiamare «trovato»
qualcosa che era un'altra cosa.

---

## 1. Diagnosi: perché non ci siamo riusciti

### Il fatto da spiegare

In **139 chiamate** all'API, su **dieci problemi aperti**, l'agente ha consegnato
al verificatore **due candidati**. Non fallisce nel dimostrare: non arriva a
provarci.

### Tre spiegazioni MISURATE e scartate

| spiegazione | misura che la esclude |
|---|---|
| non aveva budget | nel giro 0 il controllo di spesa non è scattato nemmeno una volta: tutti e dieci si sono fermati da soli avendo speso il 6–32% del tetto |
| le istruzioni gli offrivano una via d'uscita | togliendola, la spesa per problema tripla e i calcoli raddoppiano; i candidati consegnati passano da 0 a 1 |
| era il modello | Fable 5.1 e Opus 5 si comportano allo stesso modo |

### Quello che invece è MISURATO in positivo

- L'agente **funziona** quando una dimostrazione esiste: 9 problemi su 11 già
  dimostrati nell'archivio, con la prova nascosta. La catena Lean → comparator →
  kernel regge end-to-end.
- Fa bene la **matematica**: su `A109074` ha trovato da solo il nocciolo (la
  divisibilità esatta di un prodotto di fattoriali, con un argomento p-adico); su
  `A113010` ha riprodotto la mia riduzione e l'ha spinta a n < 10¹⁵⁰⁰⁰; per
  `A108569` ha scritto un crivello dei totienti in numpy fino a 6·10⁷.
- Chi ha fatto la stessa cosa con **$50 per problema** (Epoch AI) ha risolto il
  **30%** di 492 congetture OEIS aperte. Noi abbiamo speso **$2**.

### Le due ipotesi che restano (e sono ipotesi, non misure)

**Ipotesi A — non abbiamo mai fatto l'esperimento giusto.** Il solo precedente di
successo gira a 25 volte il nostro budget per problema, con un ambiente più ricco
(terminale libero, SageMath, 72 ore). Le loro dimostrazioni riuscite vanno da 250
a 1500 righe di Lean: quel lavoro richiede decine di compilazioni fallite prima
di chiudere. Con 9–19 chiamate non c'è spazio per **cominciare**, e un modello
competente che sa di non poter finire sceglie di non iniziare. Il nostro zero
sarebbe quindi coerente con i loro dati, non in contraddizione.

**Ipotesi B — ho selezionato i problemi con il criterio sbagliato.** Ho scelto
per «se esiste un risultato, Lean lo può certificare in poche righe», che non è
«esiste un risultato». Fra i dieci, per quattro avevo io stesso già escluso il
testimone con ricerche esaustive. Ho selezionato, senza accorgermene, per
*difficoltà*.

**Una terza cosa, che non è un'ipotesi ma una proprietà del compito.** Una
dimostrazione formale non ha credito parziale: 250 righe che non compilano valgono
zero. In un compito così, un agente razionale con poco budget si ferma. **Il
problema non è che l'agente sia timido: è che gli abbiamo chiesto un lavoro
indivisibile con una moneta troppo piccola.**

---

## 2. Tutte le strade

Probabilità **STIMATE** da me, riferite a «arrivare a un risultato verificato su
un problema genuinamente aperto», con questi mezzi e qualche mese di tempo.

### A. Costruzioni che battono un record pubblicato *(non l'avevamo considerata)*

Non dimostrare un teorema: **esibire un oggetto**. Nella combinatoria estremale
molte quantità hanno tabelle di record pubblicate e mantenute — numeri di Ramsey,
Zarankiewicz, van der Waerden, Schur, cap set, no-three-in-line, Heilbronn,
righelli di Golomb, codici di copertura, sistemi di Steiner minimi. Un oggetto
che batte il record **è** il risultato, e verificarlo è controllare una proprietà
su un oggetto finito: mezz'ora di programma, nessuna formalizzazione.

- **Sfrutta:** il nostro unico vantaggio reale (12 core gratis, tempo illimitato),
  il modello dove è forte (scrivere e mutare euristiche di ricerca), e la
  verifica dove è banale (controllare un oggetto).
- **Precedente 2025–26:** AlphaEvolve ha stabilito **nuovi limiti inferiori per
  cinque numeri di Ramsey classici**, alcuni fermi da oltre un decennio, e nuovi
  limiti per i numeri di Zarankiewicz — con lo stesso metodo: un LLM che scrive e
  muta programmi di ricerca, e una verifica meccanica del risultato.
- **Costo:** $5–20 di API in tutto (il modello scrive i programmi, non cerca lui);
  il calcolo è gratis. Settimane di notti di Mac.
- **Probabilità: 20–35%.** È la più alta di tutte, per tre ragioni: il compito è
  **divisibile** (ogni miglioramento parziale è un progresso misurabile, al
  contrario di una dimostrazione), i bersagli sono **molti** (decine di tabelle),
  e alcuni record sono **vecchi** — fissati con euristiche e hardware di
  vent'anni fa.
- **Come sappiamo presto che non funziona:** prima di cercare record nuovi si
  riproducono quelli **noti**. Se in due settimane non riusciamo a ritrovare i
  record pubblicati per 5–10 quantità, la strada è chiusa e lo sappiamo gratis.

### B. Istanze aperte di uno sforzo collettivo: bbchallenge *(approfondita)*

Il Busy Beaver Challenge ha determinato **BB(5) = 47.176.870 nel 2024**, con una
dimostrazione in Rocq (ex Coq), in gran parte per mano di dilettanti coordinati su
un forum. BB(6) è aperto. Lì ci sono **i due pezzi che a noi mancano**: una
comunità che sa valutare, e una verifica meccanica di terza parte.

**Lo stato, ad agosto 2026.** La lista informale di «holdout» di @mxdys conta
**1003 macchine a meno di equivalenza** (2190 senza quozientare), per un conteggio
informale di **1101**. Tutte simulate fino a 10¹³ passi; ne restano ~150 da portare
a 10¹⁴ e ~230 a 10¹⁵. Per ognuna, «questa macchina si ferma?» è una domanda aperta,
concreta, indipendente dalle altre, e verificabile formalmente.

**Che cosa serve concretamente per contribuire.** Il sito lo dice in quattro passi,
e nessuno dei quattro richiede di essere matematico:

1. leggere la loro dichiarazione su riproducibilità e verificabilità;
2. scrivere un **decider** — un programma che decide se una classe di macchine si
   ferma — e **testarlo contro macchine di esempio e di controesempio**, cioè con
   una suite di regressione (esattamente la disciplina che abbiamo già);
3. aprire un post sul forum (`discuss.bbchallenge.org`, sezione deciders) con gli
   **indici nel seed database** delle macchine decise;
4. per una singola macchina difficile, un post dedicato nella sezione
   `individual-machines` con l'ID nel titolo.

Il codice può essere in **qualunque linguaggio** — ci sono oltre venti repository
indipendenti di deciders in C, C++, Go, Rust, Haskell, Coq, Dafny, Lean e Python.
Una **dimostrazione formale in Lean o Coq è incoraggiata ma non obbligatoria**;
loro stessi la definiscono «un'impresa estremamente esigente».

**Si può cominciare senza pubblicare niente? Sì, completamente.** Lo sviluppo di un
decider è lavoro offline: si scarica il seed database, si scrive il programma, si
gira sulle macchine di test, si confronta il risultato con quello dei deciders già
pubblicati. Si pubblica solo quando si ha qualcosa, e la pubblicazione è un post su
un forum tecnico, non un annuncio. **Non c'è nessun passo che richieda la tua
firma o la tua identità prima di avere un risultato.** E c'è una terza sezione del
forum, `results-reproduction`, dove riprodurre risultati altrui è *esplicitamente*
un contributo accettato: è il modo di entrare senza dover prima vincere niente.

**Si può lavorare in parallelo ad A senza rallentarla? Sì, ed è il motivo per cui
la tengo.** Le due strade non competono per nessuna risorsa:

| risorsa | strada A | strada B |
|---|---|---|
| denaro API | $5–20 | **zero** |
| CPU del Mac | notti, saturata | minuti per decider; la simulazione lunga è già fatta da loro |
| il mio tempo di sessione | scrivere e mutare euristiche | scrivere un decider e la sua suite |
| la tua attenzione | nessuna finché non cade un record | una decisione: se e quando pubblicare |

L'unico conflitto reale è il **mio** tempo di sessione, ed è un conflitto vero: non
posso fare bene due cose insieme. Quindi la metto in questa forma: **B parte solo
quando A ha superato o mancato il suo primo punto di verifica.** Se A supera, B
resta in panchina; se A fallisce, B è già istruita e pronta, e non abbiamo perso
due settimane a decidere cosa fare.

**Probabilità: 10–20%** di decidere almeno un holdout con prova accettata. Bassa e
lo resta: quelle 1101 macchine sono il residuo duro dopo anni di lavoro di persone
competenti, con strumenti migliori dei nostri e un database già simulato a 10¹³
passi. Alcune — i «Cryptid», come Antihydra — sono equivalenti a problemi tipo
Collatz, cioè fuori portata per principio. Ma il **valore per contributo** è alto
anche quando non si decide niente: riprodurre un risultato è accettato, e la
verifica è di terza parte, quindi per la prima volta in questo progetto **non
saremmo noi a giudicare noi stessi.**

**Come sappiamo presto che non funziona:** si prende un decider già pubblicato, si
reimplementa da zero, e si controlla che decida esattamente le macchine che
dovrebbe. Due settimane. Se non riusciamo a riprodurre un risultato già ottenuto,
non decideremo un holdout — e lo sappiamo a costo zero.

### C. Il residuo irrisolto di Epoch AI, con un modello che loro non hanno provato

Delle 492 congetture OESI aperte del loro benchmark, **322 restano irrisolte**. I
loro run hanno usato Opus 4.8, GPT-5.5/5.6, Gemini 3.5/3.1, Grok 4.6, Fable 5 e
5.1, GPT-6 astra. **Opus 5 non c'è.** E la loro misura dice che un modello
*diverso e nuovo* recupera il **27,7–33,8%** dei problemi su cui i precedenti
avevano fallito.

- **Sfrutta:** l'unico tasso di successo **misurato** che esiste per questo tipo
  di lavoro, su formalizzazioni già pronte (`Isolated/*.lean` nel loro
  repository), con la stessa verifica che usiamo noi (comparator).
- **Costo: $200** per quattro tentativi a $50 l'uno. È il numero per cui vale la
  pena ricaricare, se si ricarica.
- **Probabilità: 10–40%** di almeno un successo. La forchetta è larga perché il
  28–34% è misurato con *il loro* ambiente (terminale libero, SageMath, 72 ore) e
  il nostro è più povero; il nostro 0 su 10 dice che lo sconto può essere severo.
- **Come sappiamo presto:** il primo tentativo da $50. Se a metà budget non ha
  ancora consegnato un candidato a `lean_check`, il nostro limite non è il denaro
  ed è inutile continuare.

### D. Dimostrazione informale, revisione severa, formalizzazione solo dopo

- **Sfrutta:** che il modello è bravo nella parte matematica e si ferma davanti
  alla formalizzazione. Togliendo Lean dal ciclo si vede se il collo di bottiglia
  è quello.
- **Costo:** $0,37 per problema (misurato: autore + revisore, Opus 5, effort
  high). Venti problemi: $7,4.
- **Probabilità: 5–10%.** Il problema non è produrre un testo convincente: è che
  **né tu né io possiamo distinguere** una dimostrazione vera da una plausibile,
  e un revisore che è lo stesso modello non è una garanzia. Serve un umano
  competente, che ci porta alla strada E.
- **Come sappiamo presto:** se su venti tentativi il revisore severo non lascia
  passare niente, il collo di bottiglia era la matematica.
- **Valore collaterale alto:** è il modo più economico di capire *quale* dei due
  colli di bottiglia abbiamo, e costa meno di $8.

### E. Chiedere aiuto umano come parte del metodo

Zulip di Lean per la formalizzazione, MathOverflow per «è già noto?», il sito dei
problemi di Erdős per lo stato dell'arte.

- **Sfrutta:** che la parte in cui siamo peggio (formalizzare, giudicare novità)
  è quella che a loro costa poco.
- **Costo:** zero dollari. Richiede di pubblicare, che oggi è vietato.
- **Probabilità: 15–30%** *se* combinata con D — un risultato informale
  interessante, portato a chi sa valutarlo.
- **Rischio reale:** presentarsi con un risultato sbagliato brucia credibilità, e
  la letteratura degli ultimi due anni è piena di annunci di IA smontati in
  ventiquattr'ore.

### F. Altre fonti di problemi aperti

OEIS (2649 congetture aperte nel corpus di Epoch, di cui solo 492 formalizzate),
erdosproblems.com, Open Problem Garden, liste di Wikipedia, problemi con taglia
in denaro. **Sfrutta:** che la nostra fonte attuale (formal-conjectures) è
curata *per essere difficile*. **Probabilità:** non è una strada a sé, è un
parametro delle strade C e D — ma cambiare fonte è la modifica singola con il
miglior rapporto fra effetto e costo.

### G. Ricerca combinatoria pura, senza IA

- **Sfrutta:** 12 core e infinite notti.
- **Probabilità: 3–8%.** La lettura della letteratura ha mostrato che le
  frontiere pubblicate sono quasi sempre fuori portata (Erdős 366 a 10²²,
  Goldbach a 4·10¹⁸). Le eccezioni esistono ma sono poche.
- È dentro la strada A, che è la sua versione guidata e quindi migliore.

### H. Modelli locali

- **Probabilità: ~1%.** Su 24 GB girano modelli da 7–30 miliardi di parametri;
  perfino Gemini 3.5 Flash, un modello di frontiera economico, si ferma al 22–29%
  sul benchmark OEIS. Utile solo per macinare candidati in una ricerca, non per
  dimostrare.

### I. Modelli di altri fornitori

GPT-6 astra ha il punteggio più alto misurato (57% su OEIS Open Lite) e il costo
mediano per successo più basso ($1,84). **Sfrutta:** che la scelta del modello è
la leva più forte che conosciamo. **Costo:** un account nuovo e l'adattamento del
codice (mezza giornata, gratis). **Probabilità:** alza la strada C di qualche
punto. Va considerato se si ricarica.

### J. Non spendere e aspettare

- **Costo: zero. Probabilità: la stessa delle strade sopra, spostata nel tempo.**
- Misurato: cambiare modello recupera il 28–34% dove quadruplicare il budget
  recupera il 6%. Aspettare è la mossa con il miglior rapporto fra costo e resa
  che conosciamo — l'unico difetto è che non fa niente adesso.

---

## 3. La scelta

**Strada A come principale (costruzioni che battono un record), strada D come
diagnosi parallela, strada C solo se decidi di ricaricare.**

La ragione è una sola, e viene dalla diagnosi: **il compito che ci ha fermati è
indivisibile, e questo è divisibile.** Una dimostrazione Lean da 250 righe vale
zero fino all'ultima riga; una costruzione che batte un record si migliora di un
passo alla volta, e ogni passo si misura. Tutto il resto — verifica banale,
compute gratis, precedente recente, molti bersagli — viene dopo questa.

### Il piano

**Fase 1 — riprodurre i record noti (due settimane, ~$5).**
Si scelgono 8–10 quantità con tabelle di record pubblicate e verifica semplice
(Ramsey piccoli, Zarankiewicz, van der Waerden, Schur, no-three-in-line, righelli
di Golomb, cap set, codici di copertura). Per ciascuna: il modello scrive il
verificatore (controlla che un oggetto abbia la proprietà) e una ricerca di base;
noi riproduciamo il record pubblicato.
- **Punto di verifica:** se in due settimane non riproduciamo i record di almeno
  5 quantità su 8, la strada è chiusa. Costo del fallimento: $5 e due settimane
  di macchina.

#### La lista di fase 1, con la provenienza di ogni record

Questa è la parte più importante della fase 1, e viene dalla tua osservazione:
AlphaEvolve girava sull'hardware di Google, noi abbiamo 12 core. Quindi la
selezione non si fa per «quanto è bello il problema», si fa per **chi ha fatto il
record attuale e con che cosa**. Ho cercato la provenienza di ognuno.

**TENIAMO** — record ottenuti con euristiche semplici, su hardware alla nostra
portata, e verificabili in modo esatto con aritmetica intera:

| quantità | record attuale: metodo e hardware | verifica | perché è alla nostra portata |
|---|---|---|---|
| **codici binari a peso costante** A(n,d,w) — tabelle di Brouwer, n≤64, d=4…18 | i limiti del 1990 di Brouwer–Shearer–Sloane–Smith sono ancora in tabella, e **i listati dei codici sono andati perduti**; i miglioramenti recenti vengono da *tabu search a livello di scambi di bit* e da euristiche greedy (24 celle migliorate nel 2026 così); il 2019 di Braun–Humpich–Laaksonen–Östergård usa gruppi di automorfismi | banale ed esatta: distanza di Hamming a coppie, aritmetica intera | centinaia di celle con divario fra limite inferiore e superiore, molte ferme da decenni; nessun cluster dietro |
| **codici binari generali** A(n,d) — stessa fonte, n=6…28, d=4…16 | attribuzioni dal **1978** al 2019; una trentina di celle con divario aperto (per es. A(17,4) fra 2816 e 3276) | identica alla precedente | frontiera vecchia, tabella piccola e precisa, ogni cella è un bersaglio nominato |
| **codici di copertura** K(n,R) — tabelle di Kéri | tabelle **aggiornate per ultimo fra il 2008 e il 2011**; record storicamente da tabu search e annealing | esatta: ogni parola dista ≤ R da almeno un codeword (2ⁿ controlli, fattibile per n≲22) | otto anni di immobilità significano hardware di due generazioni fa |
| **array di copertura** CAN(t,k,v) — tabelle di Colbourn | *simulated annealing*, tabu search, post-ottimizzazione randomizzata; un singolo lavoro ha prodotto **579 nuovi limiti superiori** con annealing a due stadi | esatta: si enumerano le t-uple di colonne e i vᵗ valori | tabella enorme, metodi semplici, nessuna barriera di compute |
| **determinante massimo** di matrici ±1 | record di Orrick–Solomon del **2003–2005**, con ricerca euristica; restano aperti gli ordini 29, 33, 45, 49 (i soli con n≡1 mod 4 sotto 50) | esatta: determinante intero senza frazioni (Bareiss) | hardware di vent'anni fa. **Attenzione:** il sito `indiana.edu/~maxdet` non risponde più — bisogna recuperare la tabella dal survey del 2021 o da archive.org |
| **snake-in-the-box / coil-in-the-box** | limiti inferiori da *algoritmi genetici* («Mitosis GA») e da una ricerca **Monte Carlo** che gli autori descrivono come «considerevolmente più rapida e senza taratura»; un censimento del 2026 ha rinfrescato le dimensioni 9–13 | esatta: si controlla che il cammino sia indotto nell'ipercubo | metodi che girano su una macchina sola. Rischio: la frontiera è stata appena toccata |

**SCARTIAMO SUBITO**, con la ragione precisa:

| quantità | perché la scartiamo |
|---|---|
| **numeri di van der Waerden**, limiti inferiori | il record di Monroe viene da **calcolo distribuito: 2 teraflops per 12 mesi**, primi esauriti fino a 950 milioni. Non è una gara che possiamo fare |
| **no-three-in-line** | frontiera **in movimento adesso**: n=72 trovato da Marijn Heule il 25 giugno 2026, n=74 da Thomas Prellberg il 20 luglio 2026. Heule è l'autore delle dimostrazioni SAT più grandi mai fatte. Competere qui è la definizione di spreco |
| **numeri di Schur** | S(5)=160 stabilito da Heule con SAT massivamente parallelo: **oltre 14 anni-CPU** e una dimostrazione di **2 petabyte** |
| **righelli di Golomb ottimali** | OGR-28 chiuso da distributed.net dopo **otto anni e mezzo** di rete di volontari |
| **cap set, e i numeri di Ramsey in cima alla tabella** | presi da AlphaEvolve e FunSearch, sull'infrastruttura di Google. I limiti inferiori di Ramsey *classici* restano invece da annealing e tabu su grafi circolanti (Exoo, Harborth–Krause): li teniamo **come osservazione, non come bersaglio**, perché cinque sono appena caduti e il resto è il residuo |
| **triangolo di Heilbronn** | doppio problema: la frontiera attuale usa **MINLP con solutori industriali** (Gurobi), e la verifica richiede aritmetica reale certificata, non interi. Da notare però che i record per n=13…16 sono di **dilettanti** (Karpov, Beyleveld): il precedente esiste, è la verifica che non ci conviene |

**Una precisazione onesta su «solutori industriali».** Il criterio che mi hai dato
è «scarta dove la frontiera è stata spinta con cluster o con SAT industriale», e
l'ho applicato. Ma va distinto un caso: il lavoro del 2026 che ha alzato
A(23,6,10) e A(24,6,10) usa **CHILS**, un risolutore per insieme indipendente di
peso massimo — che però gira **su una macchina sola ed è libero**. Quel tipo di
strumento non è una barriera per noi: è un'arma che possiamo prendere anche noi, e
sui nostri 12 core. La barriera vera è il **calcolo distribuito su anni** (van der
Waerden, Golomb) e la **gara con chi ha già l'infrastruttura** (no-three-in-line,
cap set). La distinzione è: scartiamo dove il record costa anni-CPU, non dove
costa un buon algoritmo.

**Fase 2 — scegliere i bersagli con la frontiera più vecchia (gratis).**
Fra quelli riprodotti, si tengono quelli dove il record è vecchio, ottenuto con
euristiche semplici, o dove la tabella pubblicata ha buchi. È lo stesso lavoro di
lettura che ho già fatto per l'archivio, e stavolta su tabelle piccole e precise.

**Fase 3 — ricerca guidata (settimane di notti, ~$10 di API).**
Il modello scrive e muta le euristiche; la macchina gira; ogni nuovo massimo si
confronta col record. Il ciclo è quello di AlphaEvolve, in piccolo: proponi,
valuta, conserva il migliore, muta.
- **Punto di verifica:** dopo un mese, se non abbiamo **pareggiato** un record in
  almeno un bersaglio, fermarsi. Pareggiare è la soglia minima: chi non pareggia
  non supera.

**Fase 4 — se un record cade.** Protocollo di [docs/04](04-protocollo-ritrovamenti.md)
per intero, con un passo in più che qui è decisivo: **ricontrollare che il record
pubblicato sia davvero quello attuale**, perché le tabelle si aggiornano e la
letteratura sta correndo. Poi, e solo poi, si decide se e a chi dirlo.

**In parallelo, gratis: fase D.** Venti problemi, dimostrazione informale più
revisione severa, $7,4 — ma **solo se ricarichi**, perché con $3,50 non ci stanno.
Serve a rispondere a una domanda che vale più del suo prezzo: il collo di
bottiglia è Lean o è la matematica? Se la risposta è «Lean», la strada C diventa
molto più attraente; se è «la matematica», tutte le strade che passano per una
dimostrazione si chiudono e resta solo A.

### Fase 1: quello che è **misurato**, dopo la prima sessione

Aggiornato l'11 settembre 2026, la sera dello stesso giorno in cui il piano è
stato approvato. Il punto di verifica della fase 1 era: *«se in due settimane non
riproduciamo i record di almeno 5 quantità su 8, la strada è chiusa».* Ecco i
numeri, tutti su A(n,d,w), la prima famiglia della lista.

**Passo zero — sappiamo leggere e controllare i record?**

| | |
|---|---|
| codici espliciti pubblicati nelle tabelle | 361 |
| **confermati esattamente** (dimensione e validità identiche alla tabella) | **331** |
| non letti (varianti di formato ancora da gestire) | 25 |
| non validi come li leggiamo noi (quasi certamente formato) | 3 |
| discordi | 2 |

Per farlo è stato necessario dedurre tre convenzioni che il sito **non documenta**:
la posizione 0 è il carattere più a destra; nei formati ciclici i blocchi si
contano da sinistra nella stringa; un resto più corto dell'ultimo blocco è fatto di
posizioni ferme. Ognuna è stata trovata perché la convenzione sbagliata produceva
un codice **non valido** — cioè il verificatore ha fatto il suo lavoro tre volte.

**Il metodo, imparato leggendo la fonte.** I record non sono pubblicati come
elenchi di parole: sono **un gruppo di permutazioni più poche parole seme**. Un
codice di 5558 parole di lunghezza 24 sta in venticinque righe: gruppo di ordine
504, 19 semi. Non è solo un formato compatto, è **il metodo con cui questi record
sono stati trovati** — non si cercano 5558 parole, si cerca un gruppo adatto. È
l'informazione più utile raccolta finora sulla strada A, e costa zero.

**Passo uno — il nostro motore, da zero.** Due motori, perché il primo ha un limite
di principio.

*Motore a orbite* (cerca un codice invariante sotto un gruppo): elegante e veloce,
ma su A(21,10,9) le orbite sotto Z₂₁ hanno taglia 7 o 21 e nessuna somma di 7 e 21
fa 27, che è il limite pubblicato. **Nessuna quantità di ricerca può arrivarci per
quella strada:** quel record non è invariante sotto quel gruppo.

*Motore a ricerca locale* (tabu search su scambi di parole, come i lavori recenti
delle tabelle): non assume niente. Risultati, con **3000 iterazioni per cella,
pochi secondi ciascuna**:

| prova | esito |
|---|---|
| raggiunge gli ottimi **noti** (26 celle con valore esatto) | **23 su 26** |
| **non** supera un ottimo noto — prova di falsificazione | **26 su 26** |
| pareggia il limite inferiore pubblicato (119 celle aperte) | **78 pareggiati, 41 sotto** |
| supera un limite pubblicato | **0** |

**Il punto di verifica è superato largamente, e in una sessione invece di due
settimane.** Ma va detto con precisione che cosa significa e che cosa no:

- **Significa** che l'infrastruttura c'è, che il verificatore è esatto e
  indipendente, che il motore è calibrato su ottimi noti, e — la cosa che conta
  più di tutte — che **non ha mai rivendicato più di un valore dimostrato ottimo**.
  Delle tre prove, la seconda è quella che rende credibili le altre.
- **Non significa** che siamo vicini a un record. Zero limiti superati, e i 41
  «sotto» sono le celle dove servirebbe il lavoro vero: 3000 iterazioni sono
  secondi, non notti. La fase 3 è precisamente questo, e il punto di verifica
  della fase 3 resta quello scritto: **dopo un mese, se non abbiamo pareggiato un
  record in un bersaglio scelto, si smette.**

### Fase D: la risposta, arrivata prima del previsto e a $2

La fase D doveva rispondere a una domanda: **il collo di bottiglia è Lean o è la
matematica?** Ha risposto subito, in un modo che non avevo previsto.

Misurato su `OeisA108569.conjecture` (dimostrare che una certa successione OEIS ha
tutti i termini pari), con il problema e tutte le sue definizioni in ingresso, e
**nessun Lean di mezzo**:

| configurazione | token in uscita | di cui ragionamento | risposta | costo |
|---|---|---|---|---|
| effort `high`, tetto 32k | 32.000 | **32.000** | **nessuna** | $0,81 |
| effort `medium`, tetto 24k | 24.000 | **24.000** | **nessuna** | $0,61 |

Il modello **esaurisce tutto lo spazio pensando e non scrive niente**. Non è un
caso limite: è successo a tutti e due gli sforzi provati, e nei primi due problemi
del giro vero — dove il revisore severo si è ritrovato a recensire una pagina
bianca, e ha giustamente scritto «la dimostrazione rivendicata è vuota».

Due conseguenze, di peso diverso.

1. **Un difetto nostro, corretto.** Lo script pagava e registrava un esito senza
   accorgersi che la risposta era vuota. Ora si ferma con il motivo esatto
   (`stop_reason`, token di ragionamento, tetto usato). Pagare e non ricevere
   nulla non è un esito ammissibile. Costo dell'errore: $0,73.
2. **Un fatto sul compito, non sullo strumento.** Il tentativo di forzare un
   bilancio di ragionamento fisso è impossibile su questo modello — l'API risponde
   che `thinking.type.enabled` non è supportato e che si deve usare `adaptive` con
   `effort`. Quindi l'unica leva è l'effort, e a due livelli su tre il modello non
   conclude.

**La stima di costo della fase D era sbagliata di circa sei volte.** Avevo scritto
$0,37 per problema; il solo autore costa $0,61–0,81 *e può non produrre nulla*. Su
venti problemi non sono $7,4 ma $25–50, senza garanzia di una riga di output. Con
$20 di ricarica **la fase D come progettata non si fa**: va ridotta a pochi
problemi con un tetto alto, oppure abbandonata.

E c'è una lettura più severa, che va detta perché è quella che conta: **su un
problema aperto, togliendo Lean di mezzo, il modello ragiona per trentaduemila
token e non arriva a una conclusione da scrivere.** È esattamente la diagnosi della
[sezione 1](#1-diagnosi-perché-non-ci-siamo-riusciti) vista da un'altra parte — non
fallisce nel formalizzare, non arriva a una tesi. Se il prossimo test a effort
basso non produce una dimostrazione leggibile, la risposta alla domanda della fase
D è **il collo di bottiglia è la matematica**, e va scritta così.

### Se A fallisce

Nell'ordine: **B** (bbchallenge, gratis, richiede di uscire dal silenzio), poi
**J** (aspettare un modello nuovo e ripetere A e C), e **non** insistere su C con
più denaro: la misura dice che il denaro sullo stesso modello non compra niente.

---

## 4. Che cosa serve ancora di quello che abbiamo costruito

**Serve:**

| pezzo | perché |
|---|---|
| l'infrastruttura per le ricerche lunghe (checkpoint, ripresa, isolamento, `verifier/ricerca.py`) | è il cuore della strada A |
| `run_python` con `numpy`/`sympy`/`numba` e la cartella persistente | il modello ci scrive e ci prova le euristiche |
| il conteggio rigoroso della spesa (`agent/costi.py`) | vale per qualunque strada a pagamento, ed è verificato contro una fattura vera |
| il registro riga per riga e `./avvia.sh guarda` | serve a te per vedere che cosa succede |
| il protocollo dei ritrovamenti e i test dei cinque falsi positivi | sono la parte che impedisce di annunciare cose che non ci sono. **È il pezzo più prezioso del progetto**, e vale su qualunque strada |
| la documentazione delle misure | è l'unica ragione per cui questo piano si appoggia a numeri |

**Non serve più (per la strada A):**

| pezzo | destino |
|---|---|
| il verificatore Lean + comparator, la sandbox, l'impronta dell'archivio | restano pronti, ma la strada A non li usa: un oggetto si verifica controllandolo. Tornano utili solo se si riprende una strada che passa per Lean (C, D+E) |
| l'indice dei 5271 teoremi, la selezione dei 54 e dei 39, le sfide negate | legati a formal-conjectures. Da mettere in archivio, non da buttare |
| la sonda degli artefatti | il suo rendimento finora è zero segnalazioni vere su ~350 problemi. Sta ancora girando: se finisce a zero, è un risultato (le formalizzazioni reggono) e il pezzo va in archivio |
| la scala, i giri, i tetti | erano un piano di spesa per una strada che la misura ha chiuso |

**La lezione che tengo di più**, e che non è tecnica: delle cose costruite, quella
che è servita davvero è stata **la disciplina sui falsi positivi**. Cinque volte
la macchina ha detto «trovato» e cinque volte era sbagliato, e ogni volta è stato
un controllo — non un'intuizione — a fermarla. Su qualunque strada futura, quella
parte va tenuta accesa.

---

## 5. Brutalità sulle probabilità

- **Che questo progetto risolva un problema che un matematico chiamerebbe
  aperto:** con il piano sopra, **20–35%** entro qualche mese. Quasi tutta quella
  probabilità sta nella strada A, e «risolvere» significherà **un limite
  inferiore migliorato in combinatoria estremale**: un numero in una tabella che
  cambia, non un teorema con un nome.
- **Che risolva un problema *famoso*:** sotto lo **0,1%**. Non è la strada e non
  sono i mezzi.
- **Che l'obiettivo sia irraggiungibile con questi mezzi:** lo metto al
  **50–70%**, e va detto. I mezzi sono un portatile, qualche decina di dollari e
  un modello che gli altri hanno già in mano; chi ha ottenuto risultati su questi
  problemi nel 2025–26 lo ha fatto con cluster e gruppi di ricerca.
- **Quello che è già stato ottenuto, e che nessuno può togliere:** frontiere
  computazionali stabilite dove non risultava una ricerca pubblicata, sette
  etichette scadute individuate, un difetto vero nella configurazione di build di
  un archivio di Google DeepMind, e un verificatore che ha rifiutato cinque volte
  quello che la nostra stessa macchina voleva far passare. Non è un problema
  aperto risolto. È lavoro onesto, e sta tutto scritto.

---

## 6. La decisione presa

Federico ha approvato l'11 settembre 2026: **strada A come principale, strada D in
parallelo, ricarica di $20.** Con le tre aggiunte che ha chiesto e che sono
incorporate qui sopra:

1. la selezione di fase 1 si fa **per provenienza del record** — hardware e metodo
   dietro il limite attuale — e non per interesse del problema;
2. che cosa significa «risolvere» per la strada A resta scritto in cima
   ([sezione 0](#0-che-cosa-vuol-dire-risolvere-per-la-strada-a));
3. la strada B è istruita in dettaglio e messa in panchina, pronta a partire al
   primo punto di verifica di A.

Il residuo di Epoch (strada C, $200) **non si fa adesso**: prima la strada D deve
dire se il collo di bottiglia è Lean o è la matematica.

---

## Fonti

Provenienza dei record e stato degli sforzi collettivi, consultati l'11 settembre
2026:

- Codici a peso costante, tabelle e attribuzioni: [aeb.win.tue.nl/codes/Andw.html](https://aeb.win.tue.nl/codes/Andw.html) · codici generali: [binary-1.html](https://aeb.win.tue.nl/codes/binary-1.html)
- Miglioramenti recenti con tabu search: [arXiv:2603.00174](https://arxiv.org/abs/2603.00174) · con solutore MWIS su macchina singola: [arXiv:2607.19550](https://arxiv.org/abs/2607.19550)
- Codici di copertura, tabelle di Kéri: [old.sztaki.hu/~keri/codes](http://old.sztaki.hu/~keri/codes/)
- Determinante massimo, survey 2021: [arXiv:2104.06756](https://arxiv.org/abs/2104.06756)
- Snake-in-the-box, censimento 2026: [arXiv:2607.15270](https://arxiv.org/abs/2607.15270)
- van der Waerden con calcolo distribuito: [Monroe, JCMCC 128](https://combinatorialpress.com/jcmcc-articles/volume-128/new-lower-bounds-for-van-der-waerden-numbers-using-distributed-computing/)
- No-three-in-line, record di giugno–luglio 2026: [wwwhomes.uni-bielefeld.de/achim/no3in](https://wwwhomes.uni-bielefeld.de/achim/no3in/readme.html)
- Schur number five: [arXiv:1711.08076](https://arxiv.org/abs/1711.08076) · Golomb OGR-28: [distributed.net/OGR](https://www.distributed.net/OGR)
- Ramsey piccoli, survey dinamico: [Radziszowski, DS1](https://www.combinatorics.org/files/Surveys/ds1/ds1v16-2021.pdf)
- Heilbronn, certificazione e coordinate esatte: [arXiv:2603.11107](https://arxiv.org/html/2603.11107)
- bbchallenge: [come contribuire](https://bbchallenge.org/contribute) · [stato di BB(6)](https://wiki.bbchallenge.org/wiki/BB(6)) · [BB(5) in Rocq](https://arxiv.org/pdf/2509.12337)
