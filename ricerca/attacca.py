"""
L'attacco vero: seme invariante sotto un gruppo, poi salita a gradini.

I TRE MOTORI, E PERCHÉ SERVONO TUTTI E TRE (misurato l'11-12 settembre 2026)
---------------------------------------------------------------------------
  * **orbite** — pareggia subito dove il record è invariante sotto un gruppo
    (A(19,6,5) = 76 in 0,8 s) e si blocca dove non lo è: su A(17,6,6) arriva a 85
    contro 113, perché 113 non è somma di taglie di orbite sotto Z17.
  * **ricerca locale da parole casuali** — 1 cella pareggiata su 34, residui di
    69–441 violazioni. Lo spazio è troppo grande per partire dal nulla.
  * **conflitti precalcolati** — la matrice dei conflitti si costruisce una volta, e
    una mossa costa una somma di N interi invece di N·m conteggi di bit. Da migliaia
    di mosse a centinaia di migliaia.

Questo script li mette in fila come li mette in fila la letteratura: **il gruppo dà
la struttura, la salita a gradini la estende una parola alla volta.** Ogni gradino
parte da un codice valido, quindi la riparazione deve sistemare poco.

Un successo passa dal giudice lento di `codici.py` e poi da `docs/04` per intero.
"""
from __future__ import annotations

import json
import os
import sys
import time
from math import comb
from multiprocessing import Pool
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "ricerca"))

from codici import verifica                                  # noqa: E402
from ibrido import estendi, miglior_invariante                # noqa: E402
from spingi import bersagli                                   # noqa: E402
from tabu import _tutte_le_parole                             # noqa: E402
from veloce import TETTO_MEMORIA_BYTE, sali                    # noqa: E402

DATI = RADICE / "dati_ricerca"


def una(argomenti) -> dict:
    n, d, w, voce, mosse, riavvii = argomenti
    t0 = time.time()
    esito = {"cella": f"A({n},{d},{w})", "pubblicato": voce["inferiore"],
             "superiore": voce["superiore"], "fonte": voce["fonte"],
             "candidate": comb(n, w)}
    N = comb(n, w)
    if N * ((N + 7) // 8) > TETTO_MEMORIA_BYTE:
        esito["saltata"] = f"matrice da {N * ((N + 7) // 8) / 1e9:.1f} GB"
        return esito
    try:
        seme, gruppo = miglior_invariante(n, d, w, riavvii=riavvii)
        tutte = _tutte_le_parole(n, w)
        seme = estendi(seme, tutte, d)
        esito.update({"invariante": len(seme), "gruppo": gruppo})
        r = sali(n, d, w, seme, voce["inferiore"] + 1,
                 mosse_per_gradino=mosse, seme=1, tentativi=3)
        esito.update({"raggiunto": r["dimensione"], "valido": r["valido"],
                      "gradini_riusciti": sum(1 for v in r["gradini"].values()
                                              if v == "riuscito")})
        if r["dimensione"] > voce["inferiore"] and r["valido"]:
            g = verifica(r["parole"], n, d, w)
            esito["giudice_lento"] = g.ok
            if g.ok:
                esito["parole"] = r["parole"]
    except MemoryError as e:
        esito["saltata"] = str(e)
    esito["secondi"] = round(time.time() - t0, 1)
    return esito


def main() -> int:
    mosse = int(sys.argv[1]) if len(sys.argv) > 1 else 150_000
    quanti = int(sys.argv[2]) if len(sys.argv) > 2 else 34
    massimo = int(sys.argv[3]) if len(sys.argv) > 3 else 120_000
    riavvii = int(sys.argv[4]) if len(sys.argv) > 4 else 250
    lista = bersagli(massimo, quanti)
    print(f"{len(lista)} celle con divario aperto. Seme invariante + salita a "
          f"gradini, {mosse:,} mosse per gradino.\n")
    lavori = [(n, d, w, v, mosse, riavvii) for _, n, d, w, v in lista]
    esiti = []
    with Pool(processes=min(6, os.cpu_count() or 1)) as piscina:
        for e in piscina.imap_unordered(una, lavori):
            esiti.append(e)
            if "saltata" in e:
                print(f"    saltata  {e['cella']:<13} {e['saltata']}")
            else:
                scarto = e["raggiunto"] - e["pubblicato"]
                marca = ("SUPERATO" if scarto > 0 else
                         "pareggiato" if scarto == 0 else f"{scarto:+d}")
                print(f"{marca:>11}  {e['cella']:<13} pubbl {e['pubblicato']:>5} "
                      f"invariante {e['invariante']:>5} ({e['gruppo']:<13}) "
                      f"-> {e['raggiunto']:>5}  "
                      f"+{e['gradini_riusciti']} gradini  {e['secondi']:>7.1f}s")
            sys.stdout.flush()
            (DATI / "fase3_attacco.json").write_text(json.dumps(esiti, indent=1))
    utili = [e for e in esiti if "saltata" not in e]
    vinti = [e for e in utili if e["raggiunto"] > e["pubblicato"]]
    pari = sum(1 for e in utili if e["raggiunto"] == e["pubblicato"])
    print(f"\n{'=' * 74}\n{len(utili)} celle tentate: "
          f"pareggiate {pari}, superate {len(vinti)}")
    for e in vinti:
        print(f"  {e['cella']}: {e['raggiunto']} invece di {e['pubblicato']}. "
              f"Giudice lento: {e.get('giudice_lento')}. APPLICARE docs/04.")
    if utili and not vinti:
        vicine = sorted(utili, key=lambda e: e["pubblicato"] - e["raggiunto"])[:6]
        print("Le celle piu' vicine:")
        for e in vicine:
            print(f"  {e['cella']}: {e['raggiunto']} contro {e['pubblicato']} "
                  f"({e['raggiunto'] - e['pubblicato']:+d}), "
                  f"invariante {e['invariante']} sotto {e['gruppo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
