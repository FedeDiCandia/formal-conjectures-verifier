# Come funziona l'archivio `formal-conjectures`

Riassunto di `README.md`, `CONTRIBUTING.md` e `AGENTS.md` del tag
`bench-v1-lean4.27.0` (commit `7a41db3d`, 6 maggio 2026).

`CONTRIBUTING.md` non contiene nulla di tecnico: parla solo di accordo di
licenza (CLA), code review e gestione delle etichette su GitHub.

---

## 1. Che cos'e' l'archivio

E' una raccolta di **enunciati** di congetture matematiche scritti in Lean 4
usando Mathlib. Il punto chiave: quasi tutti gli enunciati **non hanno una
dimostrazione**. Al posto della dimostrazione c'e' la parola `sorry`, che in
Lean significa "qui manca la prova, fidati e vai avanti".

Un file tipico e' fatto cosi':

```lean
/-- Ogni intero pari maggiore di 2 e' somma di due primi? -/
@[category research open, AMS 11]
theorem goldbach :
    answer(sorry) ↔ ∀ n : ℕ, 2 < n → Even n → ∃ p q, Prime p ∧ Prime q ∧ n = p + q := by
  sorry
```

Il nostro sistema dovra' sostituire quel `sorry` finale con una dimostrazione
vera. Il verificatore serve a stabilire se la sostituzione e' onesta.

Regola importante dell'archivio: le dimostrazioni lunghe (oltre 25-50 righe)
**non** vengono accettate nell'archivio; si linkano da un repository esterno
tramite l'attributo `formal_proof`. Questo e' un archivio di *problemi*, non di
*soluzioni*.

---

## 2. L'attributo `category` — che tipo di problema e'

E' un'etichetta obbligatoria su ogni teorema. Dice **che genere di enunciato** e'
quello. Non ha alcun effetto logico: e' pura classificazione, ma e' esattamente
cio' che ci serve per scegliere i problemi.

| Etichetta | Significato |
|---|---|
| `@[category research open]` | Problema di ricerca **aperto**: nessuna soluzione accettata dalla comunita' matematica. |
| `@[category research solved]` | Problema di ricerca **risolto**: esiste una dimostrazione informale accettata dagli esperti (non necessariamente formalizzata). |
| `@[category textbook]` | Problema da manuale (liceo, laurea, dottorato). |
| `@[category API]` | Enunciato che costruisce la teoria di base attorno a una nuova definizione. |
| `@[category test]` | Enunciato di controllo, una specie di "test unitario" per verificare che una definizione si comporti come previsto. |

Nota: `research solved` significa "i matematici sanno risolverlo", **non**
"esiste una dimostrazione formale in Lean". Questa distinzione conta molto per
noi: sono i problemi `research solved` e `textbook` quelli su cui ha senso
misurare un agente, perche' la risposta esiste.

Il codice sorgente e' in `FormalConjectures/Util/Attributes/Basic.lean` e
definisce il tipo `Category` con i costruttori `textbook`, `research (open|solved)`,
`test`, `API`.

Esiste anche l'attributo `@[AMS n]` per la materia matematica (11 = teoria dei
numeri, 5 = combinatoria, ecc.), obbligatorio anch'esso.

---

## 3. L'attributo `formal_proof` — dove sta la dimostrazione formale

Registra **l'esistenza e la posizione** di una dimostrazione formale. E'
indipendente da `category`: si puo' usare con qualunque categoria.

Sintassi: `@[formal_proof using <tipo> at "<link>"]` dove `<tipo>` e' uno di:

| Valore | Significato |
|---|---|
| `formal_conjectures` | Dimostrato formalmente **dentro questo archivio**; il link punta al commit che riempie il `sorry`. |
| `lean4` | Dimostrato in Lean 4 **altrove** (Mathlib, o un altro repository). |
| `other_system` | Dimostrato in un **altro sistema formale** (Rocq/Coq, Isabelle, Lean 3, HOL...). |

Esempio:

```lean
@[category research solved, AMS 11, formal_proof using lean4 at "https://github.com/esempio"]
theorem un_problema_risolto : ... := by
  sorry
```

Un `formal_proof` su un problema `research open` fa scattare un avviso del
linter: un problema aperto non dovrebbe avere una dimostrazione.

**Perche' ci interessa:** un teorema con `formal_proof` e' un problema per cui
sappiamo che una dimostrazione formale esiste. Sono i candidati ideali per
collaudare il nostro agente (punto 4 del piano), perche' e' ragionevole
aspettarsi che sia risolvibile.

---

## 4. L'elaboratore `answer( )` — il punto piu' delicato

### A cosa serve

Alcune domande matematiche non sono "vero o falso" ma "quanto vale X?".
Esempio: il problema di Hadwiger-Nelson chiede il numero minimo di colori per
colorare il piano. Non si puo' formalizzare senza gia' conoscere la risposta.

`answer( )` e' un segnaposto che marca **il punto dove va la risposta**:

```lean
@[category research open]
theorem HadwigerNelsonProblem :
    UnitDistancePlaneGraph.chromaticNumber = answer(sorry) := by
  sorry
```

Ci sono quindi **due buchi diversi** in un enunciato del genere:
- `answer(sorry)` = "non sappiamo **quale sia la risposta**" (buco nell'enunciato);
- `:= by sorry` = "non sappiamo **dimostrarlo**" (buco nella dimostrazione).

Sono buchi di natura diversa e vanno trattati in modo diverso. Riempire il
secondo e' un lavoro che Lean sa controllare da solo. Riempire il primo
richiede giudizio matematico: come dice il file sorgente, *"e' un lavoro per
matematici umani, non per Lean da solo"*.

### Lo stile consigliato per le domande si'/no

Quando il problema in italiano e' una domanda ("Vale P?"), la convenzione e':

```lean
/-- Vale P? -/
theorem miaCongettura : answer(sorry) ↔ P := by
  sorry
```

Cosi' l'italiano "Vale...?" corrisponde all'`answer(sorry)`. Se il problema
viene risolto, `answer(sorry)` diventa `answer(True)` o `answer(False)`.

### Come funziona davvero (dal sorgente `FormalConjectures/Util/Answer.lean`)

Questo e' il dettaglio tecnico che conta di piu' per il verificatore.
`answer( )` ha **tre modalita'**, controllate dall'opzione `google.answer`:

| Modalita' | Comportamento |
|---|---|
| `always_true` (**predefinita**) | Se l'argomento e' `sorry` e il tipo atteso e' una proposizione (`Prop`), `answer(sorry)` diventa **`True`**. |
| `postpone` | Rinvia l'elaborazione del termine; il `sorry` resta un `sorry`. |
| `with_auxiliary` | Crea una **definizione ausiliaria** a parte, di nome `<nomeTeorema>._answer`, con quel valore. |

La conseguenza della modalita' predefinita e' sorprendente e molto utile:

> `answer(sorry) ↔ P` viene elaborato come `True ↔ P`.

E `True ↔ P` e' logicamente equivalente a `P`. Quindi **per i problemi si'/no la
modalita' predefinita elimina completamente il buco dell'enunciato**: chi
dimostra il teorema sta davvero dimostrando `P`, senza scappatoie. Perfetto per
il nostro verificatore.

Il problema resta per le risposte che **non** sono proposizioni (numeri,
insiemi...): li' `answer(sorry)` resta un vero `sorry` **dentro l'enunciato**.
Un enunciato che contiene `sorry` non e' dimostrabile onestamente (qualunque
prova dipenderebbe dall'assioma `sorryAx`). Il verificatore deve accorgersene e
dirlo chiaramente, invece di far finta di niente.

### La modalita' non dipende solo dall'opzione: dipende da chi compila

*Questo vale sul ramo `main`, non sul tag `bench-v1`.*

Il `lakefile.toml` di `main` dichiara **due librerie che compilano gli stessi
file nella stessa cartella di build**:

| libreria | glob | `google.answer` |
|---|---|---|
| `FormalConjectures` | `FormalConjectures.+` | predefinito (`always_true`) |
| `FormalConjecturesAnswerPostpone` | `FormalConjectures.+` | `postpone` |

Gli `.olean` finiscono nello stesso posto, quindi **l'ultimo comando di build
vince**, e l'enunciato elaborato di un problema con `answer(sorry)` cambia di
conseguenza:

```
lake build FormalConjectures       ->  True ↔ P       (nessun sorry)
lake build <un singolo modulo>     ->  sorryAx ↔ P    (hasSorry: true)
```

Non e' una supposizione: si legge in
`.lake/build/ir/<modulo>.setup.json`, che riporta le opzioni con cui quel
modulo e' stato compilato davvero.

Per un giudice questo e' inaccettabile: lo stesso candidato viene accettato o
rifiutato secondo come e' stato costruito l'archivio poco prima. Nel nostro
snapshot la seconda libreria e' **disattivata** (`scripts/setup_snapshot_main.sh`
lo rifa' se lo snapshot viene rigenerato), cosi' la semantica e' sempre
`always_true` — quella che rende i problemi si'/no davvero dimostrabili.

### L'avvertimento da tenere a mente

Sia il README dell'archivio sia la documentazione di `comparator` avvisano della
stessa cosa: **fornire un termine dentro `answer( )` e dimostrare l'enunciato
non significa aver risolto il problema.** Se la domanda e' "quali numeri
naturali soddisfano P?", si puo' rispondere `{n | P n}` e dimostrarlo per
riflessivita': formalmente ineccepibile, matematicamente vuoto.

Quindi: per i problemi con un buco `answer( )` **non-proposizionale**, il
verificatore automatico puo' garantire la correttezza formale ma **non** che la
risposta sia matematicamente sensata. Va sempre segnalato all'utente.

---

## 5. Altre regole rilevanti per noi

- I problemi del benchmark sono dichiarati con `theorem` o `lemma`.
- `sorry` e' ammesso in `FormalConjectures/` (sono enunciati senza prova) ma
  **vietato** in `FormalConjecturesForMathlib/`.
- `native_decide` e' scoraggiato ovunque e vietato in
  `FormalConjecturesForMathlib/`. (Per noi e' da rifiutare sempre: si appoggia
  al compilatore, non al kernel — vedi il verificatore.)
- I file dei problemi importano solo `FormalConjectures.Util.ProblemImports`.
- Ogni problema sta nel proprio file; le varianti stanno nello stesso file con
  nomi puntati, es. `main_conjecture.variants.special_case`.
- I tag `bench-v{N}-lean4.{X}.{Y}` sono **immutabili**: le correzioni di
  formalizzazioni sbagliate finiscono in `v{N+1}`, mai dentro un tag esistente.
  Questo e' cio' che rende il benchmark riproducibile.
