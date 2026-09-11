# Fase C — modello dei costi e proiezione sui problemi aperti

Generato da `scripts/modello_costi.py`. Modello **claude-opus-5**, effort **medium**, snapshot `external/fc-main commit 0a8b856c, Lean 4.33.1`.

## 1. Che cosa e' stato misurato

**MISURATO** — 11 problemi tentati, 9 risolti, spesa totale $2.9834. Tutti entrati nell'archivio dopo il taglio di addestramento dichiarato (2026-05), tutti con la dimostrazione d'archivio accettata dal verificatore, tutti con la dimostrazione nascosta all'agente.

| livello | righe di prova | esito | iter. | espl. | verifiche | secondi | costo |
|---|---|---|---|---|---|---|---|
| facile | 1 | **risolto** | 8 | 6 | 1 | 110 | $0.1485 |
| facile | 2 | **risolto** | 1 | 0 | 1 | 26 | $0.0148 |
| facile | 2 | **risolto** | 2 | 1 | 1 | 38 | $0.0497 |
| facile | 3 | **risolto** | 1 | 0 | 1 | 37 | $0.0565 |
| medio | 10 | non risolto | 20 | 18 | 1 | 387 | $0.6886 |
| medio | 10 | **risolto** | 3 | 2 | 1 | 57 | $0.0662 |
| medio | 10 | **risolto** | 3 | 2 | 1 | 64 | $0.1639 |
| difficile | 15 | **risolto** | 6 | 5 | 1 | 182 | $0.2572 |
| difficile | 16 | non risolto | 13 | 12 | 0 | 499 | $1.2486 |
| difficile | 20 | **risolto** | 4 | 1 | 3 | 123 | $0.1524 |
| difficile | 34 | **risolto** | 3 | 2 | 1 | 98 | $0.1370 |

## 2. Il modello, livello per livello

Il tasso di successo e' accompagnato dall'intervallo di Clopper-Pearson al 90%: con quattro o cinque problemi per livello l'intervallo e' larghissimo, e dichiararlo e' l'unico modo onesto di dare il numero.

| livello | n | risolti | tasso | intervallo 90% | costo medio se risolto | costo se fallito |
|---|---|---|---|---|---|---|
| facile | 4 | 4 | 100% | 47% – 100% | $0.0674 | — |
| medio | 3 | 2 | 67% | 14% – 98% | $0.1150 | $0.6886 |
| difficile | 4 | 3 | 75% | 25% – 99% | $0.1822 | $1.2486 |
| **totale** | 11 | 9 | 82% | 53% – 97% | $0.1162 | $0.9686 |

**MISURATO** — le quattro voci di livello `facile` sono problemi di categoria `test`, cioe' controlli di sanita' scritti dagli autori dell'archivio: 4 su 4. Le sette voci `medio` e `difficile` sono varianti di congetture vere e proprie, di categoria `research solved`: 5 su 7. Il numero da ricordare e' **5 su 7**, non 9 su 11.

**MISURATO** — costo medio di un successo $0.1162; costo medio di un fallimento $0.9686. Un fallimento costa 8 volte un successo, perche' il fallimento consuma tutto il tetto per problema mentre il successo si ferma appena la dimostrazione passa.

**MISURATO** — costo della PRIMA iterazione, mediana su 11 problemi: $0.0430. Due dei nove successi sono arrivati proprio alla prima iterazione. Questo e' il prezzo di un colpo solo, e serve alla strategia mista del punto 4.

**MISURATO** — tempo di calendario: 0.45 ore in tutto, di cui 0.21 ore di Lean in locale (46%). Il collo di bottiglia non e' l'API: e' il verificatore.

### Costo per problema risolto

Formula: (costo se risolto x p + costo se fallito x (1-p)) / p, cioe' quanto costa in media arrivare a UN successo ritentando su problemi diversi.

| livello | p | costo per successo | con p al minimo dell'intervallo | al massimo |
|---|---|---|---|---|
| facile | 100% | $0.067 | $1.1 | $0.067 |
| medio | 67% | $0.459 | $4.5 | $0.127 |
| difficile | 75% | $0.598 | $4.0 | $0.198 |

## 3. Quanti bersagli ci sono

| | bench-v1 | main (0a8b856c) |
|---|---|---|
| teoremi indicizzati | 2615 | 5271 |
| `research open` | 1029 | 1495 |
| aperti con enunciato completo (verificabili) | 911 | 1241 |
| aperti con buco `answer( )` non proposizionale | 118 | 254 |
| aperti attaccabili per confutazione | 107 | 94 |
| aperti che sono varianti ausiliarie | 188 | 199 |
| `research solved` | 836 | 1617 |
| risolti con dimostrazione pulita in archivio | 34 | 58 |
| risolti SENZA dimostrazione in archivio | 795 | 1550 |

Tutti **MISURATI** sull'indice costruito da Lean.

Due osservazioni che cambiano la strategia. Primo: **nessuno** dei 1495 problemi marcati `research open` ha una dimostrazione completa in archivio — l'archivio e' coerente con se stesso, non ci sono aperti 'per distrazione' da raccogliere. Secondo: 1550 problemi sono marcati `research solved` ma non hanno alcuna dimostrazione Lean in archivio: la matematica e' nota, la formalizzazione manca. Quella e' una terza classe di bersagli, piu' facile degli aperti e piu' difficile di quelli su cui ho calibrato.

## 4. Proiezione sui problemi aperti

Le probabilita' di successo su un problema **aperto** non sono misurabili: sono le tre ipotesi qui sotto, e ogni riga dichiara su cosa si appoggia. I conti tengono conto del fatto che i bersagli sono in numero **finito**: quando una strategia li ha esauriti, la spesa in piu' non compra niente che questo modello sappia valutare.

### Costo di un tentativo (base del conto)

- **A, affondo completo** su un enunciato aperto: **$0.97** — **MISURATO**, media dei due fallimenti della calibrazione ($0.6886 fermato dalle 20 iterazioni, $1.2486 fermato dal tetto di spesa). Su un aperto il tentativo finisce quasi sempre cosi'.
- **C, colpo solo** (setaccio): **$0.0430** — **MISURATO**, mediana del costo della prima iterazione sugli 11 problemi della calibrazione.
- **B, programma di ricerca** scritto e lanciato: **$0.10** di API per problema — **STIMATO**, dell'ordine del costo misurato dei problemi facili (media $0.0674). Il calcolo locale non costa dollari: costa notti di macchina.

### Strategia A — dimostrazioni Lean dirette su enunciati aperti

Un affondo per problema, scelti a caso tra i 1241 aperti verificabili. Saturazione a **$1 202**.

| spesa | affondi | ottimistico | realistico | pessimistico |
|---|---|---|---|---|
| $50 | 52 | 1.0 | 0.155 | 0.010 |
| $100 | 103 | 2.1 | 0.310 | 0.021 |
| $200 | 206 | 4.1 | 0.619 | 0.041 |
| $500 | 516 | 10 | 1.5 | 0.103 |
| $1000 | 1 032 | 21 | 3.1 | 0.206 |
| $5000 | 1 241 *(saturo)* | 25 | 3.7 | 0.248 |

- **ottimistico: p = 2.00%** — STIMATO. la sonda automatica non ha chiuso nessuno dei 30 enunciati aperti provati (240 prove): il limite superiore misurato al 90% e' 9,5%. Prendo circa un quinto di quel tetto, perche' la sonda prova tattiche mentre l'agente ragiona — quindi puo' fare meglio — ma 9,5% e' il tetto di un campione di 30, non una stima.
- **realistico: p = 0.30%** — STIMATO. un successo ogni ~300 tentativi: la calibrazione misura 5/7 su varianti GIA' dimostrate in archivio (prove di 10-34 righe), ma nessun aperto ha una prova corta nota, per definizione di aperto.
- **pessimistico: p = 0.02%** — STIMATO. un successo ogni 5000: l'archivio e' curato da DeepMind per raccogliere problemi su cui gli esperti si sono fermati.

### Strategia B — ricerca di controesempi con calcolo locale

Qui il limite non e' il denaro: e' il numero di problemi su cui una ricerca ha senso. **MISURATO**: lo script di selezione ne ha trovati 30 adatti al calcolo su tutto l'archivio. Dei quattro di cui ho controllato la letteratura, due hanno una frontiera raggiungibile (numeri di Euclide: nessuna ricerca sistematica pubblicata; congettura di Selfridge: verificata solo fino a k circa 29) e due no (Erdos 366: verificata fino a 10^22; Goldbach e Legendre: fino a 4x10^18). Due su quattro, intervallo di Clopper-Pearson al 90% 10% – 90%: **STIMATO** 50%, quindi circa **15 bersagli veri**.

Costo API per saturare la strategia: 15 x $0.10 = **$1.50**. Tempo di macchina: con 8 ricerche in parallelo, circa 2-4 notti.

| spesa | ricerche | ottimistico | realistico | pessimistico |
|---|---|---|---|---|
| $50 | 15 *(saturo)* | 0.750 | 0.150 | 0.015 |
| $100 | 15 *(saturo)* | 0.750 | 0.150 | 0.015 |
| $200 | 15 *(saturo)* | 0.750 | 0.150 | 0.015 |
| $500 | 15 *(saturo)* | 0.750 | 0.150 | 0.015 |
| $1000 | 15 *(saturo)* | 0.750 | 0.150 | 0.015 |
| $5000 | 15 *(saturo)* | 0.750 | 0.150 | 0.015 |

- **ottimistico: p = 5.00%** per ricerca — STIMATO. una minoranza di congetture ha limiti verificati bassi (per la congettura di Selfridge la letteratura si ferma a k~29): su quelle il calcolo locale arriva davvero oltre il noto.
- **realistico: p = 1.00%** per ricerca — STIMATO. misurato in questo progetto: 0 ritrovamenti su 3 ricerche e ~2 ore-CPU; la ricerca sui numeri di Euclide ha superato 2,5 milioni di primi senza niente.
- **pessimistico: p = 0.10%** per ricerca — STIMATO. i limiti pubblicati sono quasi sempre fuori portata: per il problema di Erdos 366 la verifica arriva a 10^22.

La strategia B e' **satura a meno di due dollari di API**. Tutta la colonna della spesa, da $50 a $5000, non cambia niente: quello che manca non sono i soldi, sono i problemi con una frontiera raggiungibile. E un eventuale ritrovamento, secondo il protocollo della fase 7, e' piu' probabilmente una formalizzazione sbagliata che un risultato nuovo.

### Strategia C — strategia mista: setaccio, poi affondo mirato

Si da' **un colpo solo** ($0.0430) a quanti piu' problemi possibile, fino a coprire tutti i 1241; con quello che resta si comprano affondi da $0.97, partendo dai problemi dove il colpo solo ha mostrato un piano sensato. Il primo 10% degli affondi gode dell'amplificazione (sono i selezionati), il resto vale come A.

| spesa | setacciati | affondi | ottimistico | realistico | pessimistico |
|---|---|---|---|---|---|
| $50 | 1 163 | 0 | 5.1 | 0.767 | 0.051 |
| $100 | 1 241 | 48 | 8.3 | 1.1 | 0.064 |
| $200 | 1 241 | 151 | 13 | 1.6 | 0.085 |
| $500 | 1 241 | 461 | 20 | 2.6 | 0.147 |
| $1000 | 1 241 | 977 | 30 | 4.1 | 0.250 |
| $5000 | 1 241 | 1 241 | 35 | 4.9 | 0.303 |

- il colpo solo cattura la quota **22%** dei successi che l'affondo otterrebbe — **MISURATO**: 2 dei 9 successi della calibrazione sono arrivati alla prima iterazione;
- gli affondi selezionati valgono 3x / 2x / 1x un affondo alla cieca — **STIMATO**: il colpo solo scarta i problemi su cui il modello non ha nemmeno un piano; nella calibrazione entrambi i fallimenti avevano un piano coerente dalla prima iterazione, quindi il segnale esiste ma e' imperfetto.
- **MISURATO** — coprire con un colpo solo tutti i 1241 aperti verificabili costa **$53**.

### Il confronto in una riga

| scenario | dollari per successo, A | dollari per successo, C | vantaggio di C |
|---|---|---|---|
| ottimistico | $48 | $13 | 3.6x |
| realistico | $323 | $111 | 2.9x |
| pessimistico | $4 843 | $2 185 | 2.2x |

Il punto di equilibrio della strategia C — un colpo solo su tutti i 1241 aperti, piu' un affondo sul 10% migliore — costa **$174**. E' la cifra da ricordare: e' il prezzo di una passata completa sull'archivio.

## 5. Il calcolo locale, misurato

La strategia B non si paga in dollari ma in tempo di macchina, quindi il numero che conta e' la velocita'.

| ricerca | che cosa cerca | conclusiva? | candidati esaminati | ritrovamenti |
|---|---|---|---|---|
| `euclide_squarefree` | un primo p con p^2 che divide un numero di Euclide | conclusiva: un solo ritrovamento confuterebbe la congettura | 216815 | **0** |
| `erdos409_sigma` | orbite di n -> sigma(n)-1 che non toccano mai un primo | trova sospetti da esaminare a mano, non confutazioni | 199999 | **0** |
| `erdos396_binomiale` | il minimo n con descFactorial(n,k+1) che divide centralBinom(n) | raccoglie indizi: la forma 'per ogni k esiste n' non e' confutabile da un calcolo | 13 | **0** |

**MISURATO** — la ricerca sui numeri di Euclide ha esaminato 216 038 primi in 2 581 secondi  cioe' **84 candidati al secondo** su un core  ed e' arrivata al primo 2 988 497 senza trovare niente. Con 8 ricerche in parallelo e 8 ore di notte sono circa 2.4 milioni di candidati per ricerca per notte (**STIMATO**: velocita' misurata per il tempo).

**MISURATO** — una verifica Lean completa costa 32,9 s con sandbox e impronta, 25,0 s senza. Con 4 verifiche in parallelo sono circa 440 verifiche all'ora: e' questo, non l'API, il limite di quante prove si possono controllare in un giorno.

**MISURATO** — sonda automatica su 30 enunciati aperti discreti (`decide`, `plausible`, `norm_num`, `simp_arith`, forma diritta e negata, 240 prove in tutto): **0** hanno prodotto qualcosa di notevole. Intervallo di Clopper-Pearson al 90% sulla frazione di aperti che cadono da soli: 0.0% – 9.5%.
  Nessuno. Un caso apparente — `Arxiv.«2107.12475».CollatzLike` — era `plausible` che scriveva "Unable to find a counter-example" e lasciava un `sorry`: il file compilava, ma non dimostrava niente. La regola di verdetto e' stata corretta (`scripts/sonda_lean.py`).

## 6. Che cosa NON si puo' stimare

1. **La probabilita' che un problema aperto sia risolvibile da questo sistema.** E' il numero che decide tutto, ed e' esattamente quello che non ho. Non esiste alcun campione di problemi aperti risolti su cui misurarla: se esistesse, quei problemi non sarebbero aperti. I tre scenari del punto 4 sono ipotesi mie, non misure.

2. **Perche' calibrare su problemi risolti e' ottimistico.** Un problema con la dimostrazione in archivio ha, per costruzione, una dimostrazione corta: le undici che ho usato vanno da 1 a 34 righe. Chi ha scritto l'enunciato sapeva gia' che si chiudeva, e lo ha formalizzato in modo che si chiudesse. Su un aperto non c'e' nessuna garanzia che esista una dimostrazione corta, ne' che l'enunciato sia formulato in una forma aggredibile. Il 71% misurato (5 su 7) e' il tasso su una popolazione che NON contiene nessun problema aperto.

3. **La memorizzazione.** Ho scelto problemi entrati nell'archivio dopo il taglio di addestramento dichiarato, ma il taglio riguarda l'archivio, non la matematica: la quaterna di Fermat e il controesempio di 17 vertici sono in letteratura da decenni. Quanta parte dei 9 successi sia ricostruzione e quanta ricordo, non lo so misurare.

4. **Quanto pesa il limite di iterazioni.** Uno dei due fallimenti si e' fermato per esaurimento delle 20 iterazioni, non per incapacita': con 60 iterazioni forse si chiudeva. Non l'ho provato, quindi non lo conto.

5. **Il valore di un ritrovamento.** Se una ricerca trova un controesempio, il protocollo in `docs/04-protocollo-ritrovamenti.md` prevede tre esiti: formalizzazione errata, risultato gia' noto, candidato nuovo. Con zero ritrovamenti finora non ho alcun dato su come si dividano, e il caso piu' probabile a priori e' il primo.

## 7. Raccomandazione

**La strategia mista (C), e sotto i $174 non c'e' motivo di fare altro.** Tre ragioni, in ordine di peso.

1. *Il setaccio costa quasi niente e copre tutto.* Un colpo solo su un problema costa $0.0430 **MISURATO**. Con **$50** si danno 1163 colpi singoli: piu' dei 1241 aperti verificabili dell'archivio. Cioe' con cinquanta dollari si prova una volta OGNI problema aperto della raccolta, e si scopre dove il modello ha un piano e dove no. Nessuna altra spesa in questo progetto ha un rapporto informazione/prezzo simile.

2. *L'affondo va comprato dopo, non prima.* Un affondo costa $0.97 **MISURATO** e finisce non risolto quasi sempre. Comprarne uno per ognuno dei 1241 aperti costa $1 202 ed e' il modo peggiore di spendere. Setacciare tutti e affondare sui 124 migliori costa $174 e, nello scenario realistico, rende **2.9 volte** i successi per dollaro della strategia A.

3. *Il calcolo locale e' gratis: va saturato sempre.* La caccia ai controesempi non consuma budget API, solo notti di macchina. Va tenuta accesa in parallelo a qualunque strategia, perche' il suo costo marginale in dollari e' zero. Ma va puntata sui pochi problemi dove i limiti pubblicati sono bassi: dove la letteratura e' arrivata a 10^22, nessuna notte di calcolo cambia niente.

**Da quale livello di spesa ha senso tentare gli aperti.**

- **$53** — il setaccio completo: un colpo solo su tutti i 1241 aperti verificabili. Successi attesi 5.4 / 0.813 / 0.054 (ottimistico / realistico / pessimistico). Ha senso comunque, anche aspettandosi zero successi: quello che si compra e' la mappa di dove il modello ha un piano.
- **$174** — setaccio completo piu' affondo sul 10% migliore. Successi attesi 13 / 1.6 / 0.080. E' il punto in cui, se lo scenario realistico e' giusto, un successo diventa probabile piu' che no. Sotto questa cifra non c'e' motivo di fare altro; sopra, si sta scommettendo su un numero che nessuno conosce.
- **$500** — successi attesi 20 / 2.6 / 0.147. Vale la pena solo se il setaccio da $53 ha mostrato bersagli promettenti: speso alla cieca, paga affondi su problemi dove il modello non aveva nemmeno un piano.
- **$1000–$5000** — successi attesi 30 / 4.1 / 0.250 e 35 / 4.9 / 0.303. Oltre la saturazione il conto perde significato: comprerebbe secondi e terzi tentativi sugli stessi problemi, e il modello li tratta come indipendenti dai primi, cosa che non sono. Non lo consiglio senza aver prima letto i dati del setaccio.

Si noti l'ampiezza: a ogni livello di spesa i tre scenari stanno in un intervallo di due ordini di grandezza. **L'incertezza non e' nel conto: e' tutta nel valore di p**, che il punto 6 dichiara non stimabile. Chiunque dia un numero solo, qui, sta indovinando.

**Una raccomandazione sui bersagli, non solo sulla spesa.** I 1550 problemi marcati `research solved` ma privi di dimostrazione in archivio sono una classe intermedia: la matematica e' nota, manca la formalizzazione. Su quelli il tasso di successo misurabile sarebbe VERO (si puo' controllare l'esito), il risultato e' utile all'archivio, e il rischio di spendere per niente e' molto piu' basso. Se l'obiettivo e' 'fare lavoro matematico utile con questo sistema' invece di 'risolvere un problema aperto', quella e' la strada con il miglior rapporto tra costo e risultato — e la calibrazione che ho in mano la descrive meglio di quanto descriva gli aperti.

