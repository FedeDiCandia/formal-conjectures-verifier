# Stato del progetto

*Aggiornato: 10 settembre 2026, fine della sessione autonoma.*

---

## Riepilogo in cinque minuti

**Niente ritrovamenti.** Nessun controesempio, nessun problema aperto risolto.
Le tre ricerche di controesempi e la sonda automatica su una trentina di
enunciati aperti non hanno prodotto nulla, che è l'esito atteso e non un
fallimento: dice fino a dove si è guardato.

**La calibrazione è stata eseguita e questo è il numero che conta: 5 su 7.**
Su undici problemi già dimostrati nell'archivio, entrati tutti *dopo* il taglio
di addestramento del modello e con la dimostrazione nascosta, l'agente ne ha
risolti nove. Ma quattro erano problemi di categoria `test`, cioè controlli di
sanità: sulle sette varianti di congetture vere ne ha risolte cinque. Spesa
totale **$2,98** su un limite di $15.

**Costa molto meno del previsto.** Un successo costa in media **$0,12**, un
fallimento **$0,97** (il fallimento consuma tutto il tetto, il successo si
ferma appena la dimostrazione passa). Un solo colpo, la prima iterazione, costa
**$0,043**: con **$53** si può dare un colpo a *ogni* problema aperto
verificabile dell'archivio.

**La raccomandazione, in una riga:** setaccio a basso costo su tutto
l'archivio, poi affondo solo dove il setaccio mostra un piano sensato. Il conto
completo, con tre scenari e sei livelli di spesa, è in
[docs/06-modello-costi.md](06-modello-costi.md).

**Il difetto più serio l'ho trovato alla fine, e non riguarda l'agente: riguarda
il giudice.** Sul ramo `main` l'archivio dichiara due librerie Lean che
compilano gli stessi file nella stessa cartella di build, con opzioni diverse.
Gli `.olean` si sovrascrivono a vicenda, quindi l'enunciato elaborato di un
problema con `answer(sorry)` cambiava secondo l'ultimo comando eseguito:
`True ↔ P` dopo un build della libreria, `sorry ↔ P` dopo un build del singolo
modulo — che è quello che fa il giudice. Con la seconda semantica nessun
candidato può combaciare, e i 94 problemi aperti che l'indice dava per
attaccabili erano in realtà irraggiungibili. Corretto disattivando la libreria
in eccesso nello snapshot; `bench-v1` non è toccato. Dettagli in
[docs/01](01-archivio-formal-conjectures.md#la-modalita-non-dipende-solo-dallopzione-dipende-da-chi-compila).

**La calibrazione non è contaminata da quel difetto, e l'ho verificato invece
di supporlo.** Dei 17 problemi toccati fra calibrazione e verifiche d'archivio,
uno solo (`Mersenne.new_mersenne_conjecture_of_prime`) ha un `answer( )` nel
sorgente, quindi uno solo era sensibile all'opzione — e non è fra gli undici
della calibrazione. Gli altri hanno enunciati che non cambiano con la modalità.

**Due allarmi falsi trovati e corretti, che valgono più di un ritrovamento.**
La sonda automatica ha segnalato un enunciato aperto come «chiuso da
`plausible`»: non lo era — `plausible`, quando non trova controesempi, lascia un
`sorry` e il file compila comunque con un avviso. E i rapporti della caccia
chiamavano «ritrovamenti» dei valori calcolati. Entrambi corretti, con test.
Sono esattamente gli errori che in un progetto così fanno annunciare un
risultato che non c'è.

---

## Ritrovamenti

*(nessuno)*

| ricerca | fino a dove ha guardato | esito |
|---|---|---|
| un primo `p` con `p²` che divide un numero di Euclide | **tutti** i primi sotto 3 milioni (216 815), e per ognuno tutti i primoriali con fattori minori | nessuno. È l'unica delle tre **conclusiva**: un solo `p` chiuderebbe il problema. Per quei primi il controllo è completo, non parziale |
| orbite di `n → σ(n)−1` che non toccano mai un primo | `n` fino a 200 000, 200 passi ciascuna | nessuna orbita anomala |
| Erdős 396: il minimo `n` per ogni `k` | conclusa: `k` da 0 a 60, `n` fino a 20 000 (1h 45m) | minimo `n` per `k` = 0, 1, 2, 3: **1, 2, 2480, 8178**. Per `k ≥ 4` nessun `n` sotto 20 000. È un **indizio** sulla velocità con cui cresce il testimone, non un controesempio: la forma «per ogni k esiste n» non si confuta con un calcolo |
| sonda automatica: `decide`, `plausible`, `norm_num`, `simp_arith`, forma diritta e negata | 30 enunciati aperti discreti, 240 prove | nessuno cade da solo. Limite superiore misurato al 90% sulla frazione di aperti che cadono da soli: **9,5%** |

I rapporti per problema sono in [docs/dati/caccia/](dati/caccia/).

---

## Stato dei componenti

| componente | stato |
|---|---|
| Ambiente Lean 4.27.0 + archivio `bench-v1` + comparator | ✅ |
| Snapshot post-cutoff: `main` a commit fisso `0a8b856c`, Lean 4.33.1 | ✅ 1268 moduli, indice di 5271 teoremi |
| Verificatore `verify.py` | ✅ 88 test, passati su **tutti e due** gli snapshot |
| Sandbox della compilazione (`sandbox-exec`) + impronta dell'archivio | ✅ con controprova: è la sandbox, non il guard, a fermare la scrittura |
| Strumenti dell'agente (`lean_explore`, `lean_check`, `run_python`) | ✅ |
| Sfide negate (`--confutazione`) | ✅ 107 problemi aperti su `bench-v1`, 94 su `main` |
| Infrastruttura per ricerche lunghe (checkpoint, ripresa, isolamento) | ✅ |
| `avvia.sh` (`stima`, `lancia`, `stato`, `segui`, `ferma`, `riprendi`) | ✅ |
| Calibrazione dell'agente | ✅ **eseguita**, 9 su 11, $2,98 |
| Modello dei costi e proiezione | ✅ [docs/06](06-modello-costi.md) |

---

## Che cosa vorrebbe dire «risolvere un problema aperto», qui

Da mettere in chiaro prima di spendere. La strada che ha una probabilità reale
di riuscita porta a congetture che l'articolo di Epoch AI descrive così, di sé:

> «*The conjectures covered in this work are of uncertain mathematical
> significance, and most have likely received little previous attention.*»
> — [arXiv:2608.11941](https://arxiv.org/abs/2608.11941)

Tradotto: un successo sarebbe **una congettura vera, genuinamente aperta,
dimostrata e verificata dal kernel di Lean — e di importanza matematica
incerta**, del tipo proposto da una persona sola su OEIS e mai più guardato da
nessuno. Non è un risultato che cambia la matematica. È un risultato vero, e
l'obiettivo dichiarato («uno qualsiasi, non mi interessa che sia famoso») è
esattamente questo.

Sui problemi **famosi** il dato è brutale e non è una mia stima: Epoch ha
speso **$1000 per problema** su 59 problemi di Erdős e ne ha risolti **3**.

---

## La conclusione operativa più importante

**Il modo più economico di migliorare i risultati è cambiare modello, non
aumentare il budget.** È misurato sui dati pubblici di Epoch AI, sui 65 problemi
che un tentativo da $50 non aveva risolto:

| chi riprova | quanti ne recupera |
|---|---|
| lo **stesso** modello con **quattro volte** il budget ($200) | **6,2%** |
| lo stesso modello con un agente più elaborato | 6,2% |
| lo stesso modello con 476 000 articoli di arXiv a disposizione | 6,2% |
| un modello **diverso e più recente**, stesso budget alto | **27,7%** e **33,8%** |

Tre modi diversi di spendere di più sullo stesso modello danno esattamente lo
stesso 6,2%. Un modello nuovo rende quattro o cinque volte tanto. E nessuno dei
modelli nuovi ha **perso** un problema che il precedente aveva risolto: i
tentativi si sommano.

**Quindi, se i due giri previsti non danno nulla, la mossa giusta non è
insistere: è fermarsi.** La macchina, il verificatore, l'indice, la sonda e i
1188 bersagli restano dove sono; quando esce il modello successivo si rilancia
lo stesso piano con `--modello <nuovo>` e si spende di nuovo la stessa cifra,
con un'attesa quattro volte più alta di quella che si otterrebbe insistendo
oggi. **Aspettare costa zero e rende più di qualunque altra cosa possiamo
comprare.**

---

## Lavori in corso in questo momento

| lavoro | costo | cosa aspettarsi |
|---|---|---|
| sonda degli artefatti su tutti i 1188 candidati | $0 | ~2 ore. Cerca enunciati che cedono a una tattica banale, cioè formalizzazioni sbagliate |
| ricerca sulla congettura di Murthy fino a n = 10⁹ | $0 | ~2 ore. Un solo n senza k la confuterebbe |

Il tentativo da $50 **non è stato lanciato**: le due cose qui sopra stanno per
dire gratis quale bersaglio scegliere. Dettagli e criteri in
[docs/08-lettura-candidati.md](08-lettura-candidati.md).

---

## Da leggere prima di decidere

[docs/07-strategia.md](07-strategia.md) — analisi delle strade possibili verso
«risolvere un problema aperto», scritta prima di spendere il budget residuo.
Il punto: esiste una misura esterna (Epoch AI, agosto 2026, sugli **stessi**
problemi di questo archivio) che dice che un modello con $50 per problema ne
risolve il 30%. Noi ne spendevamo $0,97. Il presupposto «non esistono problemi
aperti facili» regge per i problemi celebri e cade per le congetture OEIS poco
guardate.

---

## Decisioni prese (11 settembre 2026)

**Il setaccio è annullato.** Presupposto da abbandonare: *non* esistono problemi
aperti facili da trovare con una passata a basso costo. Sono aperti perché
matematici forti non li hanno risolti. Lo scenario ottimistico del modello dei
costi si appoggiava a un limite superiore misurato (0 enunciati su 30 cadono da
soli, tetto al 9,5%), ma un tetto su «quanti cedono a una tattica» non è una
prova che esistano aperti facili: sopra ci stava un'ipotesi, e quell'ipotesi
ignorava che l'archivio è curato per raccogliere problemi difficili.

**Dove va il lavoro, in ordine:**

1. *Lettura della letteratura, gratis.* Per ogni problema aperto esplorabile con
   un programma: fonte originale, fin dove è già stato verificato, se esiste una
   ricerca sistematica pubblicata, quanti casi al secondo servirebbero per
   superare quella frontiera su questo Mac. Si scartano le frontiere fuori
   portata (10¹⁸ e oltre). Stanotte questo lavoro è stato fatto per 3 problemi
   su 30: è il pezzo che manca.
2. *Ricerche solo per i problemi con un vantaggio reale*, con checkpoint e
   ripresa. L'API serve a scrivere i programmi, non a tentare dimostrazioni.
3. *Sonda Lean su tutti e 455 gli enunciati aperti discreti*, non 30, per
   cercare **formalizzazioni sbagliate**. Per ogni sospetto confermato: bozza di
   segnalazione per gli autori dell'archivio, con il confronto fra enunciato
   Lean e fonte originale. Niente viene pubblicato senza approvazione.
4. Solo dopo, una proposta su come usare i ~$195 residui — e su quale parte
   conviene **non** spendere.

**`run_python` avrà `numpy` e `sympy`.** L'isolamento viene da `sandbox-exec`
(niente rete, scrittura solo nella cartella di lavoro) e dall'interprete lanciato
con `-I`, non dalla povertà dell'ambiente. Nel nuovo piano il modello scrive
programmi di ricerca: senza quelle librerie non può nemmeno provarli.

**Frontiere enormi: si scartano, per regola.** Con 84 candidati al secondo
misurati, arrivare a 10¹⁸ richiederebbe dell'ordine di 10¹⁴ anni-core. Erdős 366
(verificato a 10²²), Goldbach e Legendre (4×10¹⁸) restano fuori.

---

## Cosa è stato fatto in questa sessione

1. **Permessi** nel file di progetto (`.claude/settings.json`): 75 comandi
   consentiti, 9 vietati (fra cui `git push`, `gh`, e qualunque accesso a
   `.env`, `~/.ssh`, `~/.aws`). Nessun permesso disattivato in blocco.
2. **Verifica delle dimostrazioni d'archivio**: un problema entra nella
   calibrazione solo se la dimostrazione che l'archivio stesso fornisce,
   estratta e compilata da sola, viene accettata da `verify.py`.
3. **Secondo snapshot** da un commit fisso di `main`, con Lean 4.33.1,
   `lean4export` ricompilato per quella versione, indice e suite di test.
4. **`avvia.sh`**, comando unico per i lavori lunghi, con `caffeinate` e
   conferma prima di spendere.
5. **Ambiente di calcolo** (`numpy`, `sympy`, `numba`) e infrastruttura per
   ricerche che durano tutta la notte e riprendono dopo un'interruzione.
6. **Caccia ai controesempi**: sonda automatica con quattro tattiche Lean su
   forma diritta e negata; tre programmi di ricerca su misura, ciascuno
   validato su valori noti prima di partire, ciascuno con il limite pubblicato
   letto in rete e il punto di partenza scelto **oltre** quel limite.
7. **Protocollo per i ritrovamenti** ([docs/04](04-protocollo-ritrovamenti.md)).
8. **Selezione per la calibrazione** ([docs/05](05-selezione-calibrazione.md)):
   undici problemi post-cutoff, con data, rischio di memorizzazione ed esito
   della verifica della dimostrazione d'archivio.
9. **Calibrazione eseguita** e **modello dei costi**
   ([docs/06](06-modello-costi.md)).

---

## Le quattro cose più importanti da sapere

**Il benchmark è anteriore all'addestramento del modello.** Il tag
`bench-v1-lean4.27.0` è del 6 maggio 2026; il taglio dichiarato di
`claude-opus-5` è maggio 2026. Tutti i candidati di `bench-v1` erano ad alto
rischio di memorizzazione: lo snapshot da `main` non era un miglioramento
opzionale, era la condizione per misurare qualcosa.

**«Risolto nell'archivio» non vuol dire «risolvibile qui».** Su `bench-v1`, di
602 dimostrazioni complete, 109 usano assiomi che il verificatore rifiuta (95
con `decide +native`, 17 che dipendono da `sorryAx` attraverso un lemma). Fra
queste c'erano due dei tre problemi scelti per il primo test dell'agente: quel
test misurava qualcosa che non poteva riuscire.

**Un giudice vale quanto il determinismo della compilazione.** Il difetto delle
due librerie non ha prodotto un risultato sbagliato — il verificatore ha
rifiutato, cioè ha fallito dalla parte giusta — ma ha prodotto rifiuti che non
riguardavano il candidato, e avrebbe fatto sprecare l'intero setaccio sui
problemi con `answer(sorry)`. Si legge in
`.lake/build/ir/<modulo>.setup.json`, che riporta le opzioni con cui ogni
modulo è stato compilato davvero: se un giorno upstream aggiunge un'altra
libreria, quel file è il posto dove guardare.

**Il collo di bottiglia non è l'API, è il verificatore.** Nella calibrazione il
46% del tempo di calendario è stato Lean in locale, non attesa del modello. Una
verifica completa costa 32,9 secondi; con quattro in parallelo sono circa 440
verifiche all'ora. È questo, non il budget, a limitare quante dimostrazioni si
possono controllare in un giorno.

---

## Numeri dell'archivio

| | bench-v1 | main (`0a8b856c`) |
|---|---|---|
| teoremi indicizzati | 2615 | 5271 |
| `research open` | 1029 | 1495 |
| aperti verificabili (enunciato senza buchi) | 911 | 1241 |
| aperti attaccabili per confutazione (`answer(sorry)` proposizionale) | 107 | 94 |
| `research solved` | 836 | 1617 |
| con dimostrazione pulita in archivio | 34 | 58 |
| **risolti ma senza dimostrazione in archivio** | 795 | **1550** |
| file di problemi | 691 | 1268 |
| di cui OEIS | 21 | 227 |

Nessuno dei problemi marcati `research open` ha una dimostrazione completa in
archivio: l'archivio è coerente con se stesso, non ci sono aperti «per
distrazione» da raccogliere.

---

## Le ricerche sono tutte concluse

| lavoro | durata | esito |
|---|---|---|
| numeri di Euclide | 43 min | conclusa, tutto l'intervallo previsto |
| iterazione di σ | 5 s | conclusa |
| Erdős 396 | 1h 45m | conclusa |
| sonda automatica su 30 enunciati | 30 min | conclusa |

Nessuna è stata interrotta, nessuna ha prodotto ritrovamenti. I rapporti per
problema sono in [docs/dati/caccia/](dati/caccia/).

Per rilanciarne una più in là del punto raggiunto, si alza il limite in
`scripts/caccia_programmi.py` (`LIMITE_P`, `FINO_A`, `N_MAX`) e si riparte:

```bash
./avvia.sh lancia caccia
```

Il checkpoint fa riprendere dal punto in cui era, non da capo.

---

## Cosa manca

- Il setaccio vero (tentativo a basso costo su tutti gli aperti): aspetta una
  tua decisione sulla spesa.
- La sonda automatica ha coperto i primi trenta enunciati aperti discreti, non
  tutti e 455.
- `plausible` e `decide` sono le due tattiche più utili della sonda; le altre
  due (`norm_num`, `simp_arith`) non hanno mai prodotto niente e potrebbero
  essere sostituite da `omega` e `bound`.
- Dei trenta problemi scelti per la caccia ne ho strumentati tre. Non è una
  svista: per gli altri non ho controllato in rete fin dove è arrivata la
  letteratura, e senza quel controllo una ricerca rischia di ripercorrere
  terreno già battuto. Il modello dei costi stima in una quindicina i problemi
  con una frontiera davvero raggiungibile.
- L'indice di `main` è stato costruito con la semantica `always_true`, che ora
  è anche quella del giudice: i due sono allineati. Se si rigenera lo snapshot,
  l'indice va ricostruito **dopo** il passo che disattiva la libreria in
  eccesso.
