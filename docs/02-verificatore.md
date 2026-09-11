# Come funziona il verificatore

## Il problema da risolvere

Un modello linguistico che scrive dimostrazioni Lean ha molti modi di
*sembrare* aver risolto un problema senza averlo fatto. I piu' comuni:

| Trucco | Che aspetto ha |
|---|---|
| Lasciare un buco | `theorem goldbach : ... := by sorry` |
| Aggiungere un assioma | `axiom miracolo : ...` e poi usarlo |
| Fidarsi del compilatore | `by native_decide` invece del kernel |
| Dimostrare qualcos'altro | un enunciato simile ma piu' debole |
| Cambiare le definizioni | ridefinire `Prime` in modo che tutto diventi vero |
| Spegnere i controlli | `set_option debug.skipKernelTC true` |

Nessuno di questi e' necessariamente in malafede: un modello che "vuole"
compilare con successo tende a scivolarci dentro da solo. Il verificatore deve
prenderli tutti.

---

## La scelta di fondo: usare `comparator`

Non abbiamo riscritto il giudice. Usiamo
[`comparator`](https://github.com/leanprover/comparator), scritto dal Lean FRO
esattamente per questo scopo (validare dimostrazioni Lean prodotte da LLM,
nella competizione AIMO).

Il suo funzionamento, in breve:

1. Compila il modulo **Challenge** (il file originale dell'archivio, intatto).
2. Lo esporta in un formato testuale con `lean4export`. Non legge mai i file
   `.olean` compilati: quelli vengono mappati in memoria e sarebbero un punto
   d'attacco.
3. Ripete compilazione ed esportazione per il modulo **Solution** (il nostro
   candidato).
4. **Confronta gli enunciati** dei teoremi richiesti, e con essi tutte le
   dichiarazioni che l'enunciato usa. Il confronto avviene sull'albero
   sintattico esportato, non sul testo del file.
5. **Controlla gli assiomi** da cui dipende la dimostrazione.
6. **Riesegue tutto nel kernel di Lean**, ricostruendo l'ambiente da zero.

Il punto 6 e' quello decisivo: qualunque trucco fatto a livello di
*elaborazione* (macro, opzioni, tattiche) viene annullato, perche' alla fine il
termine di prova deve passare il controllo del kernel, che e' poche migliaia di
righe di codice e non conosce nessuna di quelle scorciatoie.

Il punto 4 e' quello che risponde a "il tipo del teorema e' identico
all'originale" **e** a "non ridefinisce le definizioni dell'archivio": sono la
stessa domanda vista da due lati. Un enunciato che parla di un `Prime`
ridefinito non e' lo stesso enunciato, anche se il testo e' identico.

### Quanto e' severo il confronto

Piu' del necessario, il che va bene. Provato su un caso semplice:

```lean
-- originale
theorem todo1 : 2 + 2 = 4
-- candidato
theorem todo1 : 2 + 2 = 5 - 1
```

`5 - 1` e' *definizionalmente* uguale a `4` (Lean lo riduce da solo) e una prova
del secondo vale come prova del primo. comparator **rifiuta comunque**: pretende
che l'enunciato coincida come struttura, non solo come significato.

Conseguenza pratica: **il candidato deve riscrivere l'enunciato esattamente
com'e' nell'archivio.** E' una richiesta ragionevole e va comunicata all'agente.

---

## Architettura: Challenge e Solution sono moduli separati

```
Challenge = FormalConjectures/ErdosProblems/10.lean   <- l'archivio, intatto
Solution  = FormalConjectures/_Judge/S0.lean          <- il candidato
```

Il file candidato **non puo' importare il modulo del problema**: dichiarerebbe
un nome gia' esistente e non compilerebbe. Deve quindi ripetere tutto cio' che
serve — inclusi eventuali `def` ausiliari definiti nel file originale. Ed e'
proprio qui che scatta il controllo del punto 4: se il candidato riscrive uno di
quei `def` in modo diverso, comparator se ne accorge.

L'archivio resta invariato: aggiungiamo solo un file nuovo in una sottocartella
dedicata, che viene cancellata a fine verifica.

---

## Cosa aggiungiamo noi

### 1. L'isolamento della compilazione (`sandbox.py`)

comparator, per giudicare, deve **compilare** il file candidato. E compilare un
file Lean significa eseguire codice arbitrario. Su Linux comparator isola la
compilazione con `landrun`; su macOS `landrun` non esiste.

La verifica gira quindi dentro `sandbox-exec`, il meccanismo di isolamento del
kernel di macOS. Deprecato da Apple ma funzionante:

| | |
|---|---|
| rete | **negata** |
| scrittura | **solo** le tre cartelle che una verifica tocca davvero (misurate: i sorgenti del modulo temporaneo e i due rami di `.lake/build` che lo riguardano) e i temporanei |
| lettura | negata su `.ssh`, `.aws`, `.gnupg`, le credenziali Anthropic e il `.env` |

Collaudato con un candidato che usa `#eval` e `IO.FS.writeFile` per riscrivere
un `.olean` dell'archivio. Il codice ostile stesso riporta:

```
sabotaggio impedito: operation not permitted (error code: 1)
```

e il file resta byte per byte identico. Il test include la **controprova**:
senza sandbox la stessa scrittura riesce, altrimenti non avremmo dimostrato che
e' la sandbox a fermarla.

### 2. Il controllo dell'integrita' dell'archivio (`impronta.py`)

Il README di comparator elenca fra i suoi assunti (il numero 2) che non si
debbano aver compilato file potenzialmente ostili, perche' potrebbero aver
alterato i file compilati da cui si legge l'enunciato. Noi facciamo verifiche a
ripetizione nella stessa cartella: quell'assunto va **controllato**, non dato
per buono.

Prima e dopo ogni verifica si prende un'impronta:

- i **5378 file dell'archivio** (786 `.olean` piu' i sorgenti, 126 MB) hashati
  per contenuto, uno per uno, cosi' si puo' dire *quale* file e' cambiato;
- i **111 232 file di Mathlib e delle dipendenze** (6,8 GB, troppi da hashare)
  per metadati: percorso, dimensione, data al nanosecondo.

Costa 0,75 secondi per impronta. Se qualcosa cambia, la verifica restituisce
`ERRORE`, non un esito: un confronto contro un enunciato alterato non
significherebbe niente.

Perche' servono **entrambe** le difese: comparator esporta il Challenge *prima*
di compilare la Solution, quindi un sabotaggio non altera la verifica in corso
ma quelle successive. E l'impronta non si fida del meccanismo di isolamento,
che e' deprecato da Apple e su Linux e' un altro.

### 3. Il controllo sintattico preventivo (`guard.py`)

Legge il file *prima* di compilarlo e rifiuta i costrutti che non servono a una
dimostrazione onesta.

Non e' cio' che rende affidabile il verificatore — e' un filtro testuale, e un
filtro testuale si puo' sempre aggirare. Le garanzie vere restano quelle di
comparator e della sandbox. Per questo i test verificano i livelli
separatamente: che il guard blocchi, **e** che comparator rifiuti lo stesso file
anche col guard disattivato.

Il primo collaudo con l'agente ha rivelato che **19 costrutti passavano**. Ora
l'elenco viene dai sorgenti di Lean 4.27 (`Elab/BuiltinCommand.lean`, gli
`@[builtin_command_elab ...]`) e dal censimento degli attributi di Mathlib che
registrano codice eseguibile:

- comandi: `run_meta`, `#eval!`, `simproc`, `register_simp_attr`,
  `declare_syntax_cat`, `notation3`, `meta`, ...
- attributi: `@[simproc]`, `@[tactic]`, `@[command_elab]`, `@[term_elab]`,
  `@[norm_num]`, `@[positivity]`, `@[delab]`, `@[init]`, ...
- **un controllo strutturale** sui tipi di metaprogrammazione (`MetaM`, `CoreM`,
  `TacticM`, `IO`, `Expr`, `Syntax`...): invece di inseguire i comandi uno per
  uno, rifiuta il file che *parla il linguaggio* della metaprogrammazione. E'
  questo che intercetta anche i costrutti che non abbiamo previsto.

Due bug corretti: `#eval!` sfuggiva perche' il punto esclamativo faceva parte
dei caratteri di identificatore usati nel controllo, e `meta` veniva rimosso
come modificatore *prima* del controllo, rendendo `meta def` invisibile.

Trovato anche `decide +native`, la sintassi nuova di `native_decide`: lascia lo
stesso assioma `Lean.ofReduceBool`. Non e' un caso ipotetico — **87
dimostrazioni dell'archivio la usano**, e il verificatore le rifiuta a ragione.
Conseguenza importante: *un problema "gia' risolto nell'archivio" non e' detto
sia risolvibile sotto le nostre regole*.

Contro i falsi allarmi c'e' un test che applica tutte le regole nuove ai **674
file di problemi veri** dell'archivio: l'unica cosa che scatta e' `+native`, che
e' un vero positivo.

### 4. Il trattamento di `answer( )`

Come spiegato in [01-archivio-formal-conjectures.md](01-archivio-formal-conjectures.md),
l'opzione predefinita `google.answer = always_true` fa diventare `answer(sorry)`
un `True` quando il tipo atteso e' `Prop`. Per le domande si'/no, quindi, il
buco nell'enunciato **non esiste**: `answer(sorry) ↔ P` e' `True ↔ P`, e chi lo
dimostra dimostra `P`. Nessun trattamento speciale necessario.

Restano i problemi in cui la risposta **non** e' una proposizione (un numero, un
insieme). Li' l'enunciato contiene davvero un `sorry`, e il verificatore:

- li riconosce in anticipo (campo `statementHasSorry` dell'indice);
- **non li rifiuta**: restituisce l'esito dedicato `NON_VERIFICABILE`,
  spiegando che il problema chiede di *fornire una risposta*, non solo di
  dimostrare;
- ricorda che, anche riempiendo il buco, **la verifica formale non basta**: una
  risposta tautologica passerebbe pur essendo matematicamente vuota. Lo dicono
  esplicitamente sia il README dell'archivio sia quello di comparator.

Confondere questi due casi sarebbe il modo piu' facile di costruire un sistema
che "risolve" problemi aperti senza risolvere niente.

#### Le sfide negate

Resta un terzo caso, ed e' il piu' interessante. **107 problemi ancora aperti**
sono formalizzati con `answer(sorry)` proposizionale, quindi l'enunciato che Lean
vede e' `True ↔ P`: l'affermazione che la risposta e' **si'**.

Se per uno di quei problemi la risposta giusta fosse **no**, il teorema com'e'
scritto sarebbe falso e indimostrabile. Chi trovasse la confutazione non avrebbe
modo di farla verificare: dovrebbe cambiare l'enunciato in `answer(False) ↔ P`,
e il verificatore lo rifiuterebbe — giustamente, perche' e' un altro enunciato.

`verifier/negazione.py` genera allora una seconda sfida, **fidata**: lo stesso
file dell'archivio con `answer(sorry)` sostituito da `answer(False)` nella sola
dichiarazione del teorema bersaglio. Ogni problema aperto ne ha quindi due:

| modalita' | enunciato | significato |
|---|---|---|
| `stretta` (predefinita) | `True ↔ P` | la risposta e' si' — l'enunciato dell'archivio |
| `confutazione` | `False ↔ P` | la risposta e' no, cioe' `¬P` |

Il punto essenziale e' **chi genera** quel file: lo generiamo noi,
meccanicamente, dal sorgente dell'archivio. Non lo scrive chi propone la
dimostrazione — altrimenti potrebbe metterci dentro qualunque cosa.

Uso:

```bash
./.venv/bin/python verifier/verify.py NOME_TEOREMA file.lean --confutazione
```

Come si collauda tutto questo senza risolvere un problema aperto: comparator
confronta gli **enunciati** prima di controllare gli **assiomi**. Un candidato
con la dimostrazione lasciata a `sorry` viene quindi rifiutato per `sorryAx` se
l'enunciato combacia, e per "statement do not match" se differisce. Il motivo
del rifiuto dice se gli enunciati combaciano, e quattro combinazioni bastano a
dimostrare che le due sfide sono enunciati distinti e che funzionano entrambe.

### 5. Timeout e parallelismo

Ogni verifica gira con un tempo massimo. Alla scadenza viene ucciso **l'intero
albero di processi** (`comparator` lancia `lake`, che lancia `lean`): ammazzare
solo il padre lascerebbe i figli a bruciare CPU.

Il parallelismo e' limitato da una coda di N slot (`FCS_MAX_PARALLEL`). Ogni
verifica occupa uno slot e usa il proprio nome di modulo (`S0`, `S1`, ...), cosi'
due verifiche simultanee non si sovrascrivono i file.

---

## Cosa NON garantisce il verificatore

Onesta' intellettuale, elencata esplicitamente:

1. **L'isolamento su macOS usa `sandbox-exec`, che Apple ha deprecato.** Funziona
   ed e' verificato dai test, ma non e' un meccanismo su cui Apple si impegni.
   Su Linux la strada giusta e' installare il vero `landrun` e puntarci
   `FCS_LANDRUN`. Per questo il controllo dell'impronta esiste comunque: non si
   fida della sandbox.
2. **L'impronta usa i metadati per Mathlib, non il contenuto.** Percorso,
   dimensione e data al nanosecondo: una modifica che conservasse tutti e tre
   sfuggirebbe. Hashare 6,8 GB a ogni verifica non era praticabile. I file
   dell'archivio, che sono quelli da cui si legge l'enunciato, sono invece
   hashati per contenuto.
3. **La correttezza del kernel di Lean e' un assunto.** comparator puo' usare
   kernel esterni indipendenti (`external_kernels`) per ridurre anche questo;
   noi non lo facciamo ancora.
4. **La cache di Mathlib e' scaricata da internet.** Se quella cache contenesse
   definizioni alterate, tutto il ragionamento cade. E' l'assunto standard di
   chiunque usi `lake exe cache get`.
5. **La fedelta' della formalizzazione non e' verificabile.** Se l'enunciato
   Lean nell'archivio non cattura davvero la congettura in italiano, una
   dimostrazione corretta di quell'enunciato non dimostra la congettura. E'
   un limite dell'archivio, non nostro, e l'archivio lo dichiara apertamente.
6. **Il guard e' un filtro testuale, e i filtri testuali si aggirano.** Il
   controllo strutturale sui tipi di metaprogrammazione alza molto l'asticella,
   ma la difesa vera contro l'esecuzione di codice e' la sandbox, e contro le
   scorciatoie logiche e' comparator.
7. **L'enunciato di riferimento dipende da come e' stato compilato
   l'archivio.** Su `main` esistevano due librerie che compilavano gli stessi
   file nella stessa cartella con opzioni diverse: l'enunciato elaborato di un
   problema con `answer(sorry)` cambiava secondo l'ultimo comando di build. Lo
   snapshot ora disattiva la libreria in eccesso, ma il principio resta: **il
   giudice e' affidabile quanto lo e' il determinismo con cui l'archivio
   viene compilato.** Se un giorno upstream ne aggiunge un'altra, va rifatto lo
   stesso controllo — si legge in `.lake/build/ir/<modulo>.setup.json`, che
   riporta le opzioni con cui il modulo e' stato compilato davvero.
8. **Una verifica lanciata insieme ad altri lavori sullo stesso archivio puo'
   fallire per ragioni che non riguardano il candidato.** L'impronta se ne
   accorge e rifiuta — fallisce dalla parte giusta — ma il rifiuto non e'
   informativo. Le verifiche vanno lanciate da sole.
9. **Una confutazione verificata non e' una confutazione accettata.** La
   modalita' `confutazione` garantisce che `¬P` sia dimostrato correttamente,
   non che la formalizzazione di `P` sia fedele alla congettura originale. Un
   risultato del genere va sottoposto a revisione umana prima di crederci.
