"""
Proofs in natural language, and a severe reviewer who takes them apart.

WHY
---
Three rounds on open problems gave zero, and the measured reason is that the agent
**does not submit candidates**: it computes, sees where the difficulty lies, and
stops. But one question those rounds do not separate: is the bottleneck **Lean** or
the **mathematics**?

This experiment separates them. A proof in natural language is asked for, with no
Lean and no tools, and then a severe reviewer takes it to pieces. If something
survives, the bottleneck was Lean and formalisation is the next step. If nothing
survives, the bottleneck is the mathematics, and no budget moves it.

HOW
---
Two calls per problem, no tools:

  1. **author** — proves, or explains why it cannot be done, declaring explicitly its
     own confidence and the weak points of the argument;
  2. **reviewer** — reads without confidence, looks for the error, and gives a verdict
     among `HOLDS`, `GAP`, `WRONG`, `CIRCULAR`, `NOT RELEVANT`.

The reviewer does not see the problem as something "to approve": its job is to find
the point that does not work. It is the role in which models are most reliable, and
the literature on the subject says an adversarial reviewer finds errors the author
does not see.

No use of `lean_check`: nothing is verified here. What comes out is **material to
read**, not a result.
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
    """The problem, with ALL the definitions it needs.

    The statement alone is not enough: `a n` or `IsPrimitiveTerm n` cannot be proved
    without knowing how they are defined. The same text the agent receives is sent —
    the archive's file with the proofs hidden — which contains the definitions, the
    proof terms of the first values, and the source's comment.
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
            f"not enough budget: {count.input_tokens:,} input tokens, "
            f"room for the answer {available:,}")
    with client.messages.stream(
            model=model, max_tokens=available,
            system=[{"type": "text", "text": system}],
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": effort},
            messages=[{"role": "user", "content": text}]) as stream:
        answer = stream.get_final_message()
    budget.record(answer.usage, "informal")
    output_text = "\n".join(b.text for b in answer.content
                             if b.type == "text").strip()
    if not output_text:
        # MEASURED on 11 September 2026: at effort `high` on these problems the model
        # spent 32,000 reasoning tokens without writing a single line of answer, for
        # $0.81 of nothing, and the reviewer then reviewed a blank page. Paying and
        # receiving nothing is not an acceptable outcome: it stops here, with the exact
        # reason.
        raise SpendLimitExceeded(
            f"empty answer: stop_reason={answer.stop_reason}, "
            f"{answer.usage.output_tokens:,} output tokens of which "
            f"{getattr(answer.usage.output_tokens_details, 'thinking_tokens', '?')} "
            f"of reasoning. The max_tokens cap was {available:,}: "
            f"either more room or a lower effort is needed.")
    return output_text, answer.usage


def extract(block: str, key: str) -> str:
    for line in block.split("\n"):
        if line.strip().upper().startswith(key.upper()):
            return line.split(":", 1)[1].strip()[:200]
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("problems", nargs="+")
    ap.add_argument("--model", default="claude-opus-5")
    # MEASURED on 11 September 2026 on the same problem, with the same input:
    #   effort high,   cap 32k -> 32,000 tokens, ALL of them reasoning, zero lines
    #   effort medium, cap 24k -> 24,000 tokens, ALL of them reasoning, zero lines
    #   effort low,    cap 24k -> 20,402 tokens (16,353 of reasoning),
    #                               7,066 characters of real mathematics, end_turn
    # At effort high the model exhausts the room thinking and never concludes. At
    # effort low it concludes, and concludes well: on the first problem it showed that
    # the conjecture implies a case of Lehmer's totient problem, which is open, plus
    # five rigorous partial results. The default value is therefore `low`, and that is
    # not a saving: it is the only one that works.
    ap.add_argument("--effort", default="low")
    ap.add_argument("--budget", type=float, required=True)
    ap.add_argument("--problem-cap", type=float, default=1.20)
    ap.add_argument("--report", default=str(ROOT / "runs" / "informal.json"))
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    log_path = Path(args.log) if args.log else (
        ROOT / "runs" / "jobs" / f"informal-{time.strftime('%Y%m%d-%H%M%S')}.log")
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
    print("No tools, no Lean: mathematics in natural language only.\n")

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
            entry["weakest_step"] = extract(trial, "WEAKEST STEP")
            print(f"  author:   {entry['confidence'] or '(not declared)'}")
            print(f"            weakest step: {entry['weakest_step'][:100]}")

            # The reviewer exists to break a claimed proof. If the author declares it
            # has none, there is nothing to arbitrate and the second call is money
            # thrown away: on the problems in this set most outcomes are PARTIAL or
            # NO-PROOF, so this condition is the difference between twelve problems and
            # twenty.
            confidence = entry["confidence"].upper()
            if confidence.startswith(("PARTIAL", "NO-PROOF", "NO PROOF")):
                entry["review"] = None
                entry["verdict"] = "(not arbitrated: the author claims no proof)"
                entry["finding"] = ""
                print("  reviewer: skipped, the author claims no proof")
            else:
                review, _ = one_call(
                    client, args.model, REVIEWER, reviewer_message(p, trial),
                    budget, args.problem_cap - (budget.spent - spent_before),
                    args.effort)
                entry["review"] = review
                entry["verdict"] = extract(review, "VERDICT")
                entry["finding"] = extract(review, "THE PROBLEM")
                print(f"  reviewer: {entry['verdict'] or '(not declared)'}")
                print(f"            finding: {entry['finding'][:100]}")
        except SpendLimitExceeded as e:
            entry["error"] = str(e)
            print(f"  !! {e}")
            results.append(entry)
            break
        except anthropic.APIError as e:
            entry["error"] = f"API: {e}"
            print(f"  !! API error: {e}")
            results.append(entry)
            if "credit" in str(e).lower():
                print("  credit exhausted: stopping.")
                break
            continue
        entry["cost"] = round(budget.spent - spent_before, 4)
        print(f"  cost: ${entry['cost']:.4f}   (total ${budget.spent:.4f})")
        results.append(entry)
        # The report is written after EVERY problem, not at the end. Measured on 12
        # September 2026: a mistake of mine (`review` undefined when the reviewer is
        # skipped) killed the run after the first problem, and the first problem's text
        # — already paid for — was lost because the file was only written at the end. A
        # job that costs money has to save as it goes.
        Path(args.report).write_text(json.dumps(
            {"model": args.model, "effort": args.effort,
             "spent": budget.spent, "problem_cap": args.problem_cap,
             "in_progress": True, "results": results},
            ensure_ascii=False, indent=1), encoding="utf-8")

    survivors = [v for v in results if v.get("verdict", "").upper().startswith("HOLDS")]
    print(f"\n{'='*78}\nSUMMARY\n{'='*78}")
    for v in results:
        print(f"  {v['problem'][:46]:46} author {v.get('confidence','-')[:14]:14} "
              f"reviewer {v.get('verdict','-')[:12]:12} ${v.get('cost',0):.4f}")
    print(f"\n  survivors of the review: {len(survivors)} of {len(results)}")
    print(f"  total spend: ${budget.spent:.4f} of ${args.budget:.2f}")
    Path(args.report).write_text(json.dumps(
        {"model": args.model, "effort": args.effort, "spent": budget.spent,
         "problem_cap": args.problem_cap, "results": results},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  report in {args.report}")
    if survivors:
        print("\n  ATTENTION: what survives the review is NOT a result. It is")
        print("  material to read, and the next step is the protocol in")
        print("  docs/04-finding-protocol.md plus formalisation in Lean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
