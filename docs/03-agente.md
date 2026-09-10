# L'agente

## Cosa fa

Prende un problema dell'archivio, lo consegna a un modello di Anthropic e lo
lascia lavorare finche' non produce una dimostrazione che il verificatore
accetta, oppure finche' non finiscono tentativi o soldi.

Non e' un sistema sofisticato ed e' voluto: serve a **collaudare il
verificatore in condizioni realistiche**, non a risolvere congetture. Le parti
interessanti sono tre: gli strumenti, il modo in cui il problema viene
consegnato, e il controllo della spesa.

---

## I due strumenti

### `lean_check`

Riceve un file Lean completo e lo passa a `verifier/verify.py`. Restituisce
l'esito e, se il file e' stato rifiutato, i messaggi di errore di Lean.

E' l'unico giudice: il modello non ha modo di "convincere" nessuno, puo' solo
far compilare e verificare il file. Una verifica richiede circa 30 secondi.

### `run_python`

Esegue codice Python in isolamento. Serve perche' cercare una dimostrazione
richiede spesso di fare conti: trovare un controesempio, controllare
un'ipotesi sui casi piccoli, calcolare una costante. Un modello che fa i conti
"a mente" sbaglia, e in Lean uno sbaglio numerico si paga con mezz'ora di
tentativi inutili.

L'isolamento usa `sandbox-exec` di macOS. Verificato sul campo:

| Prova | Risultato |
|---|---|
| calcolo normale | funziona |
| libreria standard (`math`, `itertools`, ...) | funziona |
| connessione di rete | **bloccata** (`URLError`) |
| scrittura fuori dalla cartella di lavoro | **bloccata** (`PermissionError`) |
| lettura della chiave API dall'ambiente | **non presente** |
| ciclo infinito | **ucciso** allo scadere del tempo |

Non ci sono pacchetti esterni (niente `numpy`, niente `sympy`) e ogni
esecuzione riparte da zero: e' un ambiente volutamente povero.

---

## Come viene consegnato il problema

Per collaudare l'agente servono problemi **gia' risolti** — altrimenti non si
saprebbe se un fallimento e' colpa dell'agente o del problema. Ma un problema
gia' risolto ha la risposta scritta nell'archivio.

`agent/nascondi.py` prende il file sorgente e sostituisce **ogni**
dimostrazione con `sorry`, ottenendo esattamente l'aspetto che il file avrebbe
se il problema fosse ancora aperto. Si sostituiscono tutte le dimostrazioni del
file, non solo quella bersaglio: i lemmi vicini sono spesso i passaggi
intermedi della soluzione.

Il taglio non e' testuale: usa le **posizioni esatte delle dichiarazioni**
riportate da Lean nell'indice, e individua il `:=` che separa enunciato e
dimostrazione contando le parentesi (cosi' un `:=` dentro `(n : ℕ := 3)` non
viene scambiato per l'inizio della prova).

Infine `controlla_che_sia_nascosta` verifica che il testo della dimostrazione
originale **non** compaia nel materiale consegnato all'agente. Se trapelasse,
il collaudo non misurerebbe niente e il codice si ferma con un errore.

---

## Il controllo della spesa

Il limite e' **rigido** e calcolato dai campi `usage` che l'API restituisce a
ogni risposta: sono i token effettivamente fatturati, non una stima.

```
costo = (input × prezzo_input
       + cache_scritta × prezzo_input × 1.25
       + cache_letta  × prezzo_input × 0.10
       + output × prezzo_output) / 1_000_000
```

Il saldo viene controllato **prima** di ogni chiamata: quando e' esaurito la
chiamata successiva non parte e l'agente si ferma dicendolo. C'e' anche un
tetto per singolo problema (di default il budget diviso il numero di problemi),
cosi' che un problema ostico non consumi la quota degli altri.

Se il modello richiesto non e' nella tabella dei prezzi, il programma si
rifiuta di partire: meglio fermarsi che far rispettare un limite sbagliato.

---

## Scelte sull'API

Basate sulla documentazione aggiornata, non sulla memoria:

| Scelta | Perche' |
|---|---|
| `thinking: {"type": "adaptive"}` | su Opus 5 il ragionamento e' attivo di default; `budget_tokens` non esiste piu' e darebbe errore 400 |
| `display: "summarized"` | mostra un riassunto del ragionamento mentre lavora. Non costa nulla in piu': il ragionamento viene fatturato uguale in ogni caso |
| `output_config: {"effort": ...}` | regola quanto a fondo ragionare. Default `high`; `xhigh` e `max` costano di piu' |
| `cache_control` sul testo di sistema **e** al livello superiore | le istruzioni sono identiche a ogni chiamata, e la conversazione cresce a ogni giro: senza cache si ripagherebbe tutto lo storico ogni volta |
| streaming con `get_final_message()` | con `max_tokens` alto una richiesta non-streaming rischia di sbattere contro il timeout HTTP |
| ciclo manuale invece del `tool_runner` | serve leggere `usage` a ogni giro per far rispettare il limite di spesa, e poter interrompere a meta' |

Il testo di sistema va tenuto **identico byte per byte** fra una chiamata e
l'altra: la cache funziona per prefisso e un solo carattere diverso la
invaliderebbe, facendo pagare tutto a prezzo pieno.

---

## Cosa aspettarsi

Poco. Questi sono problemi di matematica seria formalizzati in Lean, e un
agente con due strumenti e trenta iterazioni non e' un sistema di ricerca. Il
collaudo serve a rispondere a domande piu' modeste ma necessarie:

- il giro completo funziona da capo a fondo?
- il verificatore da' messaggi d'errore che un modello riesce a usare?
- il limite di spesa viene rispettato davvero?
- l'agente prova a barare? (con `sorry`, con un assioma, indebolendo
  l'enunciato) — e se ci prova, il verificatore lo ferma?

L'ultima domanda e' la piu' interessante delle quattro.
