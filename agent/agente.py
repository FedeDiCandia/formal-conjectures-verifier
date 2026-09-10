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

1. Starts with `import FormalConjectures.Util.ProblemImports` (you may add \
`import Mathlib...` lines if you need something specific).
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

- Call `lean_check` early and often. It is the only judgment that counts, and \
guessing is expensive. A check takes about 30 seconds.
- Read the Lean error messages carefully; they tell you exactly what failed.
- Use `run_python` for anything computational: searching for a witness or a \
counterexample, checking a hypothesis on small cases, computing a constant. \
Do not do arithmetic in your head when you can compute it.
- If a proof strategy fails twice in a row, change strategy rather than \
patching it.
- You do not have internet access and cannot read Mathlib's source. Rely on \
what you know about Mathlib's API, and let the error messages correct you.
- Stop when `lean_check` reports ACCETTATO. If you become convinced the problem \
is beyond you, say so plainly instead of submitting a proof you know is broken."""


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
class Tentativo:
    problema: str
    risolto: bool = False
    motivo: str = ""
    iterazioni: int = 0
    verifiche: int = 0
    esecuzioni_python: int = 0
    secondi: float = 0.0
    consumo: Consumo = field(default_factory=Consumo)
    soluzione: str = ""
    trascrizione: list = field(default_factory=list)


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
    controlla_che_sia_nascosta(problema, testo_file)   # il collaudo dev'essere onesto

    strumenti_api = [strumenti.SCHEMA_LEAN_CHECK, strumenti.SCHEMA_RUN_PYTHON]
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
        sistema = [{"type": "text", "text": ISTRUZIONI,
                    "cache_control": {"type": "ephemeral"}}]
        conteggio = client.messages.count_tokens(
            model=modello, system=sistema, tools=strumenti_api, messages=messaggi)
        token_input = conteggio.input_tokens

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

        budget.registra(risposta.usage, problema.theorem)
        t.consumo.aggiungi(risposta.usage)

        if risposta.stop_reason == "refusal":
            t.motivo = "il modello ha rifiutato la richiesta"
            break

        # mostra il ragionamento e il testo
        for blocco in risposta.content:
            if blocco.type == "thinking" and getattr(blocco, "thinking", ""):
                stampa(f"     [ragionamento] {blocco.thinking.strip()[:400]}")
            elif blocco.type == "text" and blocco.text.strip():
                stampa(f"     {blocco.text.strip()[:600]}")

        chiamate = [b for b in risposta.content if b.type == "tool_use"]
        messaggi.append({"role": "assistant", "content": risposta.content})

        if not chiamate:
            t.motivo = "il modello ha smesso di usare gli strumenti senza una prova accettata"
            testo = " ".join(b.text for b in risposta.content if b.type == "text")
            t.trascrizione.append({"tipo": "fine", "testo": testo})
            break

        risultati = []
        accettata = False
        for chiamata in chiamate:
            if chiamata.name == "lean_check":
                t.verifiche += 1
                codice = chiamata.input.get("codice_lean", "")
                stampa(f"     -> lean_check ({len(codice)} caratteri)...")
                rapporto, ok = strumenti.esegui_lean_check(
                    problema.theorem, codice, timeout=timeout_lean)
                prima_riga = rapporto.split("\n")[0]
                stampa(f"        {prima_riga}")
                if ok:
                    accettata = True
                    t.soluzione = codice
                risultati.append({"type": "tool_result", "tool_use_id": chiamata.id,
                                  "content": rapporto})
            elif chiamata.name == "run_python":
                t.esecuzioni_python += 1
                codice = chiamata.input.get("codice", "")
                stampa(f"     -> run_python ({len(codice)} caratteri)...")
                uscita = strumenti.esegui_run_python(codice)
                stampa(f"        {uscita.strip()[:200]}")
                risultati.append({"type": "tool_result", "tool_use_id": chiamata.id,
                                  "content": uscita})
            else:
                risultati.append({"type": "tool_result", "tool_use_id": chiamata.id,
                                  "content": f"Strumento sconosciuto: {chiamata.name}",
                                  "is_error": True})

        messaggi.append({"role": "user", "content": risultati})

        if accettata:
            t.risolto = True
            t.motivo = "dimostrazione accettata dal verificatore"
            break
    else:
        t.motivo = f"esaurite le {max_iterazioni} iterazioni disponibili"

    t.secondi = time.time() - avvio
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
        print(f"     {t.iterazioni} iterazioni, {t.verifiche} verifiche Lean, "
              f"{t.esecuzioni_python} esecuzioni Python, {t.secondi:.0f}s, "
              f"${t.consumo.costo(args.modello):.4f}")

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
                "iterazioni": t.iterazioni, "verifiche": t.verifiche,
                "esecuzioni_python": t.esecuzioni_python, "secondi": t.secondi,
                "costo": t.consumo.costo(args.modello), "consumo": t.consumo.__dict__,
                "soluzione": t.soluzione,
            } for t in tentativi],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  Resoconto salvato in {args.rapporto}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
