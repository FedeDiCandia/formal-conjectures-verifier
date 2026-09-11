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
