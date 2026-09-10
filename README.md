# Formal Conjectures Solver

Sistema sperimentale che usa l'API di Anthropic per tentare di risolvere
problemi matematici aperti formalizzati in Lean 4, presi dall'archivio
[formal-conjectures](https://github.com/google-deepmind/formal-conjectures)
di Google DeepMind.

## Struttura del progetto

| Cartella | Contenuto |
|---|---|
| `verifier/` | `verify.py`: il verificatore delle dimostrazioni (componente critico) |
| `tests/`    | Test automatici del verificatore |
| `agent/`    | Agente minimo che usa l'API Anthropic |
| `docs/`     | Note e riassunti sull'archivio |
| `scripts/`  | Script di installazione e utilità |
| `external/` | Repository esterni clonati (non versionati) |

## Stato

Fase 1: ambiente + verificatore. Nessun agente autonomo ancora.
