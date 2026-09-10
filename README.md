# Formal Conjectures Solver

Sistema sperimentale che usa l'API di Anthropic per tentare di risolvere
problemi matematici formalizzati in Lean 4, presi dall'archivio
[formal-conjectures](https://github.com/google-deepmind/formal-conjectures)
di Google DeepMind.

Il pezzo importante non e' l'agente: e' il **verificatore**. Un modello che
scrive dimostrazioni Lean ha molti modi di sembrare aver risolto un problema
senza averlo fatto, e senza un giudice affidabile qualunque risultato sarebbe
privo di significato.

---

## Installazione

```bash
git clone <questo repository> ~/Documents/Math
cd ~/Documents/Math
bash scripts/setup.sh          # LUNGO: circa un'ora, scarica ~8 GB
./.venv/bin/python verifier/index.py --build
```

Poi, per usare l'agente, crea il file `.env` con la tua chiave
(si ottiene da <https://console.anthropic.com/settings/keys>):

```bash
cp .env.esempio .env
# apri .env e sostituisci la riga con la tua chiave
```

Verifica che tutto funzioni:

```bash
./.venv/bin/python -m pytest tests/ -v     # circa 4 minuti
```

---

## Uso

### Verificare una dimostrazione

```bash
./.venv/bin/python verifier/verify.py NOME_TEOREMA file.lean
./.venv/bin/python verifier/verify.py NOME_TEOREMA file.lean --json
```

Piu' file insieme, al massimo N processi Lean in parallelo:

```bash
./.venv/bin/python verifier/verify.py --batch lavori.jsonl --jobs 4
```

### Esplorare i problemi

```bash
./.venv/bin/python verifier/index.py --stats
```

### Far lavorare l'agente

```bash
./.venv/bin/python agent/agente.py NOME_TEOREMA --budget 2.00
./.venv/bin/python agent/agente.py TEOREMA1 TEOREMA2 --budget 5.00 --effort xhigh
```

Il budget e' un limite **rigido** in dollari, calcolato dai token realmente
fatturati. Quando e' esaurito l'agente si ferma.

---

## Struttura

| Cartella | Contenuto |
|---|---|
| `verifier/` | Il verificatore: `verify.py`, `guard.py`, `index.py`, `config.py` |
| `tests/` | Test automatici (16, tutti passanti) |
| `agent/` | L'agente e i suoi strumenti |
| `docs/` | Spiegazioni dettagliate, in italiano |
| `scripts/` | Installazione e utilita' |
| `external/` | Repository clonati (non versionati) |
| `tools/bin/` | Lo shim di `landrun` per macOS |

---

## Documentazione

1. [Come funziona l'archivio](docs/01-archivio-formal-conjectures.md) —
   gli attributi `category` e `formal_proof`, l'elaboratore `answer( )` e la
   sua sottigliezza piu' importante.
2. [Come funziona il verificatore](docs/02-verificatore.md) — la scelta di
   `comparator`, l'architettura Challenge/Solution, e un elenco esplicito di
   **cio' che il verificatore NON garantisce**.
3. [L'agente](docs/03-agente.md) — i due strumenti, il nascondimento delle
   dimostrazioni, il controllo della spesa.

---

## Versioni bloccate

Il tag di benchmark decide tutto il resto:

| Componente | Versione | Perche' |
|---|---|---|
| formal-conjectures | `bench-v1-lean4.27.0` | l'unico tag di benchmark stabile; i tag sono immutabili, quindi i risultati sono riproducibili |
| Lean | `v4.27.0` | imposto dal tag |
| lean4export | sorgente recente, **compilato con Lean 4.27.0** | deve leggere gli `.olean` dell'archivio, che sono legati alla versione |
| comparator | `2312244` (Lean 4.34.0-rc2) | NON deve corrispondere: invoca `lake` e `lean4export` come processi esterni e lavora solo sul testo esportato |

---

## Limiti noti

Elencati per esteso in [docs/02-verificatore.md](docs/02-verificatore.md).
In breve:

- **Su macOS non c'e' sandbox per la compilazione Lean.** `landrun` e' solo per
  Linux; qui viene sostituito da uno shim che non isola. Il controllo
  sintattico preventivo riduce il rischio ma non lo elimina.
- **La correttezza del kernel di Lean e' un assunto**, come per chiunque usi
  Lean.
- **La cache di Mathlib viene da internet.**
- **La fedelta' delle formalizzazioni non e' verificabile**: se un enunciato
  Lean non cattura davvero la congettura in italiano, dimostrarlo non dimostra
  la congettura. L'archivio stesso lo dichiara.
