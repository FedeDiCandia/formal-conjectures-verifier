#!/usr/bin/env python3
"""
Un agent minimum che tenta di dimostrare un problem dell'archive.

COME FUNZIONA
-------------
E' un ciclo semplice:

  1. si manda al model l'statement da dimostrare e le rules;
  2. il model risponde, eventualmente chiedendo di usare one strumento;
  3. si esegue lo strumento e gli si restituisce il result_value;
  4. si ripete finche' il model smette di chiedere tools, oppure finche'
     `lean_check` accetta one_ dimostrazione, oppure finche' finiscono i soldi
     o i attempts.

Gli tools disponibili sono two (vedi agent/tools.py):
  * `lean_check`  — sottopone un file Lean al verifier;
  * `run_python`  — esegue code Python isolated, senza rete, con timeout.

IL LIMIT DI SPESA
------------------
E' un limit RIGIDO, calcolato dai fields `usage` che l'API restituisce a ogni
answer — quindi dai token davvero fatturati, non da one_ estimate. Prima di ogni
call si controlla il saldo: se e' exhausted, l'agent si ferma e lo dice.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
import httpx2   # il trasporto dell'SDK: i suoi errors a meta' answer non diventano APIError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "agent"))

import config as verifier_config          # noqa: E402
from index import ProblemIndex, Problem       # noqa: E402
from costs import Budget, SpendLimitExceeded, Usage   # noqa: E402

#: Spazio maximum concesso a one_ answer. Serve high perche' il reasoning
#: esteso ci rientra inside; il controllo del budget lo riduce se serve.
MAX_TOKENS = 32_000

#: Sotto questa threshold one_ answer non puo' essere utile nemmeno per dire
#: qualcosa di breve: allora, e only_ allora, il attempt si ferma.
#:
#: PERCHE' 2000 E NON 6000. Il controllo del budget riduce `max_tokens` a quanto
#: sta nel residue, e si arrende quando quel number scende below questa threshold.
#: Con 6000 e i prices di Fable 5.1 ($50 per milione in output) servivano $0,30
#: di margine per ogni call, oltre al cost dell'ingresso: un cap da $0,50
#: per problem permetteva UNA call, e two problems su undici ne hanno avute
#: ZERO. Non era il model ad arrendersi, era il nostro contabile. Con 2000 la
#: threshold costa $0,10 e un cap low resta utilizzabile.
#:
#: Il limit resta RIGIDO: nessuna call parte se il suo cost maximum
#: possibile supera il residue. Cambia only_ dove sta il confine fra «riduci la
#: answer» e «stopped».
MIN_USEFUL_TOKENS = 2_000

#: Sotto questa threshold la answer e' cosi' stretta che vale segnalarlo nel
#: log_: serve a capire, leggendo un attempt, se il model ha smesso
#: perche' non aveva piu' idee o perche' non aveva piu' spazio.
TIGHT_TOKENS = 8_000

#: Quante interruzioni di rete di fila si tollerano su un problem before di
#: chiuderlo. Il 12 settembre un «Connection reset by peer» a meta' answer ha
#: fermato un giro intero al terzo problem: l'error veniva da httpx2, che l'SDK
#: non traduce in `anthropic.APIError`, e il `try` del ciclo principale non lo
#: prendeva.
MAX_CONSECUTIVE_NETWORK_ERRORS = 3

#: Le eccezioni che indicano one_ connessione caduta, non one_ answer dell'API.
NETWORK_ERRORS = (anthropic.APIConnectionError, anthropic.APITimeoutError,
                  httpx2.TransportError)


class _WorstCaseUsage:
    """Un `usage` finto che costa esattamente `Budget.max_possible_cost`.

    Serve quando one_ answer non arriva: il suo cost vero non si conosce, ma
    l'API puo' averla fatturata in parte. Addebitare il caso worst tiene
    rigido il limit: la spesa registrata puo' risultare piu' alta di quella
    vera, mai piu' bassa.
    """
    def __init__(self, input_tokens: int, max_tokens: int):
        self.input_tokens = 0
        self.output_tokens = max_tokens
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = input_tokens
        self.cache_creation = None
from hide import file_without_proofs, check_it_is_hidden  # noqa: E402
import tools                              # noqa: E402
import awake                                 # noqa: E402


DEFAULT_MODEL = "claude-opus-5"


def load_env() -> None:
    """Legge il file `.env` del progetto e ne mette le variables nell'environment.

    Serve per la key_ API. Il file e' escluso da git (vedi .gitignore), cosi'
    la key_ non finisce per sbaglio in un commit. Le variables gia' presenti
    nell'environment hanno la precedenza e non vengono sovrascritte.
    """
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key_, _, value_ = line.partition("=")
        key_ = key_.strip()
        value_ = value_.strip().strip('"').strip("'")
        if key_ and key_ not in os.environ:
            os.environ[key_] = value_


# ---------------------------------------------------------------------------
# Il text di system (istruzioni fisse). Va tenuto STABILE fra one_ call e
# l'altra: e' la parte che viene messa in cache, e qualunque byte diverso
# invaliderebbe la cache facendo pagare tutto a prezzo pieno.
# ---------------------------------------------------------------------------

INSTRUCTIONS = """You are working on the `formal-conjectures` benchmark (Google DeepMind), \
proving theorems in Lean 4 with Mathlib.

You will be given one theorem to trials. Your answer is judged by a program, not \
by a person, so the rules below are absolute.

# What you must produce

A single, self-contained Lean 4 file that:

1. Starts with `import {UTILITY_MODULE}` (you may add `import Mathlib...` \
lines if you need something specific).
2. **Does NOT import the module of the problem itself** — that module already \
declares the theorem, and importing it makes the file fail to compile.
3. Re-declares, verbatim, every auxiliary definition the statement depends on \
that lives in the problem's own file (`def`, `abbrev`, `structure`, `instance`, \
notation, `open` commands...). Copy them character for character. If you change \
one, even in a way that looks equivalent, you are proving a different theorem \
and will be rejected.
4. Declares the target theorem with **exactly** the original name (namespace \
included) and **exactly** the original statement, followed by a complete proof.

# How the judge works

The judge is `comparator`, written by the Lean FRO. It compiles your file, \
exports it, and:

- compares the **elaborated syntax tree** of your statement with the original's. \
The comparison is structural, not up to definitional unfolding: stating \
`2 + 2 = 5 - 1` instead of `2 + 2 = 4` is REJECTED even though Lean considers \
them equal. Reproduce the statement exactly as given.
- checks every constant your statement mentions is identical to the archive's.
- checks the axioms your proof depends on. Only `propext`, `Classical.choice` \
and `Quot.sound` are permitted.
- replays the whole proof term through the Lean kernel.

Therefore the following are all automatic rejections, with no partial credit:

- `sorry` or `admit` anywhere in the file (leaves the axiom `sorryAx`);
- a new `axiom` declaration;
- `native_decide` (leaves the axiom `Lean.ofReduceBool` — use `decide` instead, \
which the kernel checks);
- weakening or altering the statement in any way;
- redefining any archive definition differently;
- `set_option debug.skipKernelTC`, `#eval`, `macro`, `elab`, `implemented_by`, \
or any other construct that runs code or disables checks.

Helper lemmas of your own are welcome — declare them before the theorem, with \
fresh names, and trials them properly.

# How to work

You have three tools. Using the right one matters:

**`lean_explore` — to understand.** Compiles a scratch file and returns every \
Lean message, untruncated. Use it to look things up instead of guessing:

    #print Nat.Perfect              -- the actual definition
    #print Selfridge.IsSelfridge    -- a structure's fields and constructor
    #check @Finset.sum_congr        -- the exact type, implicits included
    example : GOAL := by exact?     -- search Mathlib for a closing lemma
    example : GOAL := by apply?     -- same, by application

You may `import` the problem's own module here (you may not in `lean_check`), \
so you can inspect its definitions directly. Errors come back complete, with \
the goal state. About 8-10 seconds. This is not a judgment and costs you \
nothing but time.

**`lean_check` — to submit.** The only judgment that counts. About 30 seconds. \
Use it when you believe you have a proof, not to look something up: it will \
just tell you the theorem is missing.

**`run_python` — to compute.** Searching for a witness or a counterexample, \
checking a hypothesis on small cases, computing a constant. Do not do \
arithmetic in your head when you can compute it. `numpy`, `sympy` and `numba` \
are installed: `sympy.isprime`, `factorint`, `nextprime`, `divisors`, `totient` \
are there, so use them rather than writing your own. **The working directory \
persists between calls**: write a checkpoint file and a later call can resume \
it. Each call has a time limit, so for a long search proceed in blocks, saving \
the position reached — this is how you can search far further than a single \
call allows.

# How much room you have

This is a long attempt, not a quick one: you may use **many dozens of \
iterations**. Every tool result tells you how much of the per-problem budget \
is left and which iteration you are on. Spend the early iterations \
understanding the problem and the definitions, and do not rush a submission. \
If the conversation gets long, older tool results are shortened automatically \
to make room; ask again for anything you still need.

A disproof counts as much as a proof. If the statement is of the form \
`True ↔ P` (the archive asserting the answer is yes), and your computation \
finds a counterexample to `P`, say so clearly and explain what you found: that \
is a result, and it is checked separately.

Practical advice:

- Look it up before you guess. One `lean_explore` with `#check` and `exact?` is \
cheaper than three failed proof attempts, in both time and money.
- Read the error messages carefully; they tell you exactly what failed, and you \
now get them in full.
- If a proof strategy fails twice in a row, change strategy rather than \
patching it.
- You have no internet access. Rely on what you know about Mathlib, and use \
`lean_explore` to correct yourself.
- Stop when `lean_check` reports ACCETTATO. If you become convinced the problem \
is beyond you, say so plainly instead of submitting a proof you know is broken."""


#: La variant «insistente» delle istruzioni.
#:
#: PERCHE' ESISTE. Nel prime_ giro sui problems open_ l'agent ha failed dieci
#: volte su dieci nello stesso way: esplorava, calcolava, concludeva di non
#: farcela e si fermava — spendendo in media $0,23 di un cap da $2 e senza
#: consegnare NEMMENO UNA volta un candidato a `lean_check`. Le istruzioni
#: attuali gliela offrono, quella away d'output: «se ti convinci che il problem
#: e' oltre le tue forze, dillo chiaramente». Chi ha misurato il benchmark OEIS
#: Open aveva invece agenti che arrivavano al cap nel 70% dei cases.
#:
#: Questa variant toglie l'invito ad arrendersi e dice che il budget e' li' per
#: essere consumato. Serve a rispondere a one_ domanda precisa: lo zero su dieci
#: viene dalla difficolta' dei problems o dal way in cui l'agent si arrende?
INSISTENT_INSTRUCTIONS = INSTRUCTIONS.replace(
    """- Stop when `lean_check` reports ACCETTATO. If you become convinced the problem \
is beyond you, say so plainly instead of submitting a proof you know is broken.""",
    """- **Stop only when `lean_check` reports ACCETTATO, or when your budget is \
gone.** The per-problem budget exists to be spent: every tool result tells you \
how much is left.
- **When a route fails, change route — do not stop.** Prove a weaker statement \
first and build on it. Prove a special case (a fixed small parameter, one \
congruence class, one family) and state it as a lemma. Search by computation for \
a counterexample. Look up a different corner of Mathlib. Try the negation.
- **Deciding that a problem is beyond reach is not your call while budget \
remains.** A helper lemma that compiles, or a special case proved, is worth more \
than an early stop — and by the time half the budget is spent you should already \
have sent at least one candidate to `lean_check`, even an imperfect one, because \
its error messages are the most informative thing you can buy.
- Never submit a proof you know is broken, and never claim to have proved \
something you have not. But do not stop while you still have room to try another \
route.""")


def chosen_instructions(variant: str) -> str:
    """Il text di system, second_ la variant chiesta."""
    if variant == "insistenti":
        base = INSISTENT_INSTRUCTIONS
    elif variant == "attuali":
        base = INSTRUCTIONS
    else:
        raise SystemExit(f"variant di istruzioni sconosciuta: {variant!r} "
                         f"(sono 'attuali' e 'insistenti')")
    return base.replace("{UTILITY_MODULE}", verifier_config.utility_module())


def _verification_kind(report: str, accepted_one: bool) -> tuple[str, str]:
    """Ritorna (controllo failed, kind), leggendo il report di verify.py."""
    if accepted_one:
        return "", "accepted_one"
    failed = ""
    for line in report.split("\n"):
        if line.strip().startswith("[FALLITO]"):
            failed = line.split("]", 1)[1].split("—")[0].strip()
            break
    text = report.lower()
    if "non dichiara" in text or "not found in solution" in text:
        return failed, "exploration"
    if "non compila" in text or "compila senza errors" in failed:
        return failed, "errore_tecnico"
    if "assiom" in failed:
        return failed, "buco_o_assioma"
    if "kind_ identico" in failed or "definizioni dell" in failed:
        return failed, "enunciato_sbagliato"
    return failed, "errore_tecnico"


def istruzioni() -> str:
    """Le istruzioni, con il name del module di utility' di QUESTO snapshot.

    Cambia fra le versioni dell'archive: `FormalConjectures.Util.ProblemImports`
    nel tag bench-v1, `FormalConjecturesUtil` nel branch main. Scriverlo fisso
    faceva fallire ogni attempt sul second_ snapshot.
    """
    return INSTRUCTIONS.replace("{UTILITY_MODULE}", verifier_config.utility_module())


def problem_message(problem: Problem, file_text: str) -> str:
    descrizione = (problem.docstring or "").strip()
    return f"""# The problem

**Theorem to trials:** `{problem.theorem}`
**Module it lives in:** `{problem.module}` (do NOT import this)
**Category:** {problem.category}

{"**Informal statement:** " + descrizione if descrizione else ""}

Below is the problem's source file, with every proof replaced by `sorry`.
Everything else — imports, `open` commands, definitions, notation — is exactly
as it appears in the archive. Your file must reproduce whatever the statement
depends on.

```lean
{file_text}
```

Produce a complete Lean file proving `{problem.theorem}`, and check it with
`lean_check`."""


# ---------------------------------------------------------------------------
# Risultato di un attempt
# ---------------------------------------------------------------------------

@dataclass
class LeanCheck:
    """Una singola call a lean_check, con il suo result misurato."""
    chars: int
    result: str                  # ACCETTATO / RIFIUTATO / ERRORE / TIMEOUT
    failed_check: str      # which controllo non e' passato
    seconds: float              # tempo di computation LOCALE (Lean), non dell'API
    #: come classifichiamo il attempt. Regola dichiarata:
    #:   exploration        -> il file non dichiarava il theorem_ richiesto
    #:                          (il model stava ispezionando, non tentando)
    #:   errore_tecnico      -> il file non compila
    #:   buco_o_assioma      -> compila ma la dimostrazione ha un buco
    #:   enunciato_sbagliato -> compila ma dimostra un'altra cosa
    #:   accepted_one           -> passed_one
    kind: str


@dataclass
class Iteration:
    """Una passata del ciclo: one_ call all'API piu' gli tools usati."""
    number: int
    input_tokens: int = 0
    output_tokens: int = 0
    cache_written: int = 0
    cache_read: int = 0
    cost: float = 0.0
    api_seconds: float = 0.0
    lean_seconds: float = 0.0
    python_seconds: float = 0.0
    checks: list = field(default_factory=list)     # list[LeanCheck]
    python_runs: int = 0
    explorations: int = 0
    exploration_seconds: float = 0.0
    reasoning: str = ""


@dataclass
class Attempt:
    problem: str
    solved_one: bool = False
    reason: str = ""
    iterations: int = 0
    checks: int = 0
    explorations: int = 0
    python_runs: int = 0
    seconds: float = 0.0
    usage: Usage = field(default_factory=Usage)
    solution: str = ""
    transcript: list = field(default_factory=list)
    #: misurazioni per iteration
    detail: list = field(default_factory=list)      # list[Iteration]
    api_seconds: float = 0.0
    lean_seconds: float = 0.0
    python_seconds: float = 0.0
    #: how_many_ volte la conversazione e' stata accorciata per far spazio
    compactions: int = 0
    #: calls interrotte dalla rete, addebitate al cost maximum possibile
    network_interruptions: int = 0
    #: la total_sum di quegli addebiti: sta nel budget total, non in `usage`
    network_charge: float = 0.0
    #: classificazione del failure, second_ la rule_ dichiarata below
    cause: str = ""

    @property
    def verifications_by_kind(self) -> dict:
        count_: dict = {}
        for it in self.detail:
            for v in it.checks:
                count_[v.kind] = count_.get(v.kind, 0) + 1
        return count_

    def classify_failure(self) -> str:
        """Distingue un failure MATEMATICO da one di SISTEMA.

        Regola dichiarata, non a sensazione:
          * se non c'e' state nessun attempt vero (all_of le checks erano
            explorations), il failure e' di SISTEMA: l'agent non e' arrivato
            a provarci, ha spent tutto a capire gli tools e l'API di Mathlib;
          * se i attempts real_ones sono finiti only_ con errors di compilazione, e'
            TECNICO: sapeva cosa fare ma non come scriverlo in Lean;
          * se almeno un attempt e' arrivato a compilare e ha failed per un
            buco o per l'statement sbagliato, e' MATEMATICO: la dimostrazione
            non c'era.
        """
        if self.solved_one:
            return "solved_one"
        n = self.verifications_by_kind
        real_ones = n.get("errore_tecnico", 0) + n.get("buco_o_assioma", 0) + \
            n.get("enunciato_sbagliato", 0)
        if real_ones == 0:
            return "system: nessun attempt vero, tutto spent in exploration"
        if n.get("buco_o_assioma", 0) or n.get("enunciato_sbagliato", 0):
            return "matematico: ha compilato ma la dimostrazione non c'era"
        return "tecnico: sapeva cosa dimostrare ma non e' succeeded a scriverlo in Lean"


#: Oltre questa threshold di token in ingresso la conversazione viene compattata.
#: Serve per i attempts lunghi: chi ha misurato il benchmark OEIS Open spendeva
#: $50 per problem, cioe' dell'order di 200 iterations. Senza compattazione la
#: conversazione supera la finestra del model e il attempt muore per
#: esaurimento di context invece che di idee.
COMPACTION_THRESHOLD = 120_000

#: Quanti messages in queue restano intact quando si compatta. Il model deve
#: vedere per intero il suo job recente; quello old_ gli serve come traccia.
MESSAGES_UNTOUCHED = 8

#: A how_many chars si riducono i results degli tools piu' vecchi.
OLD_RESULTS_QUEUE = 600

_CUT_MARK = "\n… [result_value accorciato per far spazio nel context; "\
                "se ti serve di new_one, richiedilo]"


def compact_conversation(messages: list, *, intact: int = MESSAGES_UNTOUCHED,
                           queue: int = OLD_RESULTS_QUEUE) -> int:
    """Accorcia i results degli tools piu' vecchi. Ritorna how_many ne accorcia.

    Il prime_ message (l'statement del problem) e gli last_ones `intact` non si
    toccano mai. Si accorciano only_ i `tool_result`, perche' sono il grosso: un
    error di Lean arriva a 40 000 chars, e in duecento iterations sono
    milioni. Il code che il model ha scritto (i `tool_use`) resta intero: e'
    il suo job, e ricostruirlo costerebbe piu' di quanto occupa.
    """
    if len(messages) <= intact + 1:
        return 0
    cut_ = 0
    for msg in messages[1:len(messages) - intact]:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            text = block.get("content")
            if not isinstance(text, str) or len(text) <= queue:
                continue
            if text.endswith(_CUT_MARK):
                continue
            block["content"] = text[:queue] + _CUT_MARK
            cut_ += 1
    return cut_


# ---------------------------------------------------------------------------
# Il ciclo
# ---------------------------------------------------------------------------

class _Doppio:
    """Scrive su two posti insieme: lo schermo e un file.

    Serve perche' un giro lanciato in sottofondo non mostra niente finche' non
    finisce, e chi guarda non ha way di sapere se sta andando. Con il log_
    su file si puo' fare `tail -f` e vedere le lines arrivare.

    Non usa `print` reindirizzato con `>` perche' quello lo decide chi lancia:
    il log_ deve esserci sempre, also_ quando l'output va in one_ pipe.
    """

    def __init__(self, stream, path: Path):
        self.stream = stream
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(path, "a", encoding="utf-8", buffering=1)  # line per line

    def write(self, text):
        self.stream.write(text)
        self.file.write(text)
        return len(text)

    def flush(self):
        self.stream.flush()
        self.file.flush()

    def isatty(self):
        return getattr(self.stream, "isatty", lambda: False)()



def solve_(problem: Problem, index: ProblemIndex, *, client, model: str,
            budget: Budget, problem_cap: float, max_iterations: int = 30,
            effort: str = "high", lean_timeout: int | None = None,
            verbose: bool = True, instruction_variant: str = "attuali") -> Attempt:

    start_ = time.time()
    t = Attempt(problem=problem.theorem)

    file_text = file_without_proofs(problem, index)
    try:
        # Il shakedown dev'essere onesto: se la dimostrazione non e' stata
        # nascosta, il problem si SALTA. Prima interrompeva tutta l'esecuzione,
        # e one_ calibrazione da undici problems si fermava al terzo.
        check_it_is_hidden(problem, file_text)
    except AssertionError as e:
        t.reason = f"saltato: {e}"
        t.cause = "system: la dimostrazione dell'archive non si riesce a nascondere"
        t.seconds = time.time() - start_
        return t

    api_tools = [tools.SCHEMA_LEAN_EXPLORE, tools.SCHEMA_LEAN_CHECK,
                     tools.SCHEMA_RUN_PYTHON]

    # Una folder di job per problem, che sopravvive alle calls: serve
    # perche' one_ ricerca in piu' steps possa salvare un checkpoint. Il name e'
    # ripulito perche' i names dei theorems contengono points e chars strani.
    clean_name = re.sub(r"[^A-Za-z0-9_.-]", "_", problem.theorem)[:80]
    work_dir = verifier_config.ROOT / "runs" / "job" / clean_name
    work_dir.mkdir(parents=True, exist_ok=True)
    messages = [{"role": "user", "content": problem_message(problem, file_text)}]

    spent_at_start = budget.spent
    consecutive_network_errors = 0
    #: gli addebiti prudenziali delle calls interrotte: contano sul budget
    #: total, non sul cap di questo problem
    network_charges_here = 0.0

    def show(*a):
        if verbose:
            print(*a, flush=True)

    for iteration in range(1, max_iterations + 1):
        t.iterations = iteration

        # --- il controllo del portafoglio, PRIMA di spendere -------------
        # Non basta guardare quanto si e' spent: bisogna sapere quanto puo'
        # costare la prossima call. Il count dei token e' exact e
        # gratuito, quindi il cost maximum lo sappiamo in anticipo.
        system = [{"type": "text", "text": chosen_instructions(instruction_variant),
                    "cache_control": {"type": "ephemeral"}}]
        count = client.messages.count_tokens(
            model=model, system=system, tools=api_tools, messages=messages)
        input_tokens = count.input_tokens

        # --- se il context e' troppo grande, si accorcia il passato
        if input_tokens > COMPACTION_THRESHOLD:
            cut_ = compact_conversation(messages)
            if cut_:
                count = client.messages.count_tokens(
                    model=model, system=system, tools=api_tools,
                    messages=messages)
                show(f"     [context compattato: {cut_} results accorciati, "
                       f"{input_tokens:,} -> {count.input_tokens:,} token]")
                input_tokens = count.input_tokens
                t.compactions += 1

        spent_here = budget.spent - spent_at_start - network_charges_here
        problem_residue = problem_cap - spent_here
        max_tokens = budget.affordable_max_tokens(
            input_tokens, MAX_TOKENS, residue=problem_residue)

        if max_tokens < MIN_USEFUL_TOKENS:
            worst = budget.max_possible_cost(input_tokens, MIN_USEFUL_TOKENS)
            reason = (f"budget insufficiente per continuare: {input_tokens:,} token in "
                      f"ingresso, la prossima call costerebbe fino a "
                      f"${worst:.4f} ma restano ${min(budget.residue, problem_residue):.4f} "
                      f"(${budget.residue:.4f} sul total, ${problem_residue:.4f} su "
                      f"questo problem)")
            if budget.residue <= worst:
                # Il attempt va allegato all'eccezione: senza, il job fatto
                # su QUESTO problem sparisce dal report — cost, iterations e
                # checks comprese. E' successo davvero: nel giro 0 bis il
                # settimo problem risultava con $0,00 e zero checks mentre nel
                # log_ aveva one_ check consegnata e mezzo dollaro spent.
                # Un report che sottostima la spesa e' un problem di sicurezza,
                # non di cosmetica.
                t.reason = reason
                t.cause = t.classify_failure()
                t.seconds = time.time() - start_
                e = SpendLimitExceeded(reason)
                e.attempt = t
                raise e
            t.reason = reason                        # only_ questo problem si ferma
            break

        # doppia sicurezza: se also_ cosi' non ci sta, non parte
        budget.check_before_calling(input_tokens, max_tokens)

        tight = ("  ← SPAZIO STRETTO: la answer e' limitata dal budget, non "
                   "dal model" if max_tokens < TIGHT_TOKENS else "")
        show(f"\n  ── iteration {iteration}  {budget.riga_stato()}  "
               f"[{input_tokens:,} token in ingresso, fino a {max_tokens:,} in output, "
               f"al maximum ${budget.max_possible_cost(input_tokens, max_tokens):.4f}]"
               f"{tight}")

        it = Iteration(number=iteration)
        t0_api = time.time()
        try:
            with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": effort},
                tools=api_tools,
                messages=messages,
                cache_control={"type": "ephemeral"},   # mette in cache also_ la conversazione
            ) as stream:
                answer = stream.get_final_message()
        except NETWORK_ERRORS as e:
            # La conversazione non cambia: l'iteration successiva rifa' la stessa
            # call, after aver ricontrollato il budget con l'addebito fatto qui.
            it.api_seconds = time.time() - t0_api
            worst = _WorstCaseUsage(input_tokens, max_tokens)
            before = budget.spent
            # Il caso worst va sul budget TOTALE, che cosi' resta rigido, ma non
            # sul cap del problem ne' sul suo cost. La before versione lo
            # addebitava also_ li': un'interruzione da $0,84 consumava da sola un
            # cap da $1, e nella notte del 13 settembre sei attempts su dodici
            # sono finiti cosi', senza dire niente sull'agent.
            budget.record(worst)
            it.cost = budget.spent - before
            t.network_charge += it.cost
            network_charges_here += it.cost
            t.network_interruptions += 1
            t.detail.append(it)
            t.api_seconds += it.api_seconds
            consecutive_network_errors += 1
            show(f"     !! connessione interrupted ({type(e).__name__}: {e}); addebitati "
                   f"${it.cost:.4f} al budget total (il caso worst), non al cap del problem")
            if consecutive_network_errors >= MAX_CONSECUTIVE_NETWORK_ERRORS:
                t.reason = (f"error di rete ripetuto: {consecutive_network_errors} calls "
                            f"interrotte di fila ({type(e).__name__})")
                break
            time.sleep(10 * consecutive_network_errors)
            continue
        consecutive_network_errors = 0
        it.api_seconds = time.time() - t0_api

        before = budget.spent
        budget.record(answer.usage, problem.theorem)
        t.usage.add_(answer.usage)
        u = answer.usage
        it.input_tokens = getattr(u, "input_tokens", 0) or 0
        it.output_tokens = getattr(u, "output_tokens", 0) or 0
        it.cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
        it.cache_written = getattr(u, "cache_creation_input_tokens", 0) or 0
        it.cost = budget.spent - before

        if answer.stop_reason == "refusal":
            t.reason = "il model ha rifiutato la richiesta"
            break

        # mostra il reasoning e il text
        for block in answer.content:
            if block.type == "thinking" and getattr(block, "thinking", ""):
                show(f"     [reasoning] {block.thinking.strip()[:400]}")
            elif block.type == "text" and block.text.strip():
                show(f"     {block.text.strip()[:600]}")
        it.reasoning = " ".join(
            b.thinking for b in answer.content
            if b.type == "thinking" and getattr(b, "thinking", ""))[:4000]

        calls = [b for b in answer.content if b.type == "tool_use"]
        messages.append({"role": "assistant", "content": answer.content})

        if not calls:
            t.reason = "il model ha smesso di usare gli tools senza one_ trial accepted_"
            text = " ".join(b.text for b in answer.content if b.type == "text")
            t.transcript.append({"kind_": "end", "text": text})
            t.detail.append(it)
            t.api_seconds += it.api_seconds
            break

        results = []
        accepted_ = False
        for call in calls:
            if call.name == "lean_explore":
                t.explorations += 1
                it.explorations += 1
                code = call.input.get("lean_code", "")
                show(f"     -> lean_explore ({len(code)} chars)...")
                t0 = time.time()
                output = tools.run_lean_explore(
                    code, timeout=lean_timeout or 240)
                duration = time.time() - t0
                it.exploration_seconds += duration
                before = output.splitlines()[0] if output else "(vuoto)"
                show(f"        {before}  [{duration:.0f}s]")
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                  "content": output})
            elif call.name == "lean_check":
                t.checks += 1
                code = call.input.get("lean_code", "")
                show(f"     -> lean_check ({len(code)} chars)...")
                t0 = time.time()
                report, ok = tools.run_lean_check(
                    problem.theorem, code, timeout=lean_timeout)
                duration = time.time() - t0
                it.lean_seconds += duration
                failed, kind = _verification_kind(report, ok)
                it.checks.append(LeanCheck(
                    chars=len(code), result=report.split("\n")[0].replace("ESITO: ", ""),
                    failed_check=failed, seconds=duration, kind=kind))
                prima_riga = report.split("\n")[0]
                show(f"        {prima_riga}  [{kind}, {duration:.0f}s]")
                if ok:
                    accepted_ = True
                    t.solution = code
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                  "content": report})
            elif call.name == "run_python":
                t.python_runs += 1
                code = call.input.get("code", "")
                show(f"     -> run_python ({len(code)} chars)...")
                t0 = time.time()
                output = tools.run_python_tool(
                    code, folder=work_dir)
                it.python_seconds += time.time() - t0
                it.python_runs += 1
                show(f"        {output.strip()[:200]}")
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                  "content": output})
            else:
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                  "content": f"Strumento sconosciuto: {call.name}",
                                  "is_error": True})

        # Il model si rule_ meglio se sa quanto gli resta: chi ha misurato
        # OEIS Open dava al model one strumento apposta per questo.
        spent_here = budget.spent - spent_at_start - network_charges_here
        results.append({
            "type": "text",
            "text": (f"[budget: spesi ${spent_here:.2f} dei ${problem_cap:.2f} "
                     f"disponibili per questo problem; iteration {iteration} "
                     f"di {max_iterations}]")})
        messages.append({"role": "user", "content": results})
        t.detail.append(it)
        t.api_seconds += it.api_seconds
        t.lean_seconds += it.lean_seconds + it.exploration_seconds
        t.python_seconds += it.python_seconds

        if accepted_:
            t.solved_one = True
            t.reason = "dimostrazione accepted_ dal verifier"
            break
    else:
        t.reason = f"esaurite le {max_iterations} iterations disponibili"

    t.seconds = time.time() - start_
    t.cause = t.classify_failure()
    return t


# ---------------------------------------------------------------------------
# Riga di command
# ---------------------------------------------------------------------------

def write_report(path: Path, *, args, cap: float, budget: Budget,
                    attempts: list, full_: bool) -> None:
    """Scrive il resoconto JSON. `full_` e' falso finche' il giro non e' finito."""
    path.write_text(json.dumps({
        "model": args.model, "effort": args.effort,
        "istruzioni": args.istruzioni,
        "problem_cap": cap,
        "budget": args.budget, "spent": budget.spent,
        "full_": full_,
        "consumo_totale": budget.usage.__dict__,
        "attempts": [{
            "problem": t.problem, "solved_one": t.solved_one, "reason": t.reason,
            "cause": t.cause,
            "iterations": t.iterations, "checks": t.checks,
            "explorations": t.explorations,
            "python_runs": t.python_runs,
            "network_interruptions": t.network_interruptions,
            "addebito_rete_prudenziale": t.network_charge,
            "secondi_totali": t.seconds,
            "api_seconds": t.api_seconds,
            "lean_seconds": t.lean_seconds,
            "python_seconds": t.python_seconds,
            "cost": t.usage.cost(args.model), "usage": t.usage.__dict__,
            "verifications_by_kind": t.verifications_by_kind,
            "iterazioni_dettaglio": [{
                "number": it.number, "cost": it.cost,
                "input_tokens": it.input_tokens, "output_tokens": it.output_tokens,
                "cache_written": it.cache_written, "cache_read": it.cache_read,
                "api_seconds": it.api_seconds, "lean_seconds": it.lean_seconds,
                "python_seconds": it.python_seconds,
                "python_runs": it.python_runs,
                "explorations": it.explorations,
                "exploration_seconds": it.exploration_seconds,
                "checks": [{
                    "chars": v.chars, "result": v.result,
                    "failed_check": v.failed_check,
                    "seconds": v.seconds, "kind": v.kind,
                } for v in it.checks],
                "reasoning": it.reasoning,
            } for it in t.detail],
            "solution": t.solution,
        } for t in attempts],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Tenta di dimostrare one o piu' problems dell'archive con l'API di Anthropic.")
    ap.add_argument("problems", nargs="*", help="names dei theorems da tentare")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"model da usare (default: {DEFAULT_MODEL})")
    ap.add_argument("--budget", type=float, default=5.0,
                    help="limit di spesa RIGIDO in dollari per l'intera esecuzione (default: 5)")
    ap.add_argument("--cap-problem", type=float, default=None,
                    help="spesa massima per singolo problem (default: budget diviso il number di problems)")
    ap.add_argument("--max-iterations", type=int, default=30)
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--timeout-lean", type=int, default=None)
    ap.add_argument("--report", default=None, help="dove salvare il resoconto JSON")
    ap.add_argument("--istruzioni", default="attuali",
                    choices=["attuali", "insistenti"],
                    help="which variant del prompt di system usare. "
                         "'insistenti' toglie l'invito ad arrendersi e dice che "
                         "il budget e' da consumare (vedi INSISTENT_INSTRUCTIONS)")
    ap.add_argument("--log_", default=None,
                    help="dove scrivere il log_ line per line (predefinito: "
                         "runs/jobs/agent-<data>.log). Serve per seguire il "
                         "job con `tail -f` mentre gira.")
    ap.add_argument("--silenzioso", action="store_true")
    ap.add_argument("--senza-awake", action="store_true",
                    help="non avviare caffeinate e non controllare l'alimentatore "
                         "(sconsigliato: vedi agent/awake.py)")
    args = ap.parse_args()

    # --- il log_, before di qualunque show
    log_path = Path(args.log_) if args.log_ else (
        verifier_config.ROOT / "runs" / "jobs" /
        f"agent-{time.strftime('%Y%m%d-%H%M%S')}.log")
    sys.stdout = _Doppio(sys.stdout, log_path)
    print(f"Registro: {log_path}")
    print(f"  da un other terminale:  tail -f {log_path}")

    load_env()

    if not args.problems:
        ap.error("indica almeno un theorem_ da tentare")

    environment_problems = verifier_config.check_installation()
    if environment_problems:
        print("Ambiente non ready:\n  - " + "\n  - ".join(environment_problems), file=sys.stderr)
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        print("Manca la key_ API.\n"
              f"Crea il file {ROOT / '.env'} con inside one_ line:\n"
              "  ANTHROPIC_API_KEY=sk-ant-...\n"
              "(il file e' gia' escluso da git, quindi la key_ non verra' mai committata)",
              file=sys.stderr)
        return 2

    index = ProblemIndex.load()
    try:
        listing = [index.get(n) for n in args.problems]
    except KeyError as e:
        print(e, file=sys.stderr)
        return 2

    # --- il Mac deve restare sveglio: si controlla PRIMA di spendere un centesimo
    awake_process = None
    if not args.senza_veglia and sys.platform == "darwin":
        awake_process = awake.start_job(os.getpid())
        reasons = awake.controlla(awake_process)
        if reasons:
            awake_process.terminate()
            print("NON PARTO: il Mac deve restare sveglio e alimentato per tutto il giro.\n  - "
                  + "\n  - ".join(reasons)
                  + "\nTieni also_ il coperchio aperto: a coperchio chiuso il Mac si sospende "
                    "comunque. Per saltare il controllo: --senza-awake (sconsigliato).",
                  file=sys.stderr)
            return 2
        print("Veglia: caffeinate attivo, alimentatore collegato. Tieni il coperchio aperto.")

    client = anthropic.Anthropic()
    budget = Budget(dollar_limit=args.budget, model=args.model)
    cap = args.problem_cap or (args.budget / len(listing))

    print(f"Modello: {args.model} | effort: {args.effort} | "
          f"istruzioni: {args.istruzioni}")
    print(f"Budget total: ${args.budget:.2f}  (cap per problem: ${cap:.2f})")
    print(f"Problemi: {len(listing)}")

    attempts: list[Attempt] = []

    def salva(full_: bool) -> None:
        # Il report si riscrive after OGNI problem. Il 12 settembre un error di
        # rete ha fermato un giro al terzo problem e, siccome il report si
        # scriveva only_ alla end, i two attempts gia' conclusi sono vanished.
        if args.report:
            write_report(Path(args.report), args=args, cap=cap, budget=budget,
                            attempts=attempts, full_=full_)

    for i, p in enumerate(listing, 1):
        if awake_process is not None and not awake.on_mains_power():
            print(f"\n!! Alimentatore scollegato: mi fermo before di {p.theorem}. "
                  f"Il report contiene i problems gia' conclusi.")
            break
        print(f"\n{'='*78}\n[{i}/{len(listing)}] {p.theorem}   ({p.category})\n{'='*78}")
        try:
            t = solve_(p, index, client=client, model=args.model, budget=budget,
                        problem_cap=cap, max_iterations=args.max_iterations,
                        effort=args.effort, lean_timeout=args.lean_timeout,
                        verbose=not args.silenzioso,
                        instruction_variant=args.istruzioni)
        except SpendLimitExceeded as e:
            print(f"\n!! {e}")
            partial = getattr(e, "attempt", None)
            attempts.append(partial if partial is not None
                             else Attempt(problem=p.theorem, reason=str(e)))
            if partial is not None:
                print(f"     job svolto before di fermarsi: "
                      f"{partial.iterations} iterations, {partial.checks} "
                      f"checks, ${partial.usage.cost(args.model):.4f}")
            break
        except anthropic.APIError as e:
            print(f"\n!! Errore dall'API: {e}")
            attempts.append(Attempt(problem=p.theorem, reason=f"error API: {e}"))
            salva(full_=False)
            continue
        attempts.append(t)
        salva(full_=False)
        result = "RISOLTO" if t.solved_one else "non solved_one"
        print(f"\n  => {result}: {t.reason}")
        print(f"     {t.iterations} iterations, {t.explorations} explorations, "
              f"{t.checks} checks Lean, "
              f"{t.python_runs} esecuzioni Python, {t.seconds:.0f}s, "
              f"${t.usage.cost(args.model):.4f}")
        print(f"     tempo: {t.api_seconds:.0f}s in expected_value dell'API, "
              f"{t.lean_seconds:.0f}s di Lean in local_, "
              f"{t.python_seconds:.0f}s di Python in local_")
        print(f"     kind delle checks: {t.verifications_by_kind or 'nessuna'}")
        print(f"     cause: {t.cause}")

    # --- resoconto
    print(f"\n{'='*78}\nRESOCONTO\n{'='*78}")
    solved_ = sum(1 for t in attempts if t.solved_one)
    for t in attempts:
        print(f"  [{'RISOLTO    ' if t.solved_one else 'non solved_one'}] {t.problem}"
              f"   ${t.usage.cost(args.model):.4f}   {t.reason}")
    print(f"\n  Risolti: {solved_}/{len(attempts)}")
    print(f"  Spesa total: ${budget.spent:.4f} su ${args.budget:.2f} disponibili")
    print(f"  {budget.usage.riassunto(args.model)}")

    if args.report:
        salva(full_=True)
        print(f"\n  Resoconto salvato in {args.report}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
