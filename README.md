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
./.venv/bin/python -m pytest tests/ -v     # circa 5 minuti, 88 test

# gli stessi test sullo snapshot post-cutoff da `main`
env FCS_ARCHIVE=$PWD/external/fc-main \
    FCS_LEAN4EXPORT=$PWD/external/lean4export-433/.lake/build/bin/lean4export \
    FCS_INDEX=$PWD/verifier/problem_index_main.json \
    ./.venv/bin/python -m pytest tests/ -q
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

### Come usarlo per i lavori lunghi

`avvia.sh` è il comando unico per tutto ciò che dura più di qualche minuto.

```bash
./avvia.sh                          # elenco dei lavori disponibili
./avvia.sh stima agente --problemi "NOME" --budget 2
./avvia.sh lancia agente --problemi "NOME" --budget 2
./avvia.sh stato
./avvia.sh segui
./avvia.sh ferma agente
./avvia.sh riprendi caccia
```

| comando | cosa fa |
|---|---|
| `stima` | dice quanto costerebbe e quanto durerebbe. **Non spende e non lancia niente.** |
| `lancia` | avvia in background. Chiede conferma prima di spendere crediti e usa `caffeinate`, così un lavoro di otto ore non si interrompe quando il computer va in sospensione. |
| `stato` | elenco dei lavori, con quelli attivi in cima e le ultime righe di log. |
| `guarda` | **che cosa sta facendo l'agente adesso**: da quanto gira, su quale problema è arrivato, se Lean sta verificando in questo istante, e l'ultimo programma Python che il modello ha scritto da sé. Funziona anche quando il lavoro è stato lanciato senza un log da seguire, perché guarda le tracce sul disco invece dell'output. |
| `segui` | mostra il log mentre scorre. `Ctrl-C` smette di guardare, **il lavoro continua**. |
| `ferma` | interrompe con garbo: le ricerche salvano il checkpoint prima di chiudere. |
| `riprendi` | riparte dall'ultimo checkpoint, non da capo. |

I lavori disponibili sono `agente` (spende crediti), `caccia` (ricerca di
controesempi, non spende), `snapshot` (prepara l'archivio da `main`, non spende)
e `test`.

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
| `tests/` | Test automatici (88) |
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
4. [Protocollo per i ritrovamenti](docs/04-protocollo-ritrovamenti.md) — cosa
   fare se sembra di aver trovato un controesempio, prima di crederci.
5. [Selezione per la calibrazione](docs/05-selezione-calibrazione.md) — come si
   sceglie un problema onesto su cui misurare l'agente.
6. [Modello dei costi](docs/06-modello-costi.md) — quanto costa un tentativo,
   quanti bersagli ci sono, e cosa non si puo' stimare.
7. [Misurazioni](docs/dati/misurazioni.md) — il registro di tutto quello che e'
   stato osservato, con la provenienza di ogni numero.

---

## Versioni bloccate

Il tag di benchmark decide tutto il resto:

| Componente | Versione | Perche' |
|---|---|---|
| formal-conjectures | `bench-v1-lean4.27.0` | l'unico tag di benchmark stabile; i tag sono immutabili, quindi i risultati sono riproducibili |
| Lean | `v4.27.0` | imposto dal tag |
| lean4export | sorgente recente, **compilato con Lean 4.27.0** | deve leggere gli `.olean` dell'archivio, che sono legati alla versione |
| comparator | `2312244` (Lean 4.34.0-rc2) | NON deve corrispondere: invoca `lake` e `lean4export` come processi esterni e lavora solo sul testo esportato |

Accanto a `bench-v1` c'e' un **secondo snapshot**, necessario perche' il tag di
benchmark e' del 6 maggio 2026 e il taglio di addestramento dichiarato di
`claude-opus-5` e' maggio 2026: misurare l'agente su `bench-v1` misura anche
quanto ricorda.

| Componente | Versione |
|---|---|
| formal-conjectures, ramo `main` | commit `0a8b856c` (10 settembre 2026), fisso |
| Lean | `v4.33.1` |
| lean4export | sorgente recente, compilato con Lean 4.33.1 |

Si seleziona con tre variabili d'ambiente: `FCS_ARCHIVE`, `FCS_LEAN4EXPORT`,
`FCS_INDEX` (vedi sopra, nella sezione dei test).

---

## Limiti noti

Elencati per esteso in [docs/02-verificatore.md](docs/02-verificatore.md).
In breve:

- **La sandbox su macOS e' `sandbox-exec`, che Apple dichiara deprecata.**
  Funziona e il collaudo lo dimostra (un candidato che prova a riscrivere un
  `.olean` dell'archivio viene fermato dalla sandbox, non dal guard), ma
  `landrun` — la soluzione prevista da comparator — e' solo per Linux, e qui c'e'
  al suo posto uno shim che non isola: l'isolamento vero e' quello di
  `sandbox-exec`.
- **La correttezza del kernel di Lean e' un assunto**, come per chiunque usi
  Lean.
- **La cache di Mathlib viene da internet.**
- **La fedelta' delle formalizzazioni non e' verificabile**: se un enunciato
  Lean non cattura davvero la congettura in italiano, dimostrarlo non dimostra
  la congettura. L'archivio stesso lo dichiara.
