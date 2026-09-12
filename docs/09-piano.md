# Piano, ripensato da zero

*12 settembre 2026. Scritto dopo aver messo da parte tutte le decisioni
precedenti. L'obiettivo è uno: **risolvere un problema matematico non ancora
risolto**, verificato da qualcosa che non sia il nostro giudizio. Tutto il resto
è mezzo.*

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

### B. Istanze aperte di uno sforzo collettivo: bbchallenge

Il Busy Beaver Challenge ha determinato **BB(5) nel 2024** con una dimostrazione
in Rocq, in gran parte per mano di dilettanti. BB(6) è aperto e restano
**~1100 macchine di Turing «holdout»**: per ognuna, «questa macchina si ferma?» è
una domanda aperta, concreta e verificabile formalmente.

- **Sfrutta:** un'offerta enorme di problemi aperti *indipendenti*, una comunità
  che aiuta, e una verifica di terza parte (Rocq) che non richiede il nostro
  giudizio né il nostro verificatore.
- **Costo:** zero dollari. Molto tempo mio e di macchina.
- **Probabilità: 10–20%** di decidere almeno un holdout con prova accettata.
  Bassa perché quelle rimaste sono il residuo duro dopo anni di lavoro di persone
  competenti con strumenti migliori dei nostri; alcune (i «Cryptid» come
  Antihydra) sono equivalenti a problemi tipo Collatz.
- **Come sappiamo presto:** si prende un decider noto, lo si reimplementa e si
  controlla che decida le macchine che dovrebbe. Se non riusciamo a riprodurre
  risultati già ottenuti, non decideremo un holdout.
- **Richiede:** partecipare a Discord/GitHub, cioè uscire dal silenzio. È una
  decisione tua.

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

## 6. La domanda per te

Il piano ha un solo punto che dipende da te: **la strada D (dimostrazioni
informali) e la strada C (il residuo di Epoch) richiedono di ricaricare**, per
$8 la prima e $200 la seconda. La strada principale, A, no: costa $5–20 in tutto.

La mia raccomandazione: **ricarica $20 e fai A + D**, non $200 per C. La ragione è
che A è la strada con la probabilità più alta e D risponde, per meno di dieci
dollari, alla domanda che deciderà se C valga mai la pena.
