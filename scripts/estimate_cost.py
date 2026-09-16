"""
Stima quanto costerebbe far lavorare l'agent su certi problems.

It does not call the API and spends nothing: it uses the token count, which is
free, plus the data MEASURED in earlier runs.

Every number produced says where it comes from:
  MEASURED   observed in a real run
  CONTATO   calcolato esattamente (token, prices di listino)
  ESTIMATED  inferred from the two above, with the reasoning beside it
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "agent"))

import costs
from index import ProblemIndex

#: MEASURED on the only problem carried to completion in the $5 test
#: (ComplexityTheory.P_subset_coNP, 9 calls, effort high).
#: See docs/data/measurements.md e runs/test_5_dollari_interrotto.log
MEASURE = {
    "mean_cost_per_call": 0.2015,
    "median_cost_per_call": 0.0796,
    "max_cost_per_call": 0.7090,
    "seconds_per_iteration": 74,
    "calls_observed": 9,
    "problems_observed": 1,
}


def estimate(problems: list[str], budget: float, effort: str, max_iterations: int,
          model: str) -> None:
    p = costs.prices(model)
    n = max(1, len(problems))
    cap = budget / n

    print("ESTIMATE — no API call, no spend")
    print("=" * 70)
    print(f"  model        {model}   (input ${p.input}/Mtok, output ${p.output}/Mtok)")
    print(f"  effort         {effort}")
    print(f"  problems       {n}")
    print(f"  total budget  ${budget:.2f}   (cap per problem ${cap:.2f})")
    print()

    print("WHAT THIS STARTS FROM (MEASURED)")
    print("-" * 70)
    print("  A single real run, on one problem, at effort high:")
    print(f"    {MEASURE['calls_observed']} calls")
    print(f"    mean cost per call     ${MEASURE['mean_cost_per_call']:.4f}")
    print(f"    median cost per call   ${MEASURE['median_cost_per_call']:.4f}")
    print(f"    max cost per call      ${MEASURE['max_cost_per_call']:.4f}")
    print(f"    mean time per iteration    {MEASURE['seconds_per_iteration']} s")
    print()
    print("  ATTENTION: only one problem observed. These numbers are there to")
    print("  give a sense of scale, not to make precise predictions. The")
    print("  distribution was very skewed: two calls of nine were 60% of the spend.")
    print()

    factor = {"low": 0.35, "medium": 0.6, "high": 1.0, "xhigh": 1.8, "max": 3.0}[effort]
    if effort != "high":
        print(f"  Correction for effort '{effort}': x{factor} (ESTIMATED, not measured:")
        print("  the only real run was at effort high)")
        print()

    print("QUANTO POTREBBE COSTARE (STIMATO)")
    print("-" * 70)
    mean = MEASURE["mean_cost_per_call"] * factor
    median = MEASURE["median_cost_per_call"] * factor
    for label, per_call, iterations in [
        ("ottimistico (poche iterations, calls corte)", median, 5),
        ("realistic   (as in the one run observed)", mean, 9),
        ("pessimistico (arriva al cap di spesa)", mean, max_iterations),
    ]:
        total = min(per_call * iterations, cap) * n
        minutes = iterations * MEASURE["seconds_per_iteration"] * n / 60
        print(f"  {label}")
        print(f"      ${total:.2f} in all, about {minutes:.0f} minutes")
    print()
    print(f"  HARD LIMIT: ${budget:.2f}. It cannot be exceeded: before every")
    print("  call the maximum possible cost is computed and, if it does not")
    print("  fit in what is left, the call does not start.")
    print()

    if problems:
        print("I PROBLEMI SCELTI")
        print("-" * 70)
        try:
            idx = ProblemIndex.load()
        except FileNotFoundError:
            print("  (index not built: they cannot be described)")
            return
        for name in problems:
            try:
                pr = idx.get(name)
            except KeyError as e:
                print(f"  ! {name}: {str(e)[:80]}")
                continue
            state = ("solved in the archive with a clean proof"
                     if pr.archive_proof_is_clean else
                     "solved in the archive but with axioms that are not permitted"
                     if pr.proof_is_sorry_free else "APERTO")
            print(f"  {name}")
            print(f"      {pr.category} | {state} | statement {len(pr.statement)} chars")


def main() -> int:
    ap = argparse.ArgumentParser(description="Estimate the cost of an agent run.")
    ap.add_argument("--problems", default="", help="names separati da spazi")
    ap.add_argument("--budget", type=float, default=5.0)
    ap.add_argument("--effort", default="high",
                    choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--max-iterations", type=int, default=30)
    ap.add_argument("--model", default="claude-opus-5")
    args, _ignoti = ap.parse_known_args()
    estimate([x for x in args.problems.split() if x], args.budget, args.effort,
          args.max_iterations, args.model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
