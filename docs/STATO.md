# Stato del progetto

*Aggiornato: 11 settembre 2026, notte.*

---

## LA SVOLTA DELL'11 SETTEMBRE: si cambia strada

Il piano completo è in [docs/09-piano.md](09-piano.md). In breve, e questo è quello
che conta per capire tutto il resto del documento:

**Non proviamo più a dimostrare teoremi. Proviamo a esibire oggetti.**

La diagnosi che ha portato al cambio: in 139 chiamate su dieci problemi aperti
l'agente ha consegnato al verificatore **due** candidati. Non fallisce nel
dimostrare — **non arriva a provarci**. E la ragione non è il budget (il controllo
di spesa non è mai scattato: tutti si sono fermati da soli al 6–32% del tetto), non
sono le istruzioni, non è il modello. È che **una dimostrazione formale è
indivisibile**: 250 righe che non compilano valgono zero, e un modello competente
che sa di non poter finire sceglie di non iniziare.

La nuova strada è **divisibile**: migliorare un limite inferiore pubblicato in
combinatoria estremale. Ogni passo si misura, la verifica è un programma di venti
righe su aritmetica intera, il calcolo è gratis, i bersagli sono centinaia.

**Va tenuto presente che «risolvere» qui significa un'altra cosa** — un numero che
cambia in una tabella, non una congettura chiusa. La differenza è scritta nella
[sezione 0 del piano](09-piano.md#0-che-cosa-vuol-dire-risolvere-per-la-strada-a),
e va letta prima di chiamare «risultato» qualunque cosa.

### Dove siamo, in numeri misurati

**Fase 1 — riproduzione dei record noti. Superata, in una sessione invece di due
settimane.** Su A(n,d,w), codici binari a peso costante, tabelle di Brouwer:

| prova | esito |
|---|---|
| codici record pubblicati verificati esattamente | **331 su 361** |
| ottimi **noti** raggiunti dal nostro motore partendo da zero | **23 su 26** |
| ottimi noti **non** superati (prova di falsificazione) | **26 su 26** |
| limiti inferiori pubblicati pareggiati, 3000 iterazioni per cella | **78 su 119** |
| limiti superati | **0** |

Delle tre prove la più importante è la terza: **il motore non ha mai rivendicato
più di un valore dimostrato ottimo.** È quella che rende credibili le altre.

**Fase 3 — il primo tentativo di superare un limite. In corso.** 34 celle con
divario aperto (da A(27,8,5), fra 31 e 32, a celle con divari di decine), attaccate
su otto processi. Le prime sei sono finite **sotto il pareggio** — la più vicina,
A(17,6,6), a **una sola violazione** dal limite pubblicato di 113. Serve il lavoro
vero: 30.000 iterazioni sono minuti, non notti.

**Fase D — informale, senza Lean. Ha risposto, e in un modo che non avevo
previsto.** Il dettaglio è nel piano; il fatto misurato è che a effort `high` e
`medium` il modello **esaurisce tutto lo spazio ragionando e non scrive niente**
(32.000 e 24.000 token, $0,81 e $0,61 per zero righe), mentre a effort **`low`**
scrive matematica vera: sul primo problema ha dimostrato che la congettura
**implica un caso del problema del totiente di Lehmer**, che è aperto, più cinque
risultati parziali rigorosi — e ha dichiarato onestamente di non poterla
dimostrare.

Quest'ultima cosa è la spiegazione più pulita del «due candidati su 139 chiamate»
che abbiamo trovato: **l'agente non consegnava niente perché non c'era niente da
consegnare.** Quei problemi sono aperti perché si riducono ad altri problemi
aperti.

### La sonda degli artefatti: 1188 enunciati, zero ritrovamenti — ed è un risultato

La caccia alle **formalizzazioni sbagliate** è finita, con la sonda corretta a
«proporre e non giudicare». Il bilancio:

| | |
|---|---|
| enunciati aperti esaminati | **1188** |
| tentativi di tattica | **22.572** |
| candidati proposti al verificatore | **1** |
| candidati **accettati** | **0** |

L'unico candidato era `Erdos628.erdos_628`, che `aesop` dava per chiuso «senza
dipendere da nessun assioma». Passato a `verify.py`, la risposta è stata
**RIFIUTATO: il file non compila** — il file aveva un errore di notazione
`⟨...⟩`, e la riga di assiomi pulita riguardava una dichiarazione salvata in un
file che non compilava.

**Questo è il sesto falso positivo di questo progetto, e il primo fermato prima di
arrivare in un rapporto.** È esattamente il comportamento chiesto: la sonda
propone, il verificatore giudica, e solo ACCETTATO viene segnalato. Ora è anche un
test di regressione permanente (`tests/test_sonda_artefatti.py`), e la sonda non può
più mostrare un esito positivo senza l'avviso che il file conteneva errori.

**Il risultato va letto per quello che è: su 1188 enunciati aperti dell'archivio di
Google DeepMind, con ventidue tattiche automatiche, nessuna formalizzazione cade a
una tattica banale. Le formalizzazioni reggono.** Era una delle quattro strade che
avevamo considerato — cercare traduzioni sbagliate invece di dimostrazioni — e ora
sappiamo che quella strada è vuota. Non è un fallimento: è una domanda chiusa, e
costa zero non riaprirla.

### Che cosa di questo repository serve ancora

| serve | non serve più per la strada A |
|---|---|
| `ricerca/` (verificatore esatto dei codici, tabelle, orbite, due motori) | il verificatore Lean + comparator, la sandbox, l'impronta dell'archivio |
| l'infrastruttura delle ricerche lunghe con checkpoint | l'indice dei 5271 teoremi, la selezione dei 54, le sfide negate |
| `agent/costi.py` e il registro riga per riga | la sonda degli artefatti |
| **il protocollo dei ritrovamenti e i test dei falsi positivi** | la scala, i giri, i tetti |

I pezzi della colonna destra restano compilati e funzionanti: sono in archivio, non
buttati. Tornano utili se si riprende una strada che passa per Lean.

---

## Come riprendere fra qualche mese

*Scritto per il te futuro, o per chi trova questo repository senza conoscere la
storia. Tutto quello che serve è già installato: non c'è niente da ricostruire.*

### Che cosa è pronto

| | |
|---|---|
| verificatore (`verify.py` + comparator) | funzionante, **123 test** |
| archivio `bench-v1` (Lean 4.27) e snapshot `main` a commit fisso (Lean 4.33.1) | compilati |
| indice dei problemi | 2615 teoremi su bench-v1, 5271 su main |
| bersagli già scelti e ordinati | `docs/dati/lotto.json` |
| esiti di Epoch AI per escludere i problemi già risolti | `external/LeanOpenProblems-results` |
| agente con registro, cartella di lavoro persistente, `numpy`/`sympy` | pronto |

### I quattro controlli da rifare PRIMA di spendere

```bash
cd ~/Documents/Math

# 1. la suite deve passare: se Lean o Mathlib sono cambiati, si accorge qui
./.venv/bin/python -m pytest tests/ -q

# 2. l'archivio è vecchio? lo snapshot attuale è del 10 settembre 2026
git -C external/fc-main log -1 --format='%h %ad'
#    se vuoi uno snapshot nuovo:  bash scripts/setup_snapshot_main.sh
#    ATTENZIONE: quel passo disattiva la libreria a doppio glob. Se lo salti,
#    l'enunciato dei problemi con answer(sorry) cambia sotto i piedi al giudice.

# 3. Epoch AI ha risolto altri problemi? Aggiorna e rifai l'igiene:
git -C external/LeanOpenProblems-results pull
git -C external/LeanOpenProblems pull
./.venv/bin/python scripts/igiene_bersagli.py       # esclude le etichette scadute

# 4. i prezzi del modello nuovo devono stare in agent/costi.py, altrimenti
#    l'agente si RIFIUTA di partire (è voluto: senza prezzi il limite di spesa
#    non si può far rispettare). Si leggono qui:
#    https://platform.claude.com/docs/en/about-claude/pricing
```

### Il comando

```bash
env FCS_ARCHIVE=$PWD/external/fc-main \
    FCS_LEAN4EXPORT=$PWD/external/lean4export-433/.lake/build/bin/lean4export \
    FCS_INDEX=$PWD/verifier/problem_index_main.json \
  ./.venv/bin/python agent/agente.py \
    $(./.venv/bin/python -c "import json;print(' '.join(v['problema'] for v in json.load(open('docs/dati/lotto.json'))[:10]))") \
    --modello IL-MODELLO-NUOVO \
    --istruzioni insistenti \
    --tetto-problema 2.00 \
    --budget 20.00 \
    --effort medium \
    --max-iterazioni 60 \
    --rapporto runs/giro-nuovo.json \
    --registro runs/lavori/giro-nuovo.log
```

Da un altro terminale: `tail -f runs/lavori/giro-nuovo.log`, oppure
`./avvia.sh guarda --segui`.

### Perché questi parametri, e non altri

| parametro | perché |
|---|---|
| `--modello IL-MODELLO-NUOVO` | è **la sola leva che ha reso** nei dati misurati. Quadruplicare il budget sullo stesso modello recupera il 6% dei fallimenti; cambiare modello ne recupera il 28–34% |
| `--tetto-problema 2.00` | un tetto da $2 compra ~19 chiamate a un modello con i prezzi di Opus 5, ~9 con quelli di Fable 5.1. Sotto $0,30 (Opus) o $0,60 (Fable) il tentativo non ha spazio per lavorare |
| `--istruzioni insistenti` | triplicano l'impegno e, soprattutto, rendono **interpretabile** un fallimento: con quelle uno zero significa «non ci riesce», non «non ci ha provato» |
| `--effort medium` | è quello che ha dato 9 su 11 nella calibrazione. `high` costa ~3 volte per iterazione senza un guadagno misurato |
| `--budget 20.00` | il limite è rigido e controllato prima di ogni chiamata. Va messo pari a quello che sei disposto a perdere |
| i bersagli da `lotto.json` | congetture OEIS elementari, mai entrate nel benchmark di Epoch, ordinate per «se esiste un risultato, Lean lo può certificare in poche righe» |

### Come sapere presto se non sta funzionando

Guarda **una** colonna del rapporto: `verifiche`. Sono i candidati consegnati al
verificatore. Se dopo metà del budget è ancora zero su tutti i problemi, il
modello nuovo si comporta come i due vecchi e il giro non darà niente: fermalo.
Nei nostri tre giri quel numero è stato 0, 1 e 1 su 139 chiamate.

---

## Le lezioni misurate, da non riscoprire

**1. Cambiare modello rende più che aumentare il budget.** Sui 65 problemi che un
tentativo da $50 non aveva risolto: lo stesso modello con quattro volte il budget
ne recupera il **6,2%** (identico con un agente più elaborato, identico con
476 000 articoli di arXiv a disposizione); un modello diverso e più recente ne
recupera il **27,7%** e il **33,8%**. E nessun modello nuovo ha *perso* un
problema che il vecchio aveva risolto: i tentativi si sommano.

**2. Il tetto si misura in chiamate, non in dollari.** A parità di tetto, un
modello con i prezzi di Opus 5 compra il doppio delle chiamate di uno con i
prezzi di Fable 5.1:

| tetto | Opus 5 | Fable 5.1 |
|---|---|---|
| $0,50 | 4 | 2 |
| $1,00 | 9 | 4 |
| $2,00 | 19 | 9 |
| $3,00 | 29 | 14 |

Quindi «quale modello conviene» dipende dal tetto: a $200 per problema vince il
modello migliore, a $2 vince quello che compra più iterazioni.

**3. Un successo costa poco, un fallimento costa il tetto.** Misurato sui dati di
Epoch: il costo mediano di un tentativo **riuscito** è $3,55, e 22 dei 53
successi sono arrivati con meno di $2. Il budget se lo mangiano i fallimenti, che
arrivano sempre al tetto. Ne segue che molti tentativi a tetto basso rendono più
di pochi tentativi profondi — con l'avvertenza del punto 5.

**4. La trappola del «ce ne sono altri?».** Una domanda OEIS del tipo «dopo a(2),
c'è un altro primo?» viene formalizzata come `True ↔ ∃ n, ...`: con la convenzione
`answer(sorry)` dell'archivio **l'enunciato afferma che la risposta è sì**. Ma chi
ha scritto il commento aveva già cercato un po', e la risposta vera è quasi sempre
no. Il verso **certificabile** (esibire il testimone) è quindi quello vuoto, e
l'altro è un'affermazione su infiniti casi che un calcolo non chiude. Verificato
su tre: ricerca esaustiva fino a 10³⁹⁹ per `A113010`, fino a n = 24 per `A108301`,
fino a 300 000 per `A1157` — nessun testimone.

**5. Una confutazione per enumerazione non è certificabile.** Per un enunciato
«per ogni n esiste k < n con P(n,k)», confutarlo su un n specifico vuol dire
dimostrare in Lean che *nessuno* dei n−1 valori di k funziona. Oltre il milione
sono un milione di fatti di compostezza: il kernel non ci arriva. Le confutazioni
certificabili hanno **testimoni piccoli**, e i testimoni piccoli stanno solo dove
la congettura non è stata verificata lontano, oppure dove la formalizzazione si
discosta dalla fonte.

**6. Una tattica banale che chiude un problema aperto è un difetto, non una
scoperta.** `simp`, `decide`, `exact ⟨0, by simp⟩`: se chiudono un enunciato su cui
i matematici si sono fermati, l'enunciato dice meno di quel che sembra. Sta nel
protocollo ([docs/04](04-protocollo-ritrovamenti.md)), con i due casi documentati
nei risultati pubblici di Epoch.

**7. Quattro difetti nostri hanno prodotto o quasi prodotto risultati falsi.**
`plausible` che lascia un `sorry` e fa compilare il file; due esplorazioni
concorrenti che si scambiavano i messaggi di Lean; un lettore di verdetti che
attribuiva gli errori alla riga sbagliata; il contabile che fermava i tentativi
facendo sembrare che il modello si arrendesse. Nessuno di questi faceva fallire
qualcosa in modo visibile: **tutti facevano apparire un esito che non c'era.** È
la ragione per cui ogni verdetto, adesso, si legge dagli assiomi.

---

## Riepilogo in cinque minuti

**Tre giri sui problemi aperti, ventuno tentativi, $11,67 spesi, zero successi —
e adesso sappiamo perché.** Non è il budget, non è il modo in cui l'agente si
arrende, non è il modello.

| giro | modello | istruzioni | tetto | problemi | spesa | chiamate | candidati consegnati | risolti |
|---|---|---|---|---|---|---|---|---|
| 0 | Fable 5.1 | attuali | $2,00 | 10 | $2,30 | 32 | **0** | 0 |
| 0 bis | Fable 5.1 | insistenti | $2,00 | 7 | $5,51 | 57 | **1** | 0 |
| 0 ter | Opus 5 | insistenti + correzione del budget | $1,50 | 4 | $3,86 | 50 | **1** | 0 |

Le due colonne che contano sono le ultime. In 139 chiamate all'API, su dieci
problemi aperti distinti, l'agente ha consegnato al verificatore **due
candidati**. Non ha fallito nel dimostrare: **non ha provato a dimostrare**.
Quello che fa, invece, lo fa bene: calcola, conferma numericamente la congettura,
individua il nocciolo della difficoltà, e si ferma.

Tre spiegazioni sono state provate e scartate, ognuna con una misura:

1. **Non è il controllo di budget.** Nel giro 0 non è scattato nemmeno una volta:
   tutti e dieci i problemi si sono fermati da soli avendo speso il 6–32% del
   tetto. (Il difetto del contabile era vero e l'ho corretto — vedi sotto — ma
   riguardava altre esecuzioni.)
2. **Non è il modo di arrendersi.** Con le istruzioni che togliono l'invito a
   dichiararsi sconfitto, la spesa per problema tripla ($0,23 → $0,69) e i calcoli
   raddoppiano (21 → 39 esecuzioni Python). I candidati consegnati restano uno.
3. **Non è il modello.** Fable 5.1 e Opus 5 si comportano allo stesso modo.

**La conclusione, che regge a tre tentativi di smontarla:** su questi dieci
problemi aperti il modello non vede una strada verso una dimostrazione Lean, e
non ne inventa una spendendo di più. È lo stesso esito della mia analisi
gratuita, che per quattro dei dieci aveva già escluso il testimone piccolo e per
l'identità `A109074` aveva concluso che serve un argomento p-adico con stime
strette.

### Che cosa è stato corretto in questa sessione

- **Il contabile.** Si fermava quando lo spazio per la risposta scendeva sotto
  6000 token: con Fable 5.1 servivano $0,30 di margine per chiamata, e un tetto
  da $0,50 dava **una** chiamata sola (due problemi su undici ne hanno avute
  zero). Ora la soglia è 2000 e il limite resta rigido. **Una conclusione
  precedente va rivista:** nella calibrazione `GraphConjecture65` non ha fallito
  per incapacità, si è fermato per questo difetto al 76% del suo tetto. Va
  contato come esito indeterminato.
- **La contabilità dei rapporti.** Quando il budget totale finiva a metà di un
  problema, quel problema risultava con $0,00 e zero verifiche: il lavoro
  spariva. Un rapporto che sottostima la spesa è un problema di sicurezza, non
  di cosmetica.
- **Il registro.** L'agente ora scrive sempre un registro riga per riga, e
  `./avvia.sh guarda --segui` mostra che cosa sta facendo. Prima un giro da
  un'ora sembrava fermo.
- **La selezione dei bersagli**, con due criteri imparati: la trappola del «ce ne
  sono altri?» (l'archivio afferma «sì» e la risposta vera è quasi sempre «no»,
  quindi il verso certificabile è vuoto) e il bonus alle identità, l'unica forma
  su cui il modello costruisce qualcosa invece di limitarsi a calcolare.

### Spesa, e quanto resta

| | |
|---|---|
| speso in tutto, dalla prima prova | **$20,53** |
| caricato sulla Console | $24,00 |
| **residuo** | **$3,47** |

### La mia raccomandazione

**Fermarsi qui, e non ricaricare per ritentare gli stessi problemi.** Il dato
misurato è che la difficoltà non è dove pensavamo: non ci manca budget, ci manca
una strada. Spendere altri $20 su questa famiglia comprerebbe altre 139 chiamate
di calcolo e, se il triplo dell'impegno ha prodotto un candidato in più, la
previsione ragionevole è un altro zero.

Le due cose che valgono, e costano zero:

1. **Il lavoro gratuito continua a produrre.** La sonda sta passando i 1188
   enunciati in cerca di formalizzazioni sbagliate; le ricerche locali hanno
   stabilito frontiere che nessuno aveva pubblicato (numeri di Euclide oltre
   2,9 milioni di primi, Murthy oltre 350 milioni, A113010 esaustivo fino a
   10³⁹⁹). Sono contributi veri all'archivio, verificabili, e non costano niente.
2. **Aspettare il modello successivo.** È la conclusione operativa più solida di
   tutto il progetto, ed è misurata sui dati di Epoch: quadruplicare il budget
   sullo stesso modello recupera il 6% dei fallimenti, cambiare modello ne
   recupera il 28–34%. Quando esce un modello nuovo si rilancia lo stesso piano
   cambiando una parola, e la macchina, il verificatore, l'indice e i 1188
   bersagli sono già lì.

---

## Domande per Federico

**1. Serve ricaricare il credito? La mia risposta è no, e il dato è sopra.**

Restano **$3,47** dei $24 caricati. Per proseguire la scala (giri 1 e 2)
servirebbero altri $20-30, e la misura di questa sessione dice che comprerebbero
altre 139 chiamate di calcolo con la stessa probabilità di prima. *Ho proceduto
con la scelta prudente: mi sono fermato e non ho speso il residuo.*

Se invece vuoi proseguire, l'ordine giusto è: aspettare un modello nuovo, non
ricaricare adesso.

**2. Il rilancio ha coperto quattro problemi, non dieci, e la ragione è il
credito.** Con $5 disponibili e un tetto usabile di $1,50 per problema (che con
Opus 5 compra ~14 chiamate) quattro è quanto ci stava davvero. Ho scelto
`A109074` (il bersaglio, che nel giro precedente era stato troncato dal contabile
all'82% del tetto), `A105720` (primo nella classifica aggiornata), e i due che il
giro precedente non aveva coperto. Meglio quattro tentativi veri che dieci
affamati, come avevi detto.

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
