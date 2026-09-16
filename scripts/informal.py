"""
Dimostrazioni in linguaggio naturale, e un revisore severo che le smonta.

PERCHÉ
------
Tre rounds sui problems open_ hanno dato zero, e la ragione misurata è che
l'agent **non consegna candidates**: compute, capisce dov'è la difficoltà, e si
ferma. Resta però one_ domanda aperta che quei rounds non separano: il collo di
bottiglia è **Lean** o è la **matematica**?

Questo esperimento la separa. Si chiede one_ dimostrazione in linguaggio naturale,
senza Lean e senza tools, e poi si fa a pieces da un revisore severo. Se
qualcosa sopravvive, il collo di bottiglia era Lean e la formalizzazione diventa
il step successivo. Se non sopravvive niente, il collo di bottiglia è la
matematica, e nessun budget lo sposta.

COME
----
Due calls per problem, nessuno strumento:

  1. **autore** — dimostra o confuta, in italiano o inglese, e dichiara
     esplicitamente la propria confidence e i points debolial del reasoning;
  2. **revisore** — legge senza confidence, search_for l'error, e dà un verdict fra
     `REGGE`, `LACUNA`, `SBAGLIATO`, `CIRCOLARE`, `NON PERTINENTE`.

Il revisore non vede il problem come «da approvare»: il suo compito è trovare il
punto che non torna. È il ruolo in cui i modelli sono più affidabili, e la
letteratura sul tema dice che un revisore adversariale trova errors che l'autore
non vede.

Nessun uso di `lean_check`: qui non si check niente. Quello che exits da qui è
**materiale da leggere**, non un result_value.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "agent"))

import anthropic   # noqa: E402
import config as verifier_config   # noqa: E402
from agent import load_env          # noqa: E402
from costs import Budget, SpendLimitExceeded   # noqa: E402
from index import ProblemIndex         # noqa: E402

AUTHOR = """You are a research mathematician. You will be given one open problem, \
stated in Lean 4 and in English.

Your task: **trials it or disprove it, in natural language.** No Lean, no code, no \
tools — just mathematics, written the way you would write it for a colleague who \
will check every step.

Rules that matter:

- If you see a proof, give it in full. Do not sketch: a sketch cannot be checked.
- If you see a counterexample, give the object explicitly and verify the required \
properties by hand.
- If you can only trials a special case or a weaker statement, do that and say \
exactly what you proved and what you did not.
- **Never** present a heuristic, a plausibility argument, or a numerical check as \
a proof. Saying "this is what I could not do" is worth more than a gap dressed up \
as an argument.

End your answer with exactly this block, filled in:

    CONFIDENCE: <one of: PROOF / PROOF-WITH-GAP / PARTIAL / NO-PROOF>
    WEAKEST STEP: <the step most likely to be wrong, in one sentence>
    WHAT WOULD FALSIFY IT: <what a reader should check first>

Be honest in that block. It is the part that will be read first."""

REVIEWER = """You are a referee for a mathematics journal, and you are known for \
rejecting papers that other referees accept.

You will be given an open problem and a claimed proof or disproof. **Your job is \
to find what is wrong with it**, not to judge whether it is interesting. Assume \
the author is competent and still wrong: the interesting errors are the ones that \
look right.

Check, in this order:

1. **Does it trials the stated theorem?** Compare the Lean statement with what the \
author actually proved: a quantifier moved, a hypothesis added, a special case \
silently assumed — these are the usual failures.
2. **Is any step circular?** Does it use the conjecture, or a known-equivalent \
form of it, to trials itself?
3. **Is any step a heuristic in disguise?** "For large n this behaves like…", \
"the probability that…", "one expects…" are not steps.
4. **Is every existence claim constructive or justified?** "There must exist…" \
without a reason is a gap.
5. **Are the computations right?** Recompute the small cases yourself.

Then give exactly this block:

    VERDICT: <one of: HOLDS / GAP / WRONG / CIRCULAR / IRRELEVANT>
    THE PROBLEM: <if not HOLDS, the single most serious defect, precisely located>
    SALVAGEABLE: <what part, if any, is a genuine result>

`HOLDS` means: you tried to break it and could not. Use it sparingly — and if you \
do use it, name the step you attacked hardest."""


def author_message(p, index) -> str:
    """Il problem, con TUTTE le definizioni che gli servono.

    Il only_ statement non basta: `a n` o `IsPrimitiveTerm n` non si possono
    dimostrare se non si sa come sono definiti. Si manda lo stesso text che
    riceve l'agent — il file dell'archive con le dimostrazioni nascoste — che
    contiene le definizioni, i termini di trial dei primes valori, e il commento
    della source_.
    """
    from hide import file_without_proofs
    text = file_without_proofs(p, index)
    return (f"# The problem\n\n"
            f"**Name in the archive:** `{p.theorem}`\n\n"
            f"**Statement, as elaborated by Lean:**\n\n```\n{p.statement}\n```\n\n"
            f"**Statement in English, from the archive:**\n\n{p.docstring or '(none)'}\n\n"
            f"**The whole archive file, with every proof replaced by `sorry`** — the "
            f"definitions you need are in here, and so are the verified values of "
            f"the first few terms:\n\n```lean\n{text[:8000]}\n```\n\n"
            f"The archive marks this problem as open. Prove it or disprove it.")


def reviewer_message(p, trial: str) -> str:
    return (f"# The problem\n\n**Lean statement:**\n\n```\n{p.statement}\n```\n\n"
            f"**In English:** {p.docstring or '(none)'}\n\n"
            f"# The claimed proof\n\n{trial}\n\n"
            f"Now referee it.")


def one_call(client, model, system, text, budget, cap, effort,
                 max_tokens=16_000):
    count = client.messages.count_tokens(
        model=model, system=[{"type": "text", "text": system}],
        messages=[{"role": "user", "content": text}])
    available = budget.affordable_max_tokens(count.input_tokens, max_tokens,
                                                residue=cap)
    if available < 2_000:
        raise SpendLimitExceeded(
            f"budget insufficiente: {count.input_tokens:,} token in ingresso, "
            f"spazio per la answer {available:,}")
    with client.messages.stream(
            model=model, max_tokens=available,
            system=[{"type": "text", "text": system}],
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": effort},
            messages=[{"role": "user", "content": text}]) as stream:
        answer = stream.get_final_message()
    budget.record(answer.usage, "informale")
    output_text = "\n".join(b.text for b in answer.content
                             if b.type == "text").strip()
    if not output_text:
        # MISURATO l'11 settembre 2026: con effort `high` su questi problems il
        # model ha spent 32.000 token di reasoning senza scrivere one_ line
        # di answer, per $0,81 di niente, e il revisore ha poi recensito one_
        # pagina bianca. Pagare e non ricevere nulla non e' un result ammissibile:
        # qui si ferma, con il reason exact.
        raise SpendLimitExceeded(
            f"answer vuota: stop_reason={answer.stop_reason}, "
            f"{answer.usage.output_tokens:,} token in output di cui "
            f"{getattr(answer.usage.output_tokens_details, 'thinking_tokens', '?')} "
            f"di reasoning. Il cap di max_tokens era {available:,}: "
            f"serve piu' spazio oppure un effort piu' low.")
    return output_text, answer.usage


def extract(block: str, key_: str) -> str:
    for line in block.split("\n"):
        if line.strip().upper().startswith(key_.upper()):
            return line.split(":", 1)[1].strip()[:200]
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("problems", nargs="+")
    ap.add_argument("--model", default="claude-opus-5")
    # MISURATO l'11 settembre 2026 sullo stesso problem, con lo stesso ingresso:
    #   effort high,   cap 32k -> 32.000 token, TUTTI di reasoning, zero lines
    #   effort medium, cap 24k -> 24.000 token, TUTTI di reasoning, zero lines
    #   effort low,    cap 24k -> 20.402 token (16.353 di reasoning),
    #                               7.066 chars di matematica vera, end_turn
    # A effort high il model esaurisce lo spazio pensando e non conclude. A
    # effort low conclude, e conclude bene: sul prime_ problem ha dimostrato che
    # la congettura implica un caso del problem del totiente di Lehmer, che e'
    # aperto, piu' cinque results parziali rigorosi. Il value_ predefinito e'
    # quindi `low`, e non e' un risparmio: e' l'unico che funziona.
    ap.add_argument("--effort", default="low")
    ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--cap-problem", type=float, default=1.20)
    ap.add_argument("--report", default=str(ROOT / "runs" / "informale.json"))
    ap.add_argument("--log_", default=None)
    args = ap.parse_args()

    log_path = Path(args.log_) if args.log_ else (
        ROOT / "runs" / "jobs" / f"informale-{time.strftime('%Y%m%d-%H%M%S')}.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    import agent
    sys.stdout = agent._Doppio(sys.stdout, log_path)
    print(f"Registro: {log_path}")

    load_env()
    client = anthropic.Anthropic()
    idx = ProblemIndex.load()
    budget = Budget(dollar_limit=args.budget, model=args.model)
    print(f"Modello {args.model}, effort {args.effort}, budget ${args.budget:.2f}, "
          f"cap ${args.problem_cap:.2f} per problem")
    print("Nessuno strumento, nessun Lean: only_ matematica in linguaggio naturale.\n")

    results = []
    for i, name in enumerate(args.problems, 1):
        p = idx.get(name)
        print(f"\n{'='*78}\n[{i}/{len(args.problems)}] {name}\n{'='*78}")
        spent_before = budget.spent
        entry = {"problem": name, "statement": p.statement[:300]}
        try:
            trial, _ = one_call(client, args.model, AUTHOR,
                                    author_message(p, idx), budget,
                                    args.problem_cap * 0.7, args.effort)
            entry["trial"] = trial
            entry["confidence"] = extract(trial, "CONFIDENCE")
            entry["punto_debole"] = extract(trial, "WEAKEST STEP")
            print(f"  autore:   {entry['confidence'] or '(non dichiarata)'}")
            print(f"            punto debole: {entry['punto_debole'][:100]}")

            # Il revisore esiste per rompere one_ dimostrazione rivendicata. Se
            # l'autore dichiara di non averne one_, non c'e' niente da arbitrare e
            # la seconda call e' denaro buttato: sui problems di questo
            # insieme la maggioranza degli results e' PARTIAL o NO-PROOF, quindi
            # questa condizione e' la differenza fra dodici problems e venti.
            confidence = entry["confidence"].upper()
            if confidence.startswith(("PARTIAL", "NO-PROOF", "NO PROOF")):
                entry["review"] = None
                entry["verdict"] = "(non arbitrato: l'autore non rivendica one_ trial)"
                entry["finding"] = ""
                print("  revisore: salta, l'autore non rivendica one_ trial")
            else:
                review, _ = one_call(
                    client, args.model, REVIEWER, reviewer_message(p, trial),
                    budget, args.problem_cap - (budget.spent - spent_before),
                    args.effort)
                entry["review"] = review
                entry["verdict"] = extract(review, "VERDICT")
                entry["finding"] = extract(review, "THE PROBLEM")
                print(f"  revisore: {entry['verdict'] or '(non dichiarato)'}")
                print(f"            finding: {entry['finding'][:100]}")
        except SpendLimitExceeded as e:
            entry["error"] = str(e)
            print(f"  !! {e}")
            results.append(entry)
            break
        except anthropic.APIError as e:
            entry["error"] = f"API: {e}"
            print(f"  !! error dall'API: {e}")
            results.append(entry)
            if "credit" in str(e).lower():
                print("  credito exhausted: mi fermo.")
                break
            continue
        entry["cost"] = round(budget.spent - spent_before, 4)
        print(f"  cost: ${entry['cost']:.4f}   (total ${budget.spent:.4f})")
        results.append(entry)
        # Il report si scrive a OGNI problem, non alla end. Misurato il 12
        # settembre 2026: un error mio (`review` non definita quando il
        # revisore viene saltato) ha fatto morire il giro after il prime_ problem, e
        # il text del prime_ -- gia' pagato -- e' andato perso perche' il file
        # veniva scritto only_ in fondo. Un job che paga deve salvare mentre va.
        Path(args.report).write_text(json.dumps(
            {"model": args.model, "effort": args.effort,
             "spent": budget.spent, "problem_cap": args.problem_cap,
             "in_corso": True, "results": results},
            ensure_ascii=False, indent=1), encoding="utf-8")

    survivors = [v for v in results if v.get("verdict", "").upper().startswith("HOLDS")]
    print(f"\n{'='*78}\nRESOCONTO\n{'='*78}")
    for v in results:
        print(f"  {v['problem'][:46]:46} autore {v.get('confidence','-')[:14]:14} "
              f"revisore {v.get('verdict','-')[:12]:12} ${v.get('cost',0):.4f}")
    print(f"\n  survivors alla revisione: {len(survivors)} su {len(results)}")
    print(f"  spesa total: ${budget.spent:.4f} su ${args.budget:.2f}")
    Path(args.report).write_text(json.dumps(
        {"model": args.model, "effort": args.effort, "spent": budget.spent,
         "problem_cap": args.problem_cap, "results": results},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  report in {args.report}")
    if survivors:
        print("\n  ATTENZIONE: quello che sopravvive alla revisione NON e' un")
        print("  result_value. E' materiale da leggere, e il step successivo e' il")
        print("  protocollo di docs/04 piu' la formalizzazione in Lean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
