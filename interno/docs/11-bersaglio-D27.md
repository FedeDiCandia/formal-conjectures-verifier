# Il passo 0 applicato al nostro stesso bersaglio: D(27,5,2)

*12 settembre 2026. Tre controlli chiesti da Federico prima di continuare: la
citazione, lo stato del problema, il blocco fissato.*

**Il bersaglio.** A(27,8,5) della tabella di Brouwer. Con t = w − d/2 = 1 è il
**numero di pacchetto con λ = 1**: il massimo numero di sottoinsiemi di 5 elementi
di un insieme di 27, in cui ogni coppia di punti compare al massimo una volta. La
tabella dice 31 ≤ A(27,8,5) ≤ 32.

---

## 1. La citazione: il contenuto reggeva, la fonte no

**Che cosa avevo scritto** (in `ricerca/pacchetto.py` e in chat): «per v ≡ 7, 11,
15 (mod 20) si ha P(5,v) = J(5,v), con possibili eccezioni v ∈ {27, 47, 51, …}» —
**senza fonte**. Era il riassunto prodotto dallo strumento di ricerca, e il primo
link che avevo davanti era *«Packing pairs by quintuples with **index 2**»*. Non
avevo controllato a quale parametro si riferisse la frase. È esattamente l'errore
che il protocollo deve impedire.

**Che cosa risulta dopo il controllo.** v = 27 compare come «possibile eccezione» in
**tre problemi diversi**:

| problema | fonte | è il nostro? |
|---|---|---|
| packing di coppie in quintuple, **λ = 2**, v dispari, v ≢ 13 (mod 20): possibili eccezioni v = 19, 27, 137, 139, 147 | articolo su *Discrete Math.*, titolo «Packing pairs by quintuples with index 2» | **no** |
| packing **diretti** con k = 5: eccezioni possibili (v,λ) ∈ {(19,1), (27,1), (43,3)} | Burgess, Danziger, Horsley, Javed, *Packing designs with large block size*, luglio 2025, Teorema 1.7 (testo letto) | **no**: un packing diretto è un oggetto diverso |
| packing ordinari, **λ = 1**, v ≡ 7, 11, 15 (mod 20): numero di pacchetto ⌊v⌊(v−1)/4⌋/5⌋ tranne 11, 15 e forse {27, 47, 51, 67, 87, 135, 187, 231, 251, 291} | **Yin & Assaf, *Constructions of optimal packing designs*, J. Combin. Designs 6 (1998) 245–260** | **sì** |

La terza riga è quella giusta, e lo si vede dalla formula: ⌊v⌊(v−1)/4⌋/5⌋ è il limite
di Johnson–Schönheim per λ = 1. **Ma va detto come l'ho letta: di seconda mano**,
nella trascrizione che Brouwer tiene nei commenti HTML della sua pagina dei codici a
peso costante, accanto alla nota «135 was settled later». Non ho letto l'articolo
del 1998.

**Correzioni fatte:** la citazione in `ricerca/pacchetto.py` ora ha fonte, forza
dichiarata e l'avvertenza sui tre problemi; il protocollo ([docs/04](04-protocollo-ritrovamenti.md),
passo 3) ha una regola nuova — *prima di usare un risultato citato, controlla che
riguardi il nostro parametro*.

---

## 2. È aperto oggi? Per quanto posso stabilire, sì

| fonte | che cosa dice su v = 27, λ = 1 | forza della prova |
|---|---|---|
| Yin & Assaf 1998 | «possibile eccezione» | seconda mano, via Brouwer |
| A. C. H. Ling, *Packings with block size five and index one: v ≡ 2 (mod 4)*, Ars Combin. 63 (2002) 223–233 | tratta solo v ≡ 2 (mod 4); 27 ≡ 3 (mod 4), quindi **non lo tocca** | titolo accertato, testo non letto |
| Aw, Chee & **Ling**, *Six new constant weight binary codes*, Ars Combin. 67 (2003) 313–318 | alzano il limite a **A(27,8,5) ≥ 31**, un anno dopo il lavoro di Ling sui packing con λ = 1: non sarebbe servito se il caso fosse chiuso | accertato |
| Abel, Assaf, Bluskov, Greig, Shalaby, J. Combin. Des. 18 (2010) 337–368 | per λ = 1 estendono le condizioni di non raggiungibilità del limite alle classi (20t+9,5,1) e (20t+17,5,1); 27 = 20+7 **non è in quelle classi** | solo l'abstract |
| pagina di Brouwer, con note datate fino al **30 agosto 2026** | **31–32** per A(27,8,5), fonte ACL 2003; nei commenti annota che 135 e 432 sono stati chiusi in seguito, **non 27** | accertato |
| Burgess, Danziger, Horsley, Javed (2025) | «many values for k = 5 are known», rimando al Handbook 2007 per i dettagli | accertato, testo letto |
| *Handbook of Combinatorial Designs*, 2ª ed. (2007), §VI.40 «Packings» (Stinson, Wei, Yin) | **non letto** | — |
| Meszka & Rosa, *Block Size Five: Quo Vadis?* (2023) | **non letto** (solo i riferimenti, che citano Ling 2002) | — |

**Verdetto: non ho trovato nessuna fonte che chiuda il caso, e ne ho trovate diverse
che lo trattano come aperto, fino a una tabella curata e aggiornata ad agosto 2026.**
Resta vero che una ricerca che non trova niente è **prova debole**. I due buchi veri
sono il capitolo del Handbook del 2007 e il testo completo di Abel et al. 2010:
entrambi sono in biblioteca, non in rete. Se si potesse vedere una copia del
Handbook, la tabella di §VI.40 risolverebbe il dubbio in un minuto.

**I limiti superiori, ricontrollati per calcolo** (`ricerca/limiti_d27.py`):

* Johnson–Schönheim: ⌊27/5 · ⌊26/4⌋⌋ = **32**;
* la condizione di Hanani, che abbassa il limite di 1, richiede (v−1) ≡ 0 (mod k−1):
  26 mod 4 = 2, **non si applica**;
* il secondo limite di Johnson per d = 32 blocchi: 5·32 = 160 = 5·27 + 25, quindi
  q = 5, r = 25, e d(d−1) = 992 ≥ q(q−1)v + 2qr = 540 + 250 = 790: **32 è
  permesso**.

Quindi 32 non è escluso da nessuno dei limiti noti che so calcolare, e la domanda
«31 o 32?» è ben posta.

### Che cosa leggere in biblioteca, esattamente

Una copia del *Handbook* risolve il dubbio principale. Istruzioni pensate per chi non
è del mestiere.

**Il libro.** C. J. Colbourn e J. H. Dinitz (a cura di), *Handbook of Combinatorial
Designs*, **seconda edizione**, CRC Press / Chapman & Hall, 2007 (ISBN
978-1-58488-506-1). La prima edizione (1996) è più vecchia e non basta.

**Il capitolo.** Parte VI, capitolo **40, «Packings»**, di D. R. Stinson, R. Wei e
J. Yin, **pagine 550–556**. Sette pagine: si può leggere tutto.

**Il nostro caso, in tutti i nomi con cui può comparire.** Blocchi di **5** punti,
**coppie** (t = 2), **indice 1** (λ = 1), **v = 27** punti. Il numero cercato può
essere scritto D(27,5,2), D(27,5,1), D₁(27,5,2), PDN(27,5) o simili: quello che
conta è che ci sia *5* come taglia dei blocchi e *1* come indice. Il limite
superiore è chiamato «Schönheim bound», «Johnson bound», J(v,5,1) o U(v,5,1), e per
v = 27 vale **32**.

**Che cosa cercare.** Un teorema o una tabella sui packing con **k = 5** e
**λ = 1**. Probabilmente dice che il numero di pacchetto è uguale al limite
superiore «except» (tranne) alcuni valori, e «possibly except» (forse tranne) altri.
Serve la riga che riguarda **v ≡ 7 (mod 20)**, oppure v ≡ 3 (mod 4), oppure un
elenco di valori piccoli.

**Come leggere l'esito.**

| che cosa trovi | che cosa significa | che cosa facciamo |
|---|---|---|
| 27 compare fra i valori **possibili** eccezioni («possibly», «unknown», «open») | nel 2007 era aperto, come dice Brouwer oggi | continuiamo |
| una riga che dà **D(27,5,…) = 31** o **= 32**, oppure 27 fra le eccezioni **certe** con un valore | **il valore è determinato** | ci fermiamo: fotografa la riga e il numero di riferimento bibliografico accanto |
| la classe v ≡ 7 (mod 20) ha un elenco di eccezioni **senza** 27, e 27 non è altrove | quasi certamente chiuso fra il 1998 e il 2007 | ci fermiamo: fotografa l'enunciato e il riferimento citato, lo cerchiamo |
| non trovi niente su k = 5, λ = 1 | il capitolo rimanda altrove | fotografa l'indice del capitolo e la bibliografia |

**Non confondere** con tre cose vicine che nel libro stanno in altri capitoli: le
*coverings* (capitolo VI.11, dove ogni coppia è coperta **almeno** una volta), i
*directed designs* (VI.20), e i packing con **λ = 2**. Sono tutti problemi in cui 27
compare come caso speciale, e nessuno è il nostro.

**Se c'è tempo, due verifiche in più**, in ordine di utilità:

1. **Yin & Assaf**, *Constructions of optimal packing designs*, *Journal of
   Combinatorial Designs* **6** (1998) 245–260. È la fonte che ho letto solo di
   seconda mano: il teorema principale deve elencare 27 fra le possibili eccezioni.
2. **Abel, Assaf, Bluskov, Greig, Shalaby**, *New results on GDDs, covering, packing
   and directable designs with block size 5*, *Journal of Combinatorial Designs*
   **18** (2010) 337–368. È il lavoro più recente su questi packing: cercare «27» nelle
   tabelle dei casi con λ = 1.

Una foto di ogni pagina rilevante basta: le leggo io.

---

## 3. Il blocco fissato {25,1,5,9,13}: ricontrollato, e comunque tolto dal calcolo che conta

**L'argomento.** Dopo aver fissato i sei blocchi per il punto 0, la simmetria
residua è il gruppo che permuta i sei gruppi {1,2,3,4}, …, {21,22,23,24}, i punti
dentro ciascun gruppo, e i due punti liberi 25 e 26. In un pacchetto di 32 blocchi in
forma canonica: i 26 blocchi restanti portano 130 incidenze contro una capienza di
24·5 + 2·6 = 132, quindi con A, B, C = blocchi con 0, 1, 2 punti liberi si ha
5A + 4B + 3C ≤ 120, cioè grado(25) + grado(26) = B + 2C ≥ 10, e con grado ≤ 6
ciascuno **grado(25) ≥ 4**. La coppia {25,26} sta in al più un blocco, quindi almeno
3 blocchi per 25 hanno quattro punti di gruppo, da quattro gruppi distinti.

**Il controllo per calcolo** della parte che usa la simmetria:

| verifica | esito |
|---|---|
| ogni generatore del gruppo residuo preserva l'insieme dei sei blocchi fissati | sì |
| i generatori fissano 0, 25, 26 e permutano 1…24 fra loro (quindi preservano coppie e gradi) | sì |
| i blocchi della forma {25} ∪ un punto da quattro gruppi distinti sono | **3840** |
| l'orbita di {25,1,5,9,13} sotto il gruppo residuo (senza scambiare 25 e 26) contiene | **3840** — tutti |

Il gruppo agisce transitivamente su quei blocchi, quindi uno qualunque si porta su
{25,1,5,9,13} senza toccare il resto della forma canonica. **Non ho trovato
l'errore.**

**Decisione, come da tua indicazione.** Il calcolo il cui eventuale *infattibile*
conterebbe gira **senza** il blocco fissato. E senza nemmeno il vincolo
grado(25)+grado(26) ≥ 10: con la soglia «almeno 26 blocchi» quel vincolo è una
**combinazione lineare** dei vincoli di grado (somma dei vincoli sui punti 1…24,
più 5 volte la soglia), quindi non aggiunge niente alla logica. La versione con il
blocco fissato gira **accanto**, solo come acceleratore: se le due versioni
dessero risposte diverse, sarebbe la prova di un errore.

E gira una terza versione **scritta da zero**: SAT invece di ILP, con i candidati
ricavati per filtro (tutti i 5-sottoinsiemi che non riusano una coppia) invece che
per costruzione, contatori scritti a mano, e un verificatore nuovo. Condivide con le
altre soltanto l'argomento della forma canonica per il punto 0 — che è dimostrato
qui sopra e **validato su un pacchetto reale**: il nostro da 31 blocchi, rinominato,
cade esattamente nella forma canonica e usa solo blocchi candidati.

**Primo controllo incrociato, già passato.** Il programma SAT ricava i candidati per
filtro (tutti i 5-sottoinsiemi di {1,…,26} che non riusano una coppia dei sei
blocchi fissati) e ne trova **15.104**: esattamente quanti ne costruisce
`pacchetto.py` per prodotto cartesiano. Due strade diverse, stesso insieme.
Il modello SAT ha 945.402 variabili e 2.071.211 clausole; il solutore è CaDiCaL.

**Qualunque esito, niente annunci:** docs/04 per intero, confronto fra le
formulazioni, e tutto mostrato prima di qualunque passo.

---

## 4. Le probabilità, dette prima

*Scritto alle 14:37 del 12 settembre 2026, a metà delle corse di quattro ore. Tutti i
numeri che seguono sono **stime mie**, non misure: le misure su cui si appoggiano sono
nella sezione 5.*

**Quanto è plausibile che un caso aperto dal 1998 ceda al nostro Mac in qualche ora?
Poco: stimo attorno al 5%** che una delle tre formulazioni in corso concluda entro le
17:10.

Le ragioni, in ordine di peso:

1. **Qualcuno di competente ci ha già provato con il calcolatore.** Il limite 31 è di
   Aw, Chee e Ling (2003), e Ling aveva appena pubblicato proprio sui packing con
   blocchi di 5 e λ = 1. Non è un caso che nessuno ha guardato: è un caso in cui una
   ricerca mirata di specialisti si è fermata a 31. È vero che le «possibili eccezioni»
   piccole restano spesso aperte perché nessuno lancia una ricerca esaustiva, non
   perché le ricerche falliscono — ma qui una ricerca c'è stata.
2. **I nostri strumenti non danno segni di convergenza** (sezione 5): il limite duale
   fermo a 32 per un'ora e mezza, nessuna soluzione da 32, e la via del grafo residuo
   che costa più di un mese di calcolo.
3. **Una risposta «31» varrebbe poco senza un certificato.** Un «non esiste» ottenuto
   da un solutore non è credibile per nessun matematico se non viene con una prova
   verificabile in modo indipendente (per un solutore SAT, un file DRAT controllato da
   un verificatore formale), più i lemmi della forma canonica scritti per esteso.
   Un «32» invece si verifica in un secondo: basta la lista dei blocchi. **Le due
   risposte hanno costi di verifica molto diversi**, e quella più probabile è la più
   costosa.

**Quale delle due risposte è più probabile? Stimo 65% per 31, 35% per 32.** Per 32
parla il fatto che nella stessa classe (v ≡ 7 mod 20) il limite è raggiunto quasi
sempre. Per 31 parlano tre cose: le eccezioni certe della stessa classe sono proprio
i valori piccoli (11 e 15); sia la ricerca del 2003 sia la nostra trovano 31 senza
fatica e mai 32; e il metodo di Kramer–Mesner dimostra che un eventuale pacchetto da
32 **non** è invariante sotto nessuno dei nostri gruppi di ordine ≥ 9, cioè che la via
costruttiva facile non esiste. È un'evidenza debole in entrambi i sensi.

**Stimo 10–20%** che con un metodo migliore (sezione 5) e **qualche notte** di Mac si
arrivi a una risposta, e meno ancora a una risposta **certificata**.

### In quale caso ha senso insistere

Solo se valgono **tutte e tre** le condizioni:

1. **il Handbook conferma che il caso è aperto** — altrimenti ci si ferma comunque;
2. **un metodo più forte mostra prima un segnale misurabile su scala piccola**. Per
   esempio: decide in pochi secondi l'una le forme del grafo residuo del campione,
   oppure chiude per intero il caso B (685 forme) in un tempo ragionevole. Senza un
   segnale del genere, allungare i tempi è solo sperare;
3. **un tetto di calcolo fissato prima**: tre notti di Mac, poi ci si ferma e si
   scrive cosa si è imparato.

Se una sola manca, **conviene cambiare cella**. La scelta migliore è una cella dove
la domanda è di **esistenza** — trovare un codice più grande — e non di non esistenza,
perché lì un successo si verifica in un secondo e non chiede certificati.

---

## 5. Che cosa hanno mostrato i solutori, e le vie non ancora provate

### Il comportamento misurato (alle 14:37, dopo 1 h 28 min)

| formulazione | che cosa si vede | che cosa vuol dire |
|---|---|---|
| **ILP minimo** (HiGHS) | limite duale **fermo a 26 blocchi aggiuntivi, cioè 32 in tutto, dal primo secondo**; nessuna soluzione trovata; la stima dell'albero esplorato torna a 0% dopo un riavvio dalla radice; HiGHS ha rilevato da solo 20 generatori di simmetria | il rilassamento lineare ammette 32 senza fatica. Per dimostrare 31 il solutore deve chiudere quasi tutto l'albero, e la simmetria residua (circa 10¹¹ rinomine) lo moltiplica. **Nessun segno di convergenza** |
| **ILP con blocco fissato** | stesso limite duale fermo a 32; circa 15.000 nodi; stima dell'albero fra il 4% e il 6%, che **sale e scende** | la stima di HiGHS non è affidabile, e non va letta come una barra di avanzamento. Nessuna soluzione da 32 trovata dalle sue euristiche |
| **SAT indipendente** (CaDiCaL) | nessuna risposta; 690 MB di memoria | nessuna informazione intermedia disponibile |

**Un difetto trovato strada facendo, ed è importante.** CaDiCaL, dentro PySAT,
**ignora l'interruzione a tempo**: su un'istanza difficile di prova non si è fermato a
3 secondi (Glucose sì). Il SAT principale avrebbe quindi girato a oltranza, oltre il
limite di quattro ore. Ora lo ferma una **guardia esterna** alle 17:10. Anche la prima
misura dei tempi si era piantata per un'ora per un difetto mio (un `multiprocessing.Pool`
rimasto appeso): rifatta con un processo per forma, ucciso dall'esterno allo scadere.

### La via del grafo residuo, misurata

Le 25.158 forme possibili del grafo delle coppie non coperte (sezione 2 e
`ricerca/residui_d27.py`), ognuna trasformata in una **copertura esatta** di K27 − L
con 32 copie di K5:

| misura | valore |
|---|---|
| forme del campione | 16 (12 del caso A, 4 del caso B) |
| forme decise entro 100 s | **0 su 16** |
| tempo di costruzione del modello | 0,6 s: **gli altri 99 s sono risoluzione** |
| dimensione di un'istanza | circa 31.700 K5 ammessi, 320 coppie da coprire, 950.000 clausole |

**25.158 forme per più di 99 secondi l'una fanno più di 29 giorni**, e questo è solo il
limite inferiore. **Così com'è, questa via non è percorribile.**

### Le vie non provate, con un giudizio su ciascuna

| via | che cosa può dare | giudizio |
|---|---|---|
| **cliquer** (clique massima esatta, di Östergård) | in teoria entrambi i versi | **poco promettente.** Dopo la forma canonica il grafo di compatibilità ha 15.104 vertici e si cerca una clique di 26. Un risolutore di clique generico non sfrutta la struttura di packing, e i suoi limiti per colorazione sono deboli su grafi così densi |
| **CHILS / KaMIS** (insieme indipendente di peso massimo, euristico) | **solo il verso «esiste»**: può trovare un 32, non può dimostrare 31 | **tentativo economico, probabilità bassa.** È lo stato dell'arte e batte la nostra ricerca locale, ma la nostra trova 31 in un minuto e mai 32. Poche ore di calcolo, da compilare in C++ |
| **Kramer–Mesner con gruppi piccoli** (ordine 2, 3, 5, 7) | solo «esiste» | **economico.** Sopra l'ordine 9 non c'è niente oltre 27; un pacchetto da 32, se esiste, avrebbe un gruppo di automorfismi piccolo. Con gruppi di ordine 2 o 3 l'ILP resta grande, ma molto meno di quello completo |
| **forma canonica e grafo residuo insieme** | entrambi i versi | **la più promettente fra quelle economiche.** Le due riduzioni sono compatibili: i due punti liberi 25 e 26 della forma canonica sono **esattamente** i due vicini del punto 0 nel grafo residuo, perché il punto 0 ha grado 2 in L. Si fissa quindi la forma di L, si sceglie come 0 un vertice di grado 2 di L (senza perdita di generalità) e si mettono 25 e 26 sui suoi vicini. I sei blocchi per 0 non sono più fissi: diventano una partizione dei 24 punti restanti in quartine senza lati di L, da enumerare a meno degli automorfismi di L. **Da provare prima di tutto sulle stesse 16 forme**: se il tempo per forma scende a pochi secondi, l'enumerazione completa diventa questione di un giorno |
| **copertura esatta dedicata** (Algorithm X / *dancing links* di Knuth) | entrambi i versi | da provare sulle stesse 16 forme contro SAT. Sulle coperture esatte strette la scelta della coppia con meno blocchi candidati è spesso molto più efficace di un solutore generico |
| **generazione ordinata** con rigetto degli isomorfi (alla McKay) | entrambi i versi, **ed è la via professionale** | la più affidabile per un risultato definitivo, ma giorni di scrittura del codice e di calcolo, e il problema del certificato per «31» resta |

**La mia raccomandazione, per le 17:10 se nessuno avrà concluso:** fermare le tre corse
come deciso, **senza allungarle**; fare **un solo** test economico — forma canonica e
grafo residuo insieme, sulle stesse 16 forme, limite 100 s — e decidere su quel numero.
Se il tempo per forma scende a pochi secondi **e** il Handbook conferma che il caso è
aperto, vale una notte di calcolo. Altrimenti si chiude D(27,5,2), si scrive che cosa
abbiamo imparato, e si passa a una cella di esistenza.

Qualunque esito: **niente annunci**, protocollo di docs/04 per intero, e tutto mostrato
prima di qualunque passo.

---

## 7. Esito delle tre corse (fermate alle 17:10 del 12 settembre 2026)

**Nessuna ha concluso. Nessun limite è stato allungato e nient'altro è stato lanciato.**

| formulazione | come si è fermata | nodi | albero stimato | limite duale | soluzioni trovate |
|---|---|---|---|---|---|
| ILP minimo (senza blocco fissato) | limite di 14.400 s | 35.791 | 2,19% | **26 blocchi extra (= 32), mai mosso** | nessuna |
| ILP con blocco fissato | limite di 14.400 s | 73.142 | 6,98% | **26 (= 32), mai mosso** | nessuna |
| SAT (CaDiCaL), scritto da zero | fermato dalla guardia esterna alle 17:10:21 | — | — | — | nessuna risposta |

Le due formulazioni ILP **concordano**: nessuna delle due ha trovato un pacchetto da 32 né ha escluso che esista. Non c'è quindi nessun esito da passare al protocollo di docs/04.

### Che cosa ha insegnato il comportamento dei solutori

1. **Il rilassamento lineare ammette 32 senza fatica, e la ramificazione non lo scalfisce.** In
   quattro ore il limite duale non è mai sceso sotto 26 blocchi extra. Per dimostrare 31 il
   solutore avrebbe dovuto chiudere quasi tutto l'albero: in queste condizioni è fuori portata.
2. **La stima dell'albero esplorato non è una barra di avanzamento.** È rimasta fra lo 0 e il 7%,
   con riavvii dalla radice, per tutta la corsa: estrapolarla non ha senso.
3. **Nel modello minimo più di metà del tempo è andata nelle euristiche** (8.002 s di sotto-MIP su
   14.400) **senza trovare una soluzione**. È coerente con quello che aveva già mostrato la
   ricerca locale: 31 si trova subito, 32 mai. Resta però solo un indizio verso 31, non una prova.
4. **Fissare il blocco in più raddoppia i nodi esplorati** (73.142 contro 35.791) ma non cambia
   il quadro.
5. **Il SAT non dà informazioni intermedie.** Senza certificati parziali, quattro ore di SAT
   senza risposta non insegnano niente, a parte il costo.

### Che cosa resta sul tavolo, non lanciato

In ordine di rapporto fra costo e informazione, come già scritto nella sezione 5:

1. **forma canonica e grafo residuo insieme**, sulle stesse 16 forme, 100 s ciascuna: se il
   tempo per forma scende a pochi secondi, l'enumerazione completa diventa questione di un
   giorno;
2. **copertura esatta dedicata** (Algorithm X, *dancing links*) sulle stesse forme, contro SAT;
3. **generazione ordinata** con rigetto degli isomorfi: la via professionale, giorni di lavoro.

**Le tre condizioni della sezione 4 per insistere non sono ancora soddisfatte**: il controllo sul
Handbook è in corso, e nessun metodo ha ancora mostrato un segnale su scala piccola. Senza un via
esplicito non si lancia niente.
