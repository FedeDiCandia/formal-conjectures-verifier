"""
Stima quanto costerebbe far lavorare l'agente su certi problemi.

Non chiama l'API e non spende niente: usa il conteggio dei token, che e'
gratuito, e i dati MISURATI nelle esecuzioni precedenti.

Ogni numero prodotto dice da dove viene:
  MISURATO  osservato in un'esecuzione vera
  CONTATO   calcolato esattamente (token, prezzi di listino)
  STIMATO   dedotto dai due precedenti, con il ragionamento a fianco
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
sys.path.insert(0, str(RADICE / "agent"))

import costi
from index import ProblemIndex

#: MISURATO sull'unico problema portato a termine nel test da 5 dollari
#: (ComplexityTheory.P_subset_coNP, 9 chiamate, effort high).
#: Vedi runs/misurazioni.md e runs/test_5_dollari_interrotto.log
MISURA = {
    "costo_medio_chiamata": 0.2015,
    "costo_mediano_chiamata": 0.0796,
    "costo_massimo_chiamata": 0.7090,
    "secondi_per_iterazione": 74,
    "chiamate_osservate": 9,
    "problemi_osservati": 1,
}


def stima(problemi: list[str], budget: float, effort: str, max_iterazioni: int,
          modello: str) -> None:
    p = costi.prezzi(modello)
    n = max(1, len(problemi))
    tetto = budget / n

    print("STIMA — nessuna chiamata all'API, nessuna spesa")
    print("=" * 70)
    print(f"  modello        {modello}   (input ${p.input}/Mtok, output ${p.output}/Mtok)")
    print(f"  effort         {effort}")
    print(f"  problemi       {n}")
    print(f"  budget totale  ${budget:.2f}   (tetto per problema ${tetto:.2f})")
    print()

    print("DA COSA PARTO (MISURATO)")
    print("-" * 70)
    print(f"  Una sola esecuzione vera, su un solo problema, con effort high:")
    print(f"    {MISURA['chiamate_osservate']} chiamate")
    print(f"    costo medio per chiamata     ${MISURA['costo_medio_chiamata']:.4f}")
    print(f"    costo mediano per chiamata   ${MISURA['costo_mediano_chiamata']:.4f}")
    print(f"    costo massimo per chiamata   ${MISURA['costo_massimo_chiamata']:.4f}")
    print(f"    tempo medio per iterazione   {MISURA['secondi_per_iterazione']} s")
    print()
    print("  ATTENZIONE: un solo problema osservato. Questi numeri servono a")
    print("  farsi un'idea, non a fare previsioni precise. La distribuzione era")
    print("  molto storta: due chiamate su nove valevano il 60% della spesa.")
    print()

    fattore = {"low": 0.35, "medium": 0.6, "high": 1.0, "xhigh": 1.8, "max": 3.0}[effort]
    if effort != "high":
        print(f"  Correzione per effort '{effort}': x{fattore} (STIMATO, non misurato:")
        print(f"  l'unica esecuzione vera era con effort high)")
        print()

    print("QUANTO POTREBBE COSTARE (STIMATO)")
    print("-" * 70)
    medio = MISURA["costo_medio_chiamata"] * fattore
    mediano = MISURA["costo_mediano_chiamata"] * fattore
    for etichetta, per_chiamata, iterazioni in [
        ("ottimistico (poche iterazioni, chiamate corte)", mediano, 5),
        ("realistico  (come l'unica esecuzione osservata)", medio, 9),
        ("pessimistico (arriva al tetto di spesa)", medio, max_iterazioni),
    ]:
        totale = min(per_chiamata * iterazioni, tetto) * n
        minuti = iterazioni * MISURA["secondi_per_iterazione"] * n / 60
        print(f"  {etichetta}")
        print(f"      ${totale:.2f} in tutto, circa {minuti:.0f} minuti")
    print()
    print(f"  LIMITE RIGIDO: ${budget:.2f}. Non puo' essere superato: prima di")
    print(f"  ogni chiamata si calcola il costo massimo possibile e, se non ci")
    print(f"  sta nel residuo, la chiamata non parte.")
    print()

    if problemi:
        print("I PROBLEMI SCELTI")
        print("-" * 70)
        try:
            idx = ProblemIndex.load()
        except FileNotFoundError:
            print("  (indice non costruito: non posso descriverli)")
            return
        for nome in problemi:
            try:
                pr = idx.get(nome)
            except KeyError as e:
                print(f"  ! {nome}: {str(e)[:80]}")
                continue
            stato = ("risolto nell'archivio con prova pulita"
                     if pr.archive_proof_is_clean else
                     "risolto nell'archivio ma con assiomi non ammessi"
                     if pr.proof_is_sorry_free else "APERTO")
            print(f"  {nome}")
            print(f"      {pr.category} | {stato} | enunciato {len(pr.statement)} caratteri")


def main() -> int:
    ap = argparse.ArgumentParser(description="Stima il costo di un'esecuzione dell'agente.")
    ap.add_argument("--problemi", default="", help="nomi separati da spazi")
    ap.add_argument("--budget", type=float, default=5.0)
    ap.add_argument("--effort", default="high",
                    choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--max-iterazioni", type=int, default=30)
    ap.add_argument("--modello", default="claude-opus-5")
    args, _ignoti = ap.parse_known_args()
    stima([x for x in args.problemi.split() if x], args.budget, args.effort,
          args.max_iterazioni, args.modello)
    return 0


if __name__ == "__main__":
    sys.exit(main())
