"""
Chi passa al giro successivo della scala, e perché.

La scala funziona solo se la promozione è un criterio meccanico, non un
giudizio. Il criterio, dichiarato:

  **Passa al giro successivo il problema su cui l'agente ha consegnato almeno un
  candidato che COMBACIA con l'enunciato e ha fallito sulla dimostrazione.**

In termini del rapporto dell'agente: fra le nature delle verifiche compare
`errore_tecnico` o `buco_o_assioma`. Significa che il modello ha capito che cosa
dimostrare, ha scritto un file che il verificatore ha accettato come «lo stesso
teorema», e si è fermato sulla prova. È progresso verificabile.

NON passa chi ha solo `esplorazione` (non è mai arrivato a consegnare) o
`enunciato_sbagliato` (non ha nemmeno riprodotto l'enunciato): là il problema non
è il budget.

Il criterio è lo stesso che `agent/agente.py` usa per classificare i fallimenti,
quindi non aggiunge nulla da mantenere.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent

#: Le nature che contano come progresso verificabile.
PROGRESSO = ("errore_tecnico", "buco_o_assioma")


def promossi(rapporto: dict) -> tuple[list, list]:
    """Ritorna (promossi, bocciati) con la ragione di ciascuno."""
    su, giu = [], []
    for t in rapporto.get("tentativi", []):
        if t.get("risolto"):
            continue                      # già risolto: non serve promuoverlo
        nature = t.get("verifiche_per_natura") or {}
        segni = {k: v for k, v in nature.items() if k in PROGRESSO}
        voce = {
            "problema": t["problema"],
            "costo": round(t.get("costo", 0), 4),
            "iterazioni": t.get("iterazioni", 0),
            "verifiche": t.get("verifiche", 0),
            "nature": nature,
            "motivo_di_arresto": t.get("motivo", "")[:120],
        }
        if segni:
            voce["perche"] = ("ha consegnato un candidato che combacia con "
                              f"l'enunciato e ha fallito sulla prova: {segni}")
            su.append(voce)
        else:
            voce["perche"] = ("nessun candidato consegnato che combaci con "
                              f"l'enunciato (nature viste: {nature or 'nessuna'})")
            giu.append(voce)
    return su, giu


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rapporto", help="il JSON prodotto da agent/agente.py --rapporto")
    ap.add_argument("--uscita", default="", help="dove scrivere l'elenco dei promossi")
    args = ap.parse_args()

    r = json.loads(Path(args.rapporto).read_text(encoding="utf-8"))
    su, giu = promossi(r)
    risolti = [t["problema"] for t in r.get("tentativi", []) if t.get("risolto")]

    print(f"tentativi     {len(r.get('tentativi', []))}")
    print(f"risolti       {len(risolti)}")
    for n in risolti:
        print(f"    RISOLTO   {n}")
    print(f"promossi      {len(su)}   (passano al giro con tetto più alto)")
    for v in su:
        print(f"    ->        {v['problema'][:58]:58} ${v['costo']:.3f} {v['nature']}")
    print(f"bocciati      {len(giu)}")
    for v in giu[:10]:
        print(f"    x         {v['problema'][:58]:58} ${v['costo']:.3f} {v['nature'] or '—'}")
    if len(giu) > 10:
        print(f"    ... e altri {len(giu)-10}")

    if args.uscita:
        Path(args.uscita).write_text(json.dumps(
            {"risolti": risolti, "promossi": su, "bocciati": giu},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nscritto in {args.uscita}")
        print("i nomi da passare all'agente per il giro successivo:")
        print("  " + " ".join(v["problema"] for v in su))
    return 0


if __name__ == "__main__":
    sys.exit(main())
