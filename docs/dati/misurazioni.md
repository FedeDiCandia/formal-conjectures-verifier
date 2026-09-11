# Misurazioni effettuate

Ogni riga dichiara la **provenienza**. Niente numeri stimati in questo file:
solo cose osservate.

## M1 — Prova di connessione all'API
*Provenienza: output a terminale del 2026-09-10, non salvato su file.*

| grandezza | valore |
|---|---|
| modello | claude-opus-5 |
| token input | 16 |
| token output | 16 |
| costo | $0.0005 |

Nota: `max_tokens=16` è stato consumato interamente dal ragionamento (su Opus 5
il ragionamento adattivo è attivo per impostazione predefinita), quindi la
risposta testuale è arrivata vuota. È la prima conferma sperimentale che il
ragionamento consuma lo spazio di `max_tokens`.

## M2 — Rodaggio su un problema banale
*Provenienza: output a terminale del 2026-09-10, non salvato su file.*
*Problema: `JugglerConjecture.jugglerStep_36` (categoria `test`), dimostrazione nascosta.*

| grandezza | valore |
|---|---|
| esito | **RISOLTO** alla prima iterazione |
| iterazioni | 1 |
| verifiche Lean | 1 |
| esecuzioni Python | 0 |
| tempo | 68 s |
| costo | $0.0526 |
| token input | 2 |
| token scritti in cache | 3 090 |
| token letti da cache | 0 |
| token output | 1 333 |
| effort | high |

## M3 — Test da 5 dollari, interrotto
*Provenienza: `runs/test_5_dollari_interrotto.log`, analizzabile con
`scripts/analizza_log_agente.py`. Tutti i numeri sono ricavati dal log.*

Interrotto deliberatamente a $1.81 su $5.00 dopo aver scoperto un difetto in
`lean_check` (scartava i messaggi informativi di Lean) che stava facendo
sprecare il budget in esplorazione.

Vedi l'analisi completa nel testo della Fase A.

## M4 — Costo di una verifica locale (nessuna spesa API)
*Provenienza: esecuzioni di `verify.py` cronometrate con `time`.*

| configurazione | tempo |
|---|---|
| senza sandbox né impronta | 25,0 s |
| con sandbox e impronta | 32,9 s |
| impronta dell'archivio (una) | 0,75 s |

## M5 — Suite di test
*Provenienza: output di pytest.*

| quando | test | tempo |
|---|---|---|
| dopo i 4 interventi | 58 passati | 295,9 s |

## M6 — Calibrazione (Fase B4), 11 problemi post-cutoff
*Provenienza: `docs/dati/calibrazione_completa.json`, costruito da
`docs/dati/calibrazione_run1.txt` e `docs/dati/calibrazione_esito.json`.*

Snapshot `external/fc-main` (commit 0a8b856c, Lean 4.33.1), modello
`claude-opus-5`, effort `medium`, 20 iterazioni al massimo per problema,
dimostrazione d'archivio nascosta e verificata come accettabile prima del
tentativo.

| grandezza | valore |
|---|---|
| problemi tentati | 11 |
| risolti | 9 |
| di cui categoria `test` | 4 su 4 |
| di cui categoria `research solved` | 5 su 7 |
| spesa totale | $2,9834 su un limite di $15 |
| costo medio di un successo | $0,1162 |
| costo medio di un fallimento | $0,9686 |
| costo mediano della prima iterazione | $0,0430 |
| tempo totale | 0,45 ore, di cui 46% Lean in locale |

I due fallimenti: `JacobianConjecture.jacobian_conjecture` ($0,6886, fermato
dalle 20 iterazioni) e `WrittenOnTheWallII.GraphConjecture65.conjecture65`
($1,2486, fermato dal tetto di spesa). In entrambi i casi la strategia
matematica era giusta — un controesempio noto in letteratura — e il blocco
era sull'ingegneria Lean.

## M7 — Sonda automatica sugli enunciati aperti
*Provenienza: `runs/caccia/sonda_lean.json`.*

Quattro tattiche (`decide`, `plausible`, `norm_num`, `simp_arith`) su forma
diritta e negata, timeout 60 s per prova, nessuna spesa API.

| grandezza | valore |
|---|---|
| enunciati aperti provati | vedi il file: la sonda gira ancora |
| che cadono da soli | 0 |

Un caso apparente — `Arxiv.«2107.12475».CollatzLike` — era `plausible` che
non trovava controesempi e lasciava un `sorry`: il file compilava con un
warning e il verdetto lo leggeva come "chiuso". Corretto in
`scripts/sonda_lean.py`, con cinque test in `tests/test_sonda.py`.

## M8 — Velocità del calcolo locale
*Provenienza: `runs/caccia/euclide_squarefree/ricerca.log`.*

| grandezza | valore |
|---|---|
| ricerca sui numeri di Euclide | 86 candidati al secondo su un core |
| primo raggiunto | oltre 2 900 000, nessun ritrovamento |
| verifica Lean completa | 32,9 s con sandbox e impronta; 25,0 s senza |
