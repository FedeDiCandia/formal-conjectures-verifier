# Stato del progetto

*Ultimo aggiornamento: 2026-09-10, sessione autonoma in corso.*

---

## Riepilogo rapido

Il sistema è completo nelle sue tre parti: ambiente Lean, verificatore, agente.
La parte solida è il **verificatore**. L'agente è stato collaudato solo
parzialmente, e la calibrazione vera non è ancora stata eseguita.

| componente | stato |
|---|---|
| Ambiente (Lean 4.27.0, archivio `bench-v1`, comparator) | ✅ funzionante |
| Verificatore (`verify.py`) | ✅ 58 test passanti |
| Sandbox + controllo integrità archivio | ✅ collaudati |
| Strumenti dell'agente (`lean_explore`, `lean_check`, `run_python`) | ✅ |
| Sfide negate (`--confutazione`) | ✅ |
| Calibrazione dell'agente | ⏳ non eseguita |
| Snapshot post-cutoff da `main` | ⏳ in preparazione |

---

## Domande per Federico

*(nessuna al momento)*

---

## Ritrovamenti

*(nessuno al momento)*

---

## Ricerche in corso

*(nessuna al momento)*

