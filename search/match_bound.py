"""
Fase 1: la nostra ricerca contro i limiti pubblicati.

Tre domande, in ordine, e la terza conta solo se le prime due sono a posto.

  1. **Il motore trova gli ottimi noti?** Sulle celle dove A(n,d,w) e' un valore
     esatto, dobbiamo raggiungerlo. Se non ci arriviamo, il motore e' debole e
     qualunque risultato sopra e' rumore.
  2. **Il motore NON supera gli ottimi noti?** Se dice di aver trovato piu' del
     valore esatto, e' un difetto nostro. E' la prova di falsificazione: senza
     questa, un «record» non significa niente.
  3. **Pareggia i limiti pubblicati aperti?** Questa e' la soglia di ammissione
     alla fase 3: chi non pareggia non supera.
"""
from __future__ import annotations

import json
import sys
import time
from math import comb
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "search"))

from codes import verifica, verifica_veloce   # noqa: E402
from tabu import _tutte_le_parole, prova_dimensione   # noqa: E402

DATI = RADICE / "research_data"


def main() -> int:
    limiti = json.loads((DATI / "limiti_cwc.json").read_text())
    tetto_parole = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    tetto_comb = int(sys.argv[2]) if len(sys.argv) > 2 else 80_000
    iterazioni = int(sys.argv[3]) if len(sys.argv) > 3 else 3_000

    esatte, aperte = [], []
    for k, v in limiti.items():
        n, d, w = (int(x) for x in k.split(","))
        if d % 2 or v["inferiore"] > tetto_parole or comb(n, w) > tetto_comb:
            continue
        (esatte if v["esatto"] else aperte).append((k, v))
    esatte.sort(key=lambda kv: kv[1]["inferiore"])
    aperte.sort(key=lambda kv: kv[1]["inferiore"])
    print(f"{len(esatte)} celle con valore esatto noto (collaudo), "
          f"{len(aperte)} celle aperte (bersagli).\n")

    esiti = []

    print("=" * 74)
    print("1 e 2. COLLAUDO: raggiungere l'ottimo noto, e NON superarlo")
    print("=" * 74)
    r1 = r2 = 0
    for k, v in esatte:
        n, d, w = (int(x) for x in k.split(","))
        tutte = _tutte_le_parole(n, w)
        t0 = time.time()
        a, va = prova_dimensione(n, d, w, v["inferiore"], iterazioni=iterazioni,
                                 seme=11, parole=tutte)
        b, vb = prova_dimensione(n, d, w, v["inferiore"] + 1,
                                 iterazioni=iterazioni, seme=11, parole=tutte)
        raggiunto = va == 0 and verifica_veloce(a, n, d, w).ok
        sfondato = vb == 0
        r1 += raggiunto
        r2 += not sfondato
        nota = ""
        if sfondato:
            g = verifica(b, n, d, w)
            nota = ("  DIFETTO NOSTRO: ha superato un valore esatto"
                    if g.ok else "  (il giudice lento lo rifiuta: ok)")
            if g.ok:
                nota = "  ALLARME: il giudice lento lo accetta. Da capire."
        print(f"  A({n},{d},{w}):  ottimo {v['inferiore']:>3}  "
              f"raggiunto {'si' if raggiunto else 'NO':<3}  "
              f"superato {'SI' if sfondato else 'no':<3}  "
              f"{time.time() - t0:>5.1f}s{nota}")
        sys.stdout.flush()
        esiti.append({"cella": f"A({n},{d},{w})", "tipo": "esatto",
                      "valore": v["inferiore"], "raggiunto": raggiunto,
                      "superato": sfondato})
    print(f"\n  raggiunti {r1}/{len(esatte)}   non superati {r2}/{len(esatte)}")

    print("\n" + "=" * 74)
    print("3. BERSAGLI: pareggiare il limite inferiore pubblicato")
    print("=" * 74)
    pari = sopra = sotto = 0
    for k, v in aperte:
        n, d, w = (int(x) for x in k.split(","))
        tutte = _tutte_le_parole(n, w)
        t0 = time.time()
        a, va = prova_dimensione(n, d, w, v["inferiore"], iterazioni=iterazioni,
                                 seme=11, parole=tutte)
        if va != 0:
            stato, extra = "SOTTO", ""
            sotto += 1
        else:
            b, vb = prova_dimensione(n, d, w, v["inferiore"] + 1,
                                     iterazioni=iterazioni, seme=11, parole=tutte)
            if vb == 0 and verifica(b, n, d, w).ok:
                stato, extra = "SOPRA", f"  +1 sul limite ({v['inferiore'] + 1})"
                sopra += 1
            else:
                stato, extra = "PAREGGIATO", ""
                pari += 1
        print(f"  A({n},{d},{w}):  pubblicato {v['inferiore']:>3} "
              f"(sup {v['superiore']})  {stato:<11} {time.time() - t0:>5.1f}s"
              f"  fonte {v['fonte']}{extra}")
        sys.stdout.flush()
        voce = {"cella": f"A({n},{d},{w})", "tipo": "aperto",
                "pubblicato": v["inferiore"], "superiore": v["superiore"],
                "stato": stato, "fonte": v["fonte"]}
        if stato == "SOPRA":
            voce["parole"] = sorted(b)
            print("      Da trattare con docs/04: verificare che la tabella sia "
                  "aggiornata prima di chiamarlo record.")
        esiti.append(voce)
    print(f"\n  pareggiati {pari}   sopra {sopra}   sotto {sotto}")
    (DATI / "fase1_pareggio.json").write_text(json.dumps(esiti, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
