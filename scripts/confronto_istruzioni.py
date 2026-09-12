"""
Confronto fra varianti: modello, istruzioni, e quanto del tetto viene consumato.

LA DOMANDA
----------
Nel primo giro sui problemi aperti l'agente ha fallito dieci volte su dieci nello
stesso modo: si fermava a $0,23 di un tetto da $2, senza mai consegnare un
candidato a `lean_check`. Due spiegazioni possibili, e vanno separate:

  a) i problemi erano troppo difficili;
  b) l'agente si arrende troppo presto, perche' le istruzioni gliela offrono,
     quella via d'uscita.

Il modo di separarle e' rilanciare gli stessi problemi GIA' RISOLTI dell'archivio
con e senza l'invito ad arrendersi, e guardare non solo i successi ma **quanta
parte del tetto viene consumata** e **quanti candidati vengono consegnati**.
Quelle due misure dicono se l'agente ci prova; i successi dicono se ci riesce.

Il tetto di ciascun giro puo' essere diverso, quindi per confrontare si
RISIMULA lo stesso tetto su tutti: per ogni tentativo si prende
`min(costo, tetto)` e si conta come successo solo se il costo sta sotto il tetto.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path


def carica(percorso: str) -> dict:
    return json.loads(Path(percorso).read_text(encoding="utf-8"))


def misura(r: dict, tetto: float) -> dict:
    t = r["tentativi"]
    costi = [x["costo"] for x in t]
    entro = [x for x in t if x["risolto"] and x["costo"] <= tetto]
    spesa = [min(c, tetto) for c in costi]
    al_tetto = [c for c in costi if c >= 0.90 * tetto]
    verifiche = [x["verifiche"] for x in t]
    senza_verifiche = [x for x in t if x["verifiche"] == 0]
    return {
        "modello": r.get("modello", "?"),
        "istruzioni": r.get("istruzioni", "attuali"),
        "tentativi": len(t),
        "successi": len(entro),
        "tasso": len(entro) / len(t) if t else 0,
        "spesa_media": st.mean(spesa) if spesa else 0,
        "quota_tetto": (st.mean(spesa) / tetto) if spesa and tetto else 0,
        "arrivati_al_tetto": len(al_tetto),
        "verifiche_totali": sum(verifiche),
        "verifiche_medie": st.mean(verifiche) if verifiche else 0,
        "senza_nemmeno_una_verifica": len(senza_verifiche),
        "iterazioni_medie": st.mean(x["iterazioni"] for x in t) if t else 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rapporti", nargs="+", help="i rapporti JSON da confrontare")
    ap.add_argument("--tetto", type=float, required=True,
                    help="il tetto per problema da risimulare su tutti")
    ap.add_argument("--etichette", default="",
                    help="nomi separati da PUNTO E VIRGOLA (le etichette "
                         "contengono virgole), nello stesso ordine")
    args = ap.parse_args()

    etichette = args.etichette.split(";") if args.etichette else []
    righe = []
    for i, p in enumerate(args.rapporti):
        m = misura(carica(p), args.tetto)
        m["nome"] = (etichette[i].strip() if i < len(etichette)
                     else f"{m['modello']} / {m['istruzioni']}")
        righe.append(m)

    print(f"Tetto per problema risimulato su tutti: ${args.tetto:.2f}\n")
    intestazione = (f"{'variante':34} {'succ':>6} {'tasso':>7} {'spesa media':>12} "
                    f"{'% del tetto':>12} {'al tetto':>9} {'verifiche':>10} "
                    f"{'senza verifiche':>16}")
    print(intestazione)
    print("-" * len(intestazione))
    for m in righe:
        print(f"{m['nome'][:34]:34} {m['successi']:2}/{m['tentativi']:<3} "
              f"{m['tasso']:7.0%} {m['spesa_media']:11.4f}$ {m['quota_tetto']:11.0%} "
              f"{m['arrivati_al_tetto']:4}/{m['tentativi']:<4} "
              f"{m['verifiche_medie']:10.1f} {m['senza_nemmeno_una_verifica']:9}/{m['tentativi']:<5}")

    print("\nCome si legge:")
    print("  % del tetto      quanto dell'importo disponibile viene speso davvero.")
    print("                   Bassa = l'agente si arrende prima di finire i soldi.")
    print("  verifiche        candidati consegnati a lean_check, in media per problema.")
    print("                   Zero = non ha nemmeno provato a dimostrare.")
    print("  senza verifiche  su quanti problemi non ha consegnato NIENTE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
