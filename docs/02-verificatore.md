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

### 1. Il controllo sintattico preventivo (`guard.py`)

comparator, per giudicare, deve **compilare** il file candidato. E compilare un
file Lean significa eseguire codice arbitrario (`#eval`, macro, elaboratori). Su
Linux comparator isola la compilazione con `landrun`; **su macOS quella sandbox
non esiste** e noi usiamo uno shim che non isola niente.

Il guard e' la difesa in profondita': legge il file *prima* di compilarlo e
rifiuta i costrutti che non servono a una dimostrazione onesta. Vedi il
commento in cima a `verifier/guard.py` per l'elenco completo.

Il guard **non** e' cio' che rende affidabile il verificatore: e' un filtro
testuale, e un filtro testuale si puo' sempre aggirare. Le garanzie vere
restano quelle di comparator. Per questo i test verificano entrambi i livelli
separatamente: che il guard blocchi, **e** che comparator rifiuti lo stesso file
anche col guard disattivato.

### 2. Il trattamento di `answer( )`

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

### 3. Timeout e parallelismo

Ogni verifica gira con un tempo massimo. Alla scadenza viene ucciso **l'intero
albero di processi** (`comparator` lancia `lake`, che lancia `lean`): ammazzare
solo il padre lascerebbe i figli a bruciare CPU.

Il parallelismo e' limitato da una coda di N slot (`FCS_MAX_PARALLEL`). Ogni
verifica occupa uno slot e usa il proprio nome di modulo (`S0`, `S1`, ...), cosi'
due verifiche simultanee non si sovrascrivono i file.

---

## Cosa NON garantisce il verificatore

Onesta' intellettuale, elencata esplicitamente:

1. **Su macOS non c'e' sandbox.** Un file candidato ostile potrebbe eseguire
   codice durante la compilazione. Il guard riduce il rischio ma non lo
   elimina. Su Linux, installando il vero `landrun`, la garanzia si recupera.
2. **La correttezza del kernel di Lean e' un assunto.** comparator puo' usare
   kernel esterni indipendenti (`external_kernels`) per ridurre anche questo;
   noi non lo facciamo ancora.
3. **La cache di Mathlib e' scaricata da internet.** Se quella cache contenesse
   definizioni alterate, tutto il ragionamento cade. E' l'assunto standard di
   chiunque usi `lake exe cache get`.
4. **La fedelta' della formalizzazione non e' verificabile.** Se l'enunciato
   Lean nell'archivio non cattura davvero la congettura in italiano, una
   dimostrazione corretta di quell'enunciato non dimostra la congettura. E'
   un limite dell'archivio, non nostro, e l'archivio lo dichiara apertamente.
