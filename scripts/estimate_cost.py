"""
Stima quanto costerebbe far lavorare l'agent su certi problems.

Non chiama l'API e non spende niente: usa il count dei token, che e'
gratuito, e i data MISURATI nelle esecuzioni precedenti.

Ogni number prodotto dice da dove viene:
  MISURATO  osservato in un'esecuzione vera
  CONTATO   calcolato esattamente (token, prices di listino)
  STIMATO   inferred dai two precedenti, con il reasoning a fianco
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

#: MISURATO sull'unico problem portato a termine nel test da 5 dollari
#: (ComplexityTheory.P_subset_coNP, 9 calls, effort high).
#: Vedi docs/data/measurements.md e runs/test_5_dollari_interrotto.log
MEASURE = {
    "costo_medio_chiamata": 0.2015,
    "costo_mediano_chiamata": 0.0796,
    "costo_massimo_chiamata": 0.7090,
    "secondi_per_iterazione": 74,
    "chiamate_osservate": 9,
    "problemi_osservati": 1,
}


def estimate(problems: list[str], budget: float, effort: str, max_iterations: int,
          model: str) -> None:
    p = costs.prices(model)
    n = max(1, len(problems))
    cap = budget / n

    print("STIMA — nessuna call all'API, nessuna spesa")
    print("=" * 70)
    print(f"  model        {model}   (input ${p.input}/Mtok, output ${p.output}/Mtok)")
    print(f"  effort         {effort}")
    print(f"  problems       {n}")
    print(f"  budget total  ${budget:.2f}   (cap per problem ${cap:.2f})")
    print()

    print("DA COSA PARTO (MISURATO)")
    print("-" * 70)
    print(f"  Una sola esecuzione vera, su un only problem, con effort high:")
    print(f"    {MEASURE['chiamate_osservate']} calls")
    print(f"    cost mean per call     ${MEASURE['costo_medio_chiamata']:.4f}")
    print(f"    cost median per call   ${MEASURE['costo_mediano_chiamata']:.4f}")
    print(f"    cost maximum per call   ${MEASURE['costo_massimo_chiamata']:.4f}")
    print(f"    tempo mean per iteration   {MEASURE['secondi_per_iterazione']} s")
    print()
    print("  ATTENZIONE: un only problem osservato. Questi numbers servono a")
    print("  farsi un'idea, non a fare previsioni precise. La distribuzione era")
    print("  molto storta: two calls su nove valevano il 60% della spesa.")
    print()

    factor = {"low": 0.35, "medium": 0.6, "high": 1.0, "xhigh": 1.8, "max": 3.0}[effort]
    if effort != "high":
        print(f"  Correzione per effort '{effort}': x{factor} (STIMATO, non misurato:")
        print(f"  l'unica esecuzione vera era con effort high)")
        print()

    print("QUANTO POTREBBE COSTARE (STIMATO)")
    print("-" * 70)
    mean = MEASURE["costo_medio_chiamata"] * factor
    median = MEASURE["costo_mediano_chiamata"] * factor
    for label, per_call, iterations in [
        ("ottimistico (poche iterations, calls corte)", median, 5),
        ("realistico  (come l'unica esecuzione osservata)", mean, 9),
        ("pessimistico (arriva al cap di spesa)", mean, max_iterations),
    ]:
        total = min(per_call * iterations, cap) * n
        minuti = iterations * MEASURE["secondi_per_iterazione"] * n / 60
        print(f"  {label}")
        print(f"      ${total:.2f} in tutto, circa {minuti:.0f} minuti")
    print()
    print(f"  LIMIT RIGIDO: ${budget:.2f}. Non puo' essere exceeded: before di")
    print(f"  ogni call si compute il cost maximum possibile e, se non ci")
    print(f"  sta nel residue, la call non parte.")
    print()

    if problems:
        print("I PROBLEMI SCELTI")
        print("-" * 70)
        try:
            idx = ProblemIndex.load()
        except FileNotFoundError:
            print("  (index non built: non posso descriverli)")
            return
        for name in problems:
            try:
                pr = idx.get(name)
            except KeyError as e:
                print(f"  ! {name}: {str(e)[:80]}")
                continue
            state = ("solved nell'archive con trial pulita"
                     if pr.archive_proof_is_clean else
                     "solved nell'archive ma con axioms non permitted"
                     if pr.proof_is_sorry_free else "APERTO")
            print(f"  {name}")
            print(f"      {pr.category} | {state} | statement {len(pr.statement)} chars")


def main() -> int:
    ap = argparse.ArgumentParser(description="Stima il cost di un'esecuzione dell'agent.")
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
