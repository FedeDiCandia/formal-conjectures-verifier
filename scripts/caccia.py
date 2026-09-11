"""
Esegue le ricerche di controesempi, in coda, con checkpoint e ripresa.

Non usa l'API e non costa niente: gira solo sul computer.
Ogni ricerca lascia in runs/caccia/<nome>/ il programma, il log, il checkpoint
e un rapporto leggibile.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
sys.path.insert(0, str(RADICE / "scripts"))

import ricerca as modulo_ricerca
from caccia_programmi import RICERCHE


def rapporto(nome: str, definizione: dict, esito) -> str:
    natura = definizione.get("natura_trovati", "da interpretare")
    righe = [
        f"# Ricerca: {nome}", "",
        f"**Problema:** `{definizione['problema']}`", "",
        f"**Cosa cerca:** {definizione['descrizione']}", "",
        f"**Stato noto del problema:** {definizione['stato_noto']}", "",
        f"**La ricerca è conclusiva?** {definizione['conclusivo']}", "",
        "## Esito", "",
        f"| | |", "|---|---|",
        f"| conclusa | {'sì' if esito.conclusa else 'no, interrotta'} |",
        f"| durata | {esito.secondi:.0f} s |",
        f"| posizione raggiunta | {esito.posizione} |",
        f"| casi esaminati | {esito.esaminati} |",
        f"| voci nella lista dei risultati | {len(esito.trovati)} |",
        f"| natura di quelle voci | {natura} |",
        "",
    ]
    if esito.trovati and natura == "controesempi":
        righe += ["## Ritrovamenti", "",
                  "⚠️ Da sottoporre al protocollo della fase 7 prima di crederci.", ""]
    elif esito.trovati:
        righe += [f"## Risultati ({natura})", "",
                  "**Non sono ritrovamenti.** Questa ricerca non puo' produrre un",
                  "controesempio: quello che segue e' materiale da leggere, non una",
                  "confutazione.", ""]
    if esito.trovati:
        for t in esito.trovati[:40]:
            righe.append(f"- `{json.dumps(t, ensure_ascii=False)}`")
        if len(esito.trovati) > 40:
            righe.append(f"- ... e altri {len(esito.trovati) - 40}")
    else:
        righe += ["## Ritrovamenti", "",
                  "Nessuno. **Non è un fallimento:** significa che fino al punto",
                  f"raggiunto ({esito.posizione}) non esistono controesempi, che è",
                  "un'informazione."]
    righe.append("")
    return "\n".join(righe)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", default="", help="esegui solo questa ricerca")
    ap.add_argument("--ore", type=float, default=0, help="tempo massimo per ricerca")
    ap.add_argument("--riprendi", action="store_true", default=True)
    ap.add_argument("--dacapo", action="store_true")
    ap.add_argument("--collaudo", action="store_true",
                    help="esecuzione breve, solo per controllare che i programmi funzionino")
    args = ap.parse_args()

    nomi = [args.solo] if args.solo else list(RICERCHE)
    secondi = args.ore * 3600 if args.ore else None
    if args.collaudo:
        secondi = 25

    print(f"Ricerche in coda: {len(nomi)}")
    print(f"Tempo massimo per ricerca: "
          f"{'illimitato' if secondi is None else f'{secondi:.0f}s'}")
    print("Costo in crediti API: ZERO\n", flush=True)

    riepilogo = []
    for nome in nomi:
        d = RICERCHE[nome]
        variabili = dict(d.get("variabili", {}))
        if args.collaudo:
            # valori piccoli: serve solo a vedere che il programma parta e salvi
            for k, v in list(variabili.items()):
                if isinstance(v, int) and v > 1000:
                    variabili[k] = 2000
        print(f"{'='*70}\n{nome}\n{'='*70}", flush=True)
        r = modulo_ricerca.Ricerca(nome, d["programma"],
                                   cartella=RADICE / "runs" / "caccia" / nome,
                                   variabili=variabili)
        esito = r.esegui(secondi_massimi=secondi, riprendi=not args.dacapo)
        (r.cartella / "rapporto.md").write_text(rapporto(nome, d, esito), encoding="utf-8")
        riepilogo.append({"nome": nome, "conclusa": esito.conclusa,
                          "posizione": esito.posizione, "esaminati": esito.esaminati,
                          "trovati": len(esito.trovati), "secondi": round(esito.secondi),
                          "natura_trovati": d.get("natura_trovati",
                                                  "da interpretare")})
        etichetta = ("ritrovamenti" if d.get("natura_trovati") == "controesempi"
                     else "risultati (non ritrovamenti)")
        print(f"  -> {'conclusa' if esito.conclusa else 'interrotta'}, "
              f"posizione {esito.posizione}, {etichetta} {len(esito.trovati)}",
              flush=True)

    dest = RADICE / "runs" / "caccia" / "riepilogo.json"
    dest.write_text(json.dumps(riepilogo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRiepilogo in {dest}")
    con_ritrovamenti = [r for r in riepilogo if r["trovati"]
                        and r.get("natura_trovati") == "controesempi"]
    if con_ritrovamenti:
        print("\n*** RITROVAMENTI DA ESAMINARE ***")
        for r in con_ritrovamenti:
            print(f"  {r['nome']}: {r['trovati']}  -> runs/caccia/{r['nome']}/rapporto.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
