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
| Erdős 396: il minimo `n` per ogni `k` | in corso; `k` fino a 60, `n` fino a 20 000 | minimo `n` per `k` = 0, 1, 2, 3: **1, 2, 2480, 8178**. Niente per `k ≥ 4` sotto `n` = 20 000, che è un **indizio**, non un controesempio: la forma «per ogni k esiste n» non si confuta con un calcolo |
| sonda automatica: `decide`, `plausible`, `norm_num`, `simp_arith`, forma diritta e negata | 30 enunciati aperti discreti, 240 prove | nessuno cade da solo. Limite superiore misurato al 90% sulla frazione di aperti che cadono da soli: **9,5%** |

I rapporti per problema sono in [docs/dati/caccia/](dati/caccia/).

---

## Stato dei componenti

| componente | stato |
|---|---|
| Ambiente Lean 4.27.0 + archivio `bench-v1` + comparator | ✅ |
| Snapshot post-cutoff: `main` a commit fisso `0a8b856c`, Lean 4.33.1 | ✅ 1268 moduli, indice di 5271 teoremi |
| Verificatore `verify.py` | ✅ 88 test |
| Sandbox della compilazione (`sandbox-exec`) + impronta dell'archivio | ✅ con controprova: è la sandbox, non il guard, a fermare la scrittura |
| Strumenti dell'agente (`lean_explore`, `lean_check`, `run_python`) | ✅ |
| Sfide negate (`--confutazione`) | ✅ 107 problemi aperti su `bench-v1`, 94 su `main` |
| Infrastruttura per ricerche lunghe (checkpoint, ripresa, isolamento) | ✅ |
| `avvia.sh` (`stima`, `lancia`, `stato`, `segui`, `ferma`, `riprendi`) | ✅ |
| Calibrazione dell'agente | ✅ **eseguita**, 9 su 11, $2,98 |
| Modello dei costi e proiezione | ✅ [docs/06](06-modello-costi.md) |

---

## Domande per Federico

**1. Quanto si spende, e su cosa?**
Il modello dice che con $53 si dà un colpo solo a tutti i 1241 problemi aperti
verificabili, e che il punto di equilibrio della strategia mista (setaccio
completo + affondo sul 10% migliore) costa $174. Sopra quella cifra il conto
diventa una scommessa sul valore di `p`, che nessuno conosce. Dimmi tu il
limite e imposto il setaccio.
*Non ho proceduto: qualunque scelta qui spende soldi.*

**2. Vale la pena puntare sui problemi "risolti ma non formalizzati"?**
Sono **1550** su `main`: la matematica è nota, in archivio manca la
dimostrazione Lean. Su quelli il tasso di successo è *misurabile* (si sa se
l'esito è giusto), il risultato è utile all'archivio, e il rischio di spendere
per niente è molto più basso che sugli aperti. Se l'obiettivo è «fare lavoro
matematico utile» invece di «risolvere un problema aperto», è la strada
migliore. Se l'obiettivo è il secondo, lo dico chiaramente: il modello non
promette niente.

**3. `run_python` deve avere `numpy` e `sympy`?**
Oggi no, per scelta: l'agente riceve un interprete nudo, isolato, senza
pacchetti. L'ambiente di calcolo con `numpy`/`sympy`/`numba` esiste ma lo usano
solo le ricerche lunghe che scrivo io. Dare le librerie all'agente lo
renderebbe più capace sui problemi da controesempio — i due fallimenti della
calibrazione erano proprio di quel tipo — ma allarga la superficie di quello
che può eseguire.
*Ho proceduto con la scelta prudente (nessun pacchetto).*

**4. Le ricerche sui problemi con limiti noti enormi vanno tentate comunque?**
Per Erdős 366 la letteratura è a 10²², per Goldbach e Legendre a 4×10¹⁸: il
calcolo locale non può avvicinarsi. Le ho lasciate fuori dalla coda.
*Ho proceduto escludendole.*

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

## Le tre cose più importanti da sapere

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

## Cosa manca

- Il setaccio vero (tentativo a basso costo su tutti gli aperti): aspetta una
  tua decisione sulla spesa.
- La sonda automatica ha coperto i primi trenta enunciati aperti discreti, non
  tutti e 455.
- `plausible` e `decide` sono le due tattiche più utili della sonda; le altre
  due (`norm_num`, `simp_arith`) non hanno mai prodotto niente e potrebbero
  essere sostituite da `omega` e `bound`.
