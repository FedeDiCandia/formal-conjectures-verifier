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
