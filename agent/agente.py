#!/usr/bin/env python3
"""
Un agente minimo che tenta di dimostrare un problema dell'archivio.

COME FUNZIONA
-------------
E' un ciclo semplice:

  1. si manda al modello l'enunciato da dimostrare e le regole;
  2. il modello risponde, eventualmente chiedendo di usare uno strumento;
  3. si esegue lo strumento e gli si restituisce il risultato;
  4. si ripete finche' il modello smette di chiedere strumenti, oppure finche'
     `lean_check` accetta una dimostrazione, oppure finche' finiscono i soldi
     o i tentativi.

Gli strumenti disponibili sono due (vedi agent/strumenti.py):
  * `lean_check`  — sottopone un file Lean al verificatore;
  * `run_python`  — esegue codice Python isolato, senza rete, con timeout.

IL LIMITE DI SPESA
------------------
E' un limite RIGIDO, calcolato dai campi `usage` che l'API restituisce a ogni
risposta — quindi dai token davvero fatturati, non da una stima. Prima di ogni
chiamata si controlla il saldo: se e' esaurito, l'agente si ferma e lo dice.
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "agent"))

import config as config_verificatore          # noqa: E402
from index import ProblemIndex, Problem       # noqa: E402
from costi import Budget, LimiteSpesaSuperato, Consumo   # noqa: E402

#: Spazio massimo concesso a una risposta. Serve alto perche' il ragionamento
#: esteso ci rientra dentro; il controllo del budget lo riduce se serve.
MAX_TOKENS = 32_000

#: Sotto questa soglia una risposta non puo' essere utile: meglio fermarsi che
#: pagare per un ragionamento troncato a metа.
MIN_TOKENS_UTILI = 6_000
from nascondi import file_senza_dimostrazioni, controlla_che_sia_nascosta  # noqa: E402
import strumenti                              # noqa: E402


MODELLO_PREDEFINITO = "claude-opus-5"


def carica_env() -> None:
    """Legge il file `.env` del progetto e ne mette le variabili nell'ambiente.

    Serve per la chiave API. Il file e' escluso da git (vedi .gitignore), cosi'
    la chiave non finisce per sbaglio in un commit. Le variabili gia' presenti
    nell'ambiente hanno la precedenza e non vengono sovrascritte.
    """
    percorso = ROOT / ".env"
    if not percorso.is_file():
        return
    for riga in percorso.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        chiave, _, valore = riga.partition("=")
        chiave = chiave.strip()
        valore = valore.strip().strip('"').strip("'")
        if chiave and chiave not in os.environ:
            os.environ[chiave] = valore


# ---------------------------------------------------------------------------
# Il testo di sistema (istruzioni fisse). Va tenuto STABILE fra una chiamata e
# l'altra: e' la parte che viene messa in cache, e qualunque byte diverso
# invaliderebbe la cache facendo pagare tutto a prezzo pieno.
# ---------------------------------------------------------------------------

ISTRUZIONI = """You are working on the `formal-conjectures` benchmark (Google DeepMind), \
proving theorems in Lean 4 with Mathlib.

You will be given one theorem to prove. Your answer is judged by a program, not \
by a person, so the rules below are absolute.

# What you must produce

A single, self-contained Lean 4 file that:

1. Starts with `import {MODULO_UTILITA}` (you may add `import Mathlib...` \
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
fresh names, and prove them properly.

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


def _natura_della_verifica(rapporto: str, accettato: bool) -> tuple[str, str]:
    """Ritorna (controllo fallito, natura), leggendo il rapporto di verify.py."""
    if accettato:
        return "", "accettato"
    fallito = ""
    for riga in rapporto.split("\n"):
        if riga.strip().startswith("[FALLITO]"):
            fallito = riga.split("]", 1)[1].split("—")[0].strip()
            break
    testo = rapporto.lower()
    if "non dichiara" in testo or "not found in solution" in testo:
        return fallito, "esplorazione"
    if "non compila" in testo or "compila senza errori" in fallito:
        return fallito, "errore_tecnico"
    if "assiom" in fallito:
        return fallito, "buco_o_assioma"
    if "tipo identico" in fallito or "definizioni dell" in fallito:
        return fallito, "enunciato_sbagliato"
    return fallito, "errore_tecnico"


def istruzioni() -> str:
    """Le istruzioni, con il nome del modulo di utilita' di QUESTO snapshot.

    Cambia fra le versioni dell'archivio: `FormalConjectures.Util.ProblemImports`
    nel tag bench-v1, `FormalConjecturesUtil` nel ramo main. Scriverlo fisso
    faceva fallire ogni tentativo sul secondo snapshot.
    """
    return ISTRUZIONI.replace("{MODULO_UTILITA}", config_verificatore.modulo_utilita())


def messaggio_problema(problema: Problem, testo_file: str) -> str:
    descrizione = (problema.docstring or "").strip()
    return f"""# The problem

**Theorem to prove:** `{problema.theorem}`
**Module it lives in:** `{problema.module}` (do NOT import this)
**Category:** {problema.category}

{"**Informal statement:** " + descrizione if descrizione else ""}

Below is the problem's source file, with every proof replaced by `sorry`.
Everything else — imports, `open` commands, definitions, notation — is exactly
as it appears in the archive. Your file must reproduce whatever the statement
depends on.

```lean
{testo_file}
```

Produce a complete Lean file proving `{problema.theorem}`, and check it with
`lean_check`."""


# ---------------------------------------------------------------------------
# Risultato di un tentativo
# ---------------------------------------------------------------------------

@dataclass
class VerificaLean:
    """Una singola chiamata a lean_check, con il suo esito misurato."""
    caratteri: int
    esito: str                  # ACCETTATO / RIFIUTATO / ERRORE / TIMEOUT
    controllo_fallito: str      # quale controllo non e' passato
    secondi: float              # tempo di calcolo LOCALE (Lean), non dell'API
    #: come classifichiamo il tentativo. Regola dichiarata:
    #:   esplorazione        -> il file non dichiarava il teorema richiesto
    #:                          (il modello stava ispezionando, non tentando)
    #:   errore_tecnico      -> il file non compila
    #:   buco_o_assioma      -> compila ma la dimostrazione ha un buco
    #:   enunciato_sbagliato -> compila ma dimostra un'altra cosa
    #:   accettato           -> superato
    natura: str


@dataclass
class Iterazione:
    """Una passata del ciclo: una chiamata all'API piu' gli strumenti usati."""
    numero: int
    token_input: int = 0
    token_output: int = 0
    cache_scritta: int = 0
    cache_letta: int = 0
    costo: float = 0.0
    secondi_api: float = 0.0
    secondi_lean: float = 0.0
    secondi_python: float = 0.0
    verifiche: list = field(default_factory=list)     # list[VerificaLean]
    esecuzioni_python: int = 0
    esplorazioni: int = 0
    secondi_esplorazione: float = 0.0
    ragionamento: str = ""


@dataclass
class Tentativo:
    problema: str
    risolto: bool = False
    motivo: str = ""
    iterazioni: int = 0
    verifiche: int = 0
    esplorazioni: int = 0
    esecuzioni_python: int = 0
    secondi: float = 0.0
    consumo: Consumo = field(default_factory=Consumo)
    soluzione: str = ""
    trascrizione: list = field(default_factory=list)
    #: misurazioni per iterazione
    dettaglio: list = field(default_factory=list)      # list[Iterazione]
    secondi_api: float = 0.0
    secondi_lean: float = 0.0
    secondi_python: float = 0.0
    #: quante volte la conversazione e' stata accorciata per far spazio
    compattazioni: int = 0
    #: classificazione del fallimento, secondo la regola dichiarata sotto
    causa: str = ""

    @property
    def verifiche_per_natura(self) -> dict:
        conta: dict = {}
        for it in self.dettaglio:
            for v in it.verifiche:
                conta[v.natura] = conta.get(v.natura, 0) + 1
        return conta

    def classifica_fallimento(self) -> str:
        """Distingue un fallimento MATEMATICO da uno di SISTEMA.

        Regola dichiarata, non a sensazione:
          * se non c'e' stato nessun tentativo vero (tutte le verifiche erano
            esplorazioni), il fallimento e' di SISTEMA: l'agente non e' arrivato
            a provarci, ha speso tutto a capire gli strumenti e l'API di Mathlib;
          * se i tentativi veri sono finiti solo con errori di compilazione, e'
            TECNICO: sapeva cosa fare ma non come scriverlo in Lean;
          * se almeno un tentativo e' arrivato a compilare e ha fallito per un
            buco o per l'enunciato sbagliato, e' MATEMATICO: la dimostrazione
            non c'era.
        """
        if self.risolto:
            return "risolto"
        n = self.verifiche_per_natura
        veri = n.get("errore_tecnico", 0) + n.get("buco_o_assioma", 0) + \
            n.get("enunciato_sbagliato", 0)
        if veri == 0:
            return "sistema: nessun tentativo vero, tutto speso in esplorazione"
        if n.get("buco_o_assioma", 0) or n.get("enunciato_sbagliato", 0):
            return "matematico: ha compilato ma la dimostrazione non c'era"
        return "tecnico: sapeva cosa dimostrare ma non e' riuscito a scriverlo in Lean"


#: Oltre questa soglia di token in ingresso la conversazione viene compattata.
#: Serve per i tentativi lunghi: chi ha misurato il benchmark OEIS Open spendeva
#: $50 per problema, cioe' dell'ordine di 200 iterazioni. Senza compattazione la
#: conversazione supera la finestra del modello e il tentativo muore per
#: esaurimento di contesto invece che di idee.
SOGLIA_COMPATTAZIONE = 120_000

#: Quanti messaggi in coda restano intatti quando si compatta. Il modello deve
#: vedere per intero il suo lavoro recente; quello vecchio gli serve come traccia.
MESSAGGI_INTATTI = 8

#: A quanti caratteri si riducono i risultati degli strumenti piu' vecchi.
CODA_RISULTATI_VECCHI = 600

_SEGNO_TAGLIO = "\n… [risultato accorciato per far spazio nel contesto; "\
                "se ti serve di nuovo, richiedilo]"


def compatta_conversazione(messaggi: list, *, intatti: int = MESSAGGI_INTATTI,
                           coda: int = CODA_RISULTATI_VECCHI) -> int:
    """Accorcia i risultati degli strumenti piu' vecchi. Ritorna quanti ne accorcia.

    Il primo messaggio (l'enunciato del problema) e gli ultimi `intatti` non si
    toccano mai. Si accorciano solo i `tool_result`, perche' sono il grosso: un
    errore di Lean arriva a 40 000 caratteri, e in duecento iterazioni sono
    milioni. Il codice che il modello ha scritto (i `tool_use`) resta intero: e'
    il suo lavoro, e ricostruirlo costerebbe piu' di quanto occupa.
    """
    if len(messaggi) <= intatti + 1:
        return 0
    tagliati = 0
    for msg in messaggi[1:len(messaggi) - intatti]:
        contenuto = msg.get("content")
        if not isinstance(contenuto, list):
            continue
        for blocco in contenuto:
            if not isinstance(blocco, dict) or blocco.get("type") != "tool_result":
                continue
            testo = blocco.get("content")
            if not isinstance(testo, str) or len(testo) <= coda:
                continue
            if testo.endswith(_SEGNO_TAGLIO):
                continue
            blocco["content"] = testo[:coda] + _SEGNO_TAGLIO
            tagliati += 1
    return tagliati


# ---------------------------------------------------------------------------
# Il ciclo
# ---------------------------------------------------------------------------

def risolvi(problema: Problem, indice: ProblemIndex, *, client, modello: str,
            budget: Budget, tetto_problema: float, max_iterazioni: int = 30,
            effort: str = "high", timeout_lean: int | None = None,
            verboso: bool = True) -> Tentativo:

    avvio = time.time()
    t = Tentativo(problema=problema.theorem)

    testo_file = file_senza_dimostrazioni(problema, indice)
    try:
        # Il collaudo dev'essere onesto: se la dimostrazione non e' stata
        # nascosta, il problema si SALTA. Prima interrompeva tutta l'esecuzione,
        # e una calibrazione da undici problemi si fermava al terzo.
        controlla_che_sia_nascosta(problema, testo_file)
    except AssertionError as e:
        t.motivo = f"saltato: {e}"
        t.causa = "sistema: la dimostrazione dell'archivio non si riesce a nascondere"
        t.secondi = time.time() - avvio
        return t

    strumenti_api = [strumenti.SCHEMA_LEAN_EXPLORE, strumenti.SCHEMA_LEAN_CHECK,
                     strumenti.SCHEMA_RUN_PYTHON]

    # Una cartella di lavoro per problema, che sopravvive alle chiamate: serve
    # perche' una ricerca in piu' passi possa salvare un checkpoint. Il nome e'
    # ripulito perche' i nomi dei teoremi contengono punti e caratteri strani.
    nome_pulito = re.sub(r"[^A-Za-z0-9_.-]", "_", problema.theorem)[:80]
    cartella_lavoro = config_verificatore.ROOT / "runs" / "lavoro" / nome_pulito
    cartella_lavoro.mkdir(parents=True, exist_ok=True)
    messaggi = [{"role": "user", "content": messaggio_problema(problema, testo_file)}]

    speso_all_inizio = budget.speso

    def stampa(*a):
        if verboso:
            print(*a, flush=True)

    for iterazione in range(1, max_iterazioni + 1):
        t.iterazioni = iterazione

        # --- il controllo del portafoglio, PRIMA di spendere -------------
        # Non basta guardare quanto si e' speso: bisogna sapere quanto puo'
        # costare la prossima chiamata. Il conteggio dei token e' esatto e
        # gratuito, quindi il costo massimo lo sappiamo in anticipo.
        sistema = [{"type": "text", "text": istruzioni(),
                    "cache_control": {"type": "ephemeral"}}]
        conteggio = client.messages.count_tokens(
            model=modello, system=sistema, tools=strumenti_api, messages=messaggi)
        token_input = conteggio.input_tokens

        # --- se il contesto e' troppo grande, si accorcia il passato
        if token_input > SOGLIA_COMPATTAZIONE:
            tagliati = compatta_conversazione(messaggi)
            if tagliati:
                conteggio = client.messages.count_tokens(
                    model=modello, system=sistema, tools=strumenti_api,
                    messages=messaggi)
                stampa(f"     [contesto compattato: {tagliati} risultati accorciati, "
                       f"{token_input:,} -> {conteggio.input_tokens:,} token]")
                token_input = conteggio.input_tokens
                t.compattazioni += 1

        speso_qui = budget.speso - speso_all_inizio
        residuo_problema = tetto_problema - speso_qui
        max_tokens = budget.max_tokens_sostenibile(
            token_input, MAX_TOKENS, residuo=residuo_problema)

        if max_tokens < MIN_TOKENS_UTILI:
            peggiore = budget.costo_massimo_possibile(token_input, MIN_TOKENS_UTILI)
            motivo = (f"budget insufficiente per continuare: {token_input:,} token in "
                      f"ingresso, la prossima chiamata costerebbe fino a "
                      f"${peggiore:.4f} ma restano ${min(budget.residuo, residuo_problema):.4f} "
                      f"(${budget.residuo:.4f} sul totale, ${residuo_problema:.4f} su "
                      f"questo problema)")
            if budget.residuo <= peggiore:
                raise LimiteSpesaSuperato(motivo)   # ferma tutta l'esecuzione
            t.motivo = motivo                        # solo questo problema si ferma
            break

        # doppia sicurezza: se anche cosi' non ci sta, non parte
        budget.verifica_prima_di_chiamare(token_input, max_tokens)

        stampa(f"\n  ── iterazione {iterazione}  {budget.riga_stato()}  "
               f"[{token_input:,} token in ingresso, fino a {max_tokens:,} in uscita, "
               f"al massimo ${budget.costo_massimo_possibile(token_input, max_tokens):.4f}]")

        it = Iterazione(numero=iterazione)
        t0_api = time.time()
        with client.messages.stream(
            model=modello,
            max_tokens=max_tokens,
            system=sistema,
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": effort},
            tools=strumenti_api,
            messages=messaggi,
            cache_control={"type": "ephemeral"},   # mette in cache anche la conversazione
        ) as flusso:
            risposta = flusso.get_final_message()
        it.secondi_api = time.time() - t0_api

        prima = budget.speso
        budget.registra(risposta.usage, problema.theorem)
        t.consumo.aggiungi(risposta.usage)
        u = risposta.usage
        it.token_input = getattr(u, "input_tokens", 0) or 0
        it.token_output = getattr(u, "output_tokens", 0) or 0
        it.cache_letta = getattr(u, "cache_read_input_tokens", 0) or 0
        it.cache_scritta = getattr(u, "cache_creation_input_tokens", 0) or 0
        it.costo = budget.speso - prima

        if risposta.stop_reason == "refusal":
            t.motivo = "il modello ha rifiutato la richiesta"
            break

        # mostra il ragionamento e il testo
        for blocco in risposta.content:
            if blocco.type == "thinking" and getattr(blocco, "thinking", ""):
                stampa(f"     [ragionamento] {blocco.thinking.strip()[:400]}")
            elif blocco.type == "text" and blocco.text.strip():
                stampa(f"     {blocco.text.strip()[:600]}")
        it.ragionamento = " ".join(
            b.thinking for b in risposta.content
            if b.type == "thinking" and getattr(b, "thinking", ""))[:4000]

        chiamate = [b for b in risposta.content if b.type == "tool_use"]
        messaggi.append({"role": "assistant", "content": risposta.content})

        if not chiamate:
            t.motivo = "il modello ha smesso di usare gli strumenti senza una prova accettata"
            testo = " ".join(b.text for b in risposta.content if b.type == "text")
            t.trascrizione.append({"tipo": "fine", "testo": testo})
            t.dettaglio.append(it)
            t.secondi_api += it.secondi_api
            break

        risultati = []
        accettata = False
        for chiamata in chiamate:
            if chiamata.name == "lean_explore":
                t.esplorazioni += 1
                it.esplorazioni += 1
                codice = chiamata.input.get("codice_lean", "")
                stampa(f"     -> lean_explore ({len(codice)} caratteri)...")
                t0 = time.time()
                uscita = strumenti.esegui_lean_explore(
                    codice, timeout=timeout_lean or 240)
                durata = time.time() - t0
                it.secondi_esplorazione += durata
                prima = uscita.splitlines()[0] if uscita else "(vuoto)"
                stampa(f"        {prima}  [{durata:.0f}s]")
                risultati.append({"type": "tool_result", "tool_use_id": chiamata.id,
                                  "content": uscita})
            elif chiamata.name == "lean_check":
                t.verifiche += 1
                codice = chiamata.input.get("codice_lean", "")
                stampa(f"     -> lean_check ({len(codice)} caratteri)...")
                t0 = time.time()
                rapporto, ok = strumenti.esegui_lean_check(
                    problema.theorem, codice, timeout=timeout_lean)
                durata = time.time() - t0
                it.secondi_lean += durata
                fallito, natura = _natura_della_verifica(rapporto, ok)
                it.verifiche.append(VerificaLean(
                    caratteri=len(codice), esito=rapporto.split("\n")[0].replace("ESITO: ", ""),
                    controllo_fallito=fallito, secondi=durata, natura=natura))
                prima_riga = rapporto.split("\n")[0]
                stampa(f"        {prima_riga}  [{natura}, {durata:.0f}s]")
                if ok:
                    accettata = True
                    t.soluzione = codice
                risultati.append({"type": "tool_result", "tool_use_id": chiamata.id,
                                  "content": rapporto})
            elif chiamata.name == "run_python":
                t.esecuzioni_python += 1
                codice = chiamata.input.get("codice", "")
                stampa(f"     -> run_python ({len(codice)} caratteri)...")
                t0 = time.time()
                uscita = strumenti.esegui_run_python(
                    codice, cartella=cartella_lavoro)
                it.secondi_python += time.time() - t0
                it.esecuzioni_python += 1
                stampa(f"        {uscita.strip()[:200]}")
                risultati.append({"type": "tool_result", "tool_use_id": chiamata.id,
                                  "content": uscita})
            else:
                risultati.append({"type": "tool_result", "tool_use_id": chiamata.id,
                                  "content": f"Strumento sconosciuto: {chiamata.name}",
                                  "is_error": True})

        # Il modello si regola meglio se sa quanto gli resta: chi ha misurato
        # OEIS Open dava al modello uno strumento apposta per questo.
        speso_qui = budget.speso - speso_all_inizio
        risultati.append({
            "type": "text",
            "text": (f"[budget: spesi ${speso_qui:.2f} dei ${tetto_problema:.2f} "
                     f"disponibili per questo problema; iterazione {iterazione} "
                     f"di {max_iterazioni}]")})
        messaggi.append({"role": "user", "content": risultati})
        t.dettaglio.append(it)
        t.secondi_api += it.secondi_api
        t.secondi_lean += it.secondi_lean + it.secondi_esplorazione
        t.secondi_python += it.secondi_python

        if accettata:
            t.risolto = True
            t.motivo = "dimostrazione accettata dal verificatore"
            break
    else:
        t.motivo = f"esaurite le {max_iterazioni} iterazioni disponibili"

    t.secondi = time.time() - avvio
    t.causa = t.classifica_fallimento()
    return t


# ---------------------------------------------------------------------------
# Riga di comando
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Tenta di dimostrare uno o piu' problemi dell'archivio con l'API di Anthropic.")
    ap.add_argument("problemi", nargs="*", help="nomi dei teoremi da tentare")
    ap.add_argument("--modello", default=MODELLO_PREDEFINITO,
                    help=f"modello da usare (default: {MODELLO_PREDEFINITO})")
    ap.add_argument("--budget", type=float, default=5.0,
                    help="limite di spesa RIGIDO in dollari per l'intera esecuzione (default: 5)")
    ap.add_argument("--tetto-problema", type=float, default=None,
                    help="spesa massima per singolo problema (default: budget diviso il numero di problemi)")
    ap.add_argument("--max-iterazioni", type=int, default=30)
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--timeout-lean", type=int, default=None)
    ap.add_argument("--rapporto", default=None, help="dove salvare il resoconto JSON")
    ap.add_argument("--silenzioso", action="store_true")
    args = ap.parse_args()

    carica_env()

    if not args.problemi:
        ap.error("indica almeno un teorema da tentare")

    problemi_ambiente = config_verificatore.check_installation()
    if problemi_ambiente:
        print("Ambiente non pronto:\n  - " + "\n  - ".join(problemi_ambiente), file=sys.stderr)
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        print("Manca la chiave API.\n"
              f"Crea il file {ROOT / '.env'} con dentro una riga:\n"
              "  ANTHROPIC_API_KEY=sk-ant-...\n"
              "(il file e' gia' escluso da git, quindi la chiave non verra' mai committata)",
              file=sys.stderr)
        return 2

    indice = ProblemIndex.load()
    try:
        elenco = [indice.get(n) for n in args.problemi]
    except KeyError as e:
        print(e, file=sys.stderr)
        return 2

    client = anthropic.Anthropic()
    budget = Budget(limite_dollari=args.budget, modello=args.modello)
    tetto = args.tetto_problema or (args.budget / len(elenco))

    print(f"Modello: {args.modello} | effort: {args.effort}")
    print(f"Budget totale: ${args.budget:.2f}  (tetto per problema: ${tetto:.2f})")
    print(f"Problemi: {len(elenco)}")

    tentativi: list[Tentativo] = []
    for i, p in enumerate(elenco, 1):
        print(f"\n{'='*78}\n[{i}/{len(elenco)}] {p.theorem}   ({p.category})\n{'='*78}")
        try:
            t = risolvi(p, indice, client=client, modello=args.modello, budget=budget,
                        tetto_problema=tetto, max_iterazioni=args.max_iterazioni,
                        effort=args.effort, timeout_lean=args.timeout_lean,
                        verboso=not args.silenzioso)
        except LimiteSpesaSuperato as e:
            print(f"\n!! {e}")
            tentativi.append(Tentativo(problema=p.theorem, motivo=str(e)))
            break
        except anthropic.APIError as e:
            print(f"\n!! Errore dall'API: {e}")
            tentativi.append(Tentativo(problema=p.theorem, motivo=f"errore API: {e}"))
            continue
        tentativi.append(t)
        esito = "RISOLTO" if t.risolto else "non risolto"
        print(f"\n  => {esito}: {t.motivo}")
        print(f"     {t.iterazioni} iterazioni, {t.esplorazioni} esplorazioni, "
              f"{t.verifiche} verifiche Lean, "
              f"{t.esecuzioni_python} esecuzioni Python, {t.secondi:.0f}s, "
              f"${t.consumo.costo(args.modello):.4f}")
        print(f"     tempo: {t.secondi_api:.0f}s in attesa dell'API, "
              f"{t.secondi_lean:.0f}s di Lean in locale, "
              f"{t.secondi_python:.0f}s di Python in locale")
        print(f"     natura delle verifiche: {t.verifiche_per_natura or 'nessuna'}")
        print(f"     causa: {t.causa}")

    # --- resoconto
    print(f"\n{'='*78}\nRESOCONTO\n{'='*78}")
    risolti = sum(1 for t in tentativi if t.risolto)
    for t in tentativi:
        print(f"  [{'RISOLTO    ' if t.risolto else 'non risolto'}] {t.problema}"
              f"   ${t.consumo.costo(args.modello):.4f}   {t.motivo}")
    print(f"\n  Risolti: {risolti}/{len(tentativi)}")
    print(f"  Spesa totale: ${budget.speso:.4f} su ${args.budget:.2f} disponibili")
    print(f"  {budget.consumo.riassunto(args.modello)}")

    if args.rapporto:
        Path(args.rapporto).write_text(json.dumps({
            "modello": args.modello, "effort": args.effort,
            "budget": args.budget, "speso": budget.speso,
            "consumo_totale": budget.consumo.__dict__,
            "tentativi": [{
                "problema": t.problema, "risolto": t.risolto, "motivo": t.motivo,
                "causa": t.causa,
                "iterazioni": t.iterazioni, "verifiche": t.verifiche,
                "esplorazioni": t.esplorazioni,
                "esecuzioni_python": t.esecuzioni_python,
                "secondi_totali": t.secondi,
                "secondi_api": t.secondi_api,
                "secondi_lean": t.secondi_lean,
                "secondi_python": t.secondi_python,
                "costo": t.consumo.costo(args.modello), "consumo": t.consumo.__dict__,
                "verifiche_per_natura": t.verifiche_per_natura,
                "iterazioni_dettaglio": [{
                    "numero": it.numero, "costo": it.costo,
                    "token_input": it.token_input, "token_output": it.token_output,
                    "cache_scritta": it.cache_scritta, "cache_letta": it.cache_letta,
                    "secondi_api": it.secondi_api, "secondi_lean": it.secondi_lean,
                    "secondi_python": it.secondi_python,
                    "esecuzioni_python": it.esecuzioni_python,
                    "esplorazioni": it.esplorazioni,
                    "secondi_esplorazione": it.secondi_esplorazione,
                    "verifiche": [{
                        "caratteri": v.caratteri, "esito": v.esito,
                        "controllo_fallito": v.controllo_fallito,
                        "secondi": v.secondi, "natura": v.natura,
                    } for v in it.verifiche],
                    "ragionamento": it.ragionamento,
                } for it in t.dettaglio],
                "soluzione": t.soluzione,
            } for t in tentativi],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  Resoconto salvato in {args.rapporto}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
