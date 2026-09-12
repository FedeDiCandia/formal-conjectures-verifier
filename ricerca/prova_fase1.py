"""
Fase 1 vera: la nostra ricerca, da zero, contro i limiti pubblicati.

Il passo zero (`riproduci.py`) ha mostrato che sappiamo leggere e verificare i
record. Qui si misura la cosa che conta: **partendo da niente, quanto ci
avviciniamo?** Per ogni cella si prova un repertorio di gruppi, si cerca la clique
pesata massima fra le orbite, e si confronta con la tabella.

Tre esiti: PAREGGIATO (uguale al limite pubblicato), SOTTO (di quanto), SOPRA
(record battuto — da trattare con il protocollo di docs/04, non da annunciare).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "ricerca"))

from cerca import cerca                    # noqa: E402
from codici import verifica                # noqa: E402
from gruppi import nome_gruppi             # noqa: E402

DATI = RADICE / "dati_ricerca"


def scegli(limiti: dict, *, massimo_parole: int, massimo_combinazioni: int,
           quante: int) -> list[tuple[str, dict]]:
    """Celle alla portata di un primo giro: piccole, e con un limite pubblicato."""
    candidate = []
    for k, v in limiti.items():
        n, d, w = (int(x) for x in k.split(","))
        if v["inferiore"] > massimo_parole or d % 2:
            continue
        from math import comb
        if comb(n, w) > massimo_combinazioni:
            continue
        candidate.append((k, v))
    candidate.sort(key=lambda kv: (-int(kv[1]["superiore"] is not None
                                       and kv[1]["superiore"] > kv[1]["inferiore"]),
                                   kv[1]["inferiore"]))
    return candidate[:quante]


def main() -> int:
    limiti = json.loads((DATI / "limiti_cwc.json").read_text())
    celle = scegli(limiti, massimo_parole=400, massimo_combinazioni=300_000,
                   quante=int(sys.argv[1]) if len(sys.argv) > 1 else 12)
    print(f"{len(celle)} celle nel primo giro.\n")
    print(f"{'cella':<14}{'pubbl.':>8}{'nostro':>8}{'esito':>12}  "
          f"{'gruppo':<14}{'fonte':<8}{'tempo':>7}")
    print("-" * 78)
    esiti = []
    conta = {"PAREGGIATO": 0, "SOTTO": 0, "SOPRA": 0}
    for k, v in celle:
        n, d, w = (int(x) for x in k.split(","))
        t0 = time.time()
        r = cerca(n, d, w, nome_gruppi(n), riavvii=60)
        mio = r["migliore"]["dimensione"]
        if mio > v["inferiore"]:
            stato = "SOPRA"
        elif mio == v["inferiore"]:
            stato = "PAREGGIATO"
        else:
            stato = "SOTTO"
        conta[stato] += 1
        dt = time.time() - t0
        print(f"A({n},{d},{w})".ljust(14)
              + f"{v['inferiore']:>8}{mio:>8}{stato:>12}  "
              + f"{str(r['migliore']['gruppo']):<14}{v['fonte']:<8}{dt:>6.1f}s")
        sys.stdout.flush()
        voce = {"cella": f"A({n},{d},{w})", "pubblicato": v["inferiore"],
                "nostro": mio, "stato": stato, "fonte": v["fonte"],
                "gruppo": r["migliore"]["gruppo"], "secondi": round(dt, 1),
                "per_gruppo": r["per_gruppo"]}
        if stato == "SOPRA":
            # il giudice lento, non quello rapido, e le parole per esteso
            g = verifica(r["migliore"]["parole"], n, d, w)
            voce["giudice_lento"] = g.ok
            voce["parole"] = r["migliore"]["parole"]
            print(f"    ATTENZIONE: sopra il limite pubblicato. "
                  f"Giudice lento: {'valido' if g.ok else g.difetti[:2]}. "
                  f"Applicare docs/04 prima di chiamarlo risultato.")
        esiti.append(voce)
    (DATI / "fase1_ricerca.json").write_text(json.dumps(esiti, indent=1))
    print("-" * 78)
    print("  ".join(f"{s}: {c}" for s, c in conta.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
