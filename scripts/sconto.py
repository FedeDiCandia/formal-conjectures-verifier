"""
Lo sconto di trasferimento, misurato sul nostro giro invece che stimato.

Tutto il piano di spesa si appoggia a un numero che non si può leggere nei dati
di altri: **quanto vale il nostro sistema rispetto al loro**. Loro, con Fable 5.1
e un tetto di $2 per problema, risolvono il 22% delle congetture OEIS (MISURATO
sui loro `info.json`). Noi abbiamo formalizzazioni diverse, un ambiente più
povero e un agente più semplice. Il rapporto fra i due tassi è lo sconto.

Questo script lo calcola dal rapporto di un giro e riproietta la scala con il
numero vero al posto della mia stima.

**Va usato solo sui rapporti di giri su problemi APERTI.** Applicarlo al rapporto
della calibrazione non ha senso e da' un numero senza significato (3,54): quella
girava su problemi GIA' DIMOSTRATI nell'archivio, cioe' su una popolazione
completamente diversa da quella su cui e' misurato il 22% di Epoch.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent

#: MISURATO sul run `oeis-open-lite-fable51` di Epoch AI: la frazione di problemi
#: risolti entro un tetto di $2, e la spesa media per tentativo a quel tetto.
LORO_TASSO_A_2 = 0.22
LORO_SPESA_A_2 = 1.71


def clopper_pearson(k: int, n: int, conf: float = 0.90) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    a = 1 - conf
    def alta(p): return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(k, n+1))
    def bassa(p): return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(0, k+1))
    def bis(f, t):
        lo, hi = 0.0, 1.0
        for _ in range(80):
            m = (lo + hi) / 2
            if f(m) < t: lo = m
            else: hi = m
        return (lo + hi) / 2
    return (0.0 if k == 0 else bis(alta, a/2),
            1.0 if k == n else bis(lambda p: 1 - bassa(p), 1 - a/2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rapporto")
    ap.add_argument("--restanti", type=int, default=44,
                    help="quanti problemi restano nella famiglia dopo questo giro")
    ap.add_argument("--residuo", type=float, default=0.0,
                    help="budget residuo dopo questo giro")
    args = ap.parse_args()

    r = json.loads(Path(args.rapporto).read_text(encoding="utf-8"))
    t = r["tentativi"]
    risolti = [x for x in t if x["risolto"]]
    saltati = [x for x in t if x.get("causa", "").startswith("sistema: la dimostrazione")]
    veri = [x for x in t if x not in saltati]
    speso = r["speso"]

    print(f"modello {r['modello']}, effort {r['effort']}, tetto per problema "
          f"${r['budget'] / max(1, len(t)):.2f} nominale")
    print(f"\n{'problema':52} {'esito':12} {'iter':>5} {'ver':>4} {'costo':>8}  causa")
    for x in t:
        print(f"{x['problema'][:52]:52} "
              f"{'RISOLTO' if x['risolto'] else 'non risolto':12} "
              f"{x['iterazioni']:5} {x['verifiche']:4} {x['costo']:8.4f}  "
              f"{(x.get('causa') or '')[:44]}")

    n = len(veri)
    k = len(risolti)
    basso, alto = clopper_pearson(k, n)
    print(f"\nTENTATIVI VERI       {n}   (saltati: {len(saltati)})")
    print(f"RISOLTI              {k}")
    print(f"NOSTRO TASSO         {k/n:.1%}   intervallo 90%: {basso:.1%} – {alto:.1%}")
    print(f"LORO TASSO a $2      {LORO_TASSO_A_2:.0%}   (MISURATO sui loro dati)")
    sconto = (k/n) / LORO_TASSO_A_2 if n else 0
    print(f"SCONTO DI TRASFERIMENTO  {sconto:.2f}   (la mia stima era 0,50)")
    print(f"\nSPESA                ${speso:.4f}   media per tentativo "
          f"${speso/max(1,n):.4f}")
    print(f"loro spesa media a $2 ${LORO_SPESA_A_2:.2f}")
    if risolti:
        c = sorted(x["costo"] for x in risolti)
        print(f"costo dei successi:  mediana ${c[len(c)//2]:.4f}, "
              f"da ${c[0]:.4f} a ${c[-1]:.4f}")

    if args.restanti and args.residuo:
        media = speso / max(1, n)
        possibili = int(args.residuo / media)
        print(f"\nPROIEZIONE con i numeri veri:")
        print(f"  con ${args.residuo:.2f} residui e ${media:.3f} per tentativo: "
              f"{possibili} tentativi possibili")
        for etichetta, tasso in (("il nostro tasso misurato", k/n),
                                 ("il minimo dell'intervallo", basso),
                                 ("il massimo dell'intervallo", alto)):
            attesi = min(possibili, args.restanti) * tasso
            print(f"  {etichetta:28} {tasso:6.1%} -> {attesi:5.2f} successi attesi "
                  f"sui {min(possibili, args.restanti)} restanti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
