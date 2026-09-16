"""
D(27,5,2) con λ = 1: esiste un pacchetto di 32 blocchi?

FORMULAZIONE INDIPENDENTE, SCRITTA DA ZERO
------------------------------------------
Questo file non importa niente dagli altri file di `ricerca/`. Esiste perché un
«infattibile» (o un «trovato») prodotto da un solo programma non vale: deve dirlo
anche un secondo programma, scritto separatamente, con un altro tipo di solutore.

Che cosa condivide con `pacchetto.py`: SOLO l'argomento della forma canonica per il
punto 0, dimostrato in docs/11-bersaglio-D27.md e validato su un pacchetto reale
di 31 blocchi. Tutto il resto è diverso:

  * i candidati si ricavano per FILTRO — tutti i 5-sottoinsiemi di {1,…,26} che non
    riusano una coppia dei sei blocchi fissati — invece che per costruzione; il
    conteggio deve tornare 15.104, e se non torna uno dei due programmi è sbagliato;
  * il solutore è SAT (CaDiCaL, tramite PySAT), non programmazione lineare intera;
  * il vincolo «almeno 26 blocchi» è un contatore sequenziale scritto a mano;
  * nessun blocco fissato oltre ai sei per il punto 0, nessun vincolo di conteggio;
  * il verificatore finale è scritto qui, da capo.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from itertools import combinations
from pathlib import Path

from pysat.card import CardEnc, EncType
from pysat.formula import CNF, IDPool
from pysat.solvers import Solver

RADICE = Path(__file__).resolve().parent.parent
SECONDI = float(sys.argv[1]) if len(sys.argv) > 1 else 14400.0

# la forma canonica, ricavata di nuovo: il punto 0 ha grado 6 e i suoi sei blocchi
# ripartiscono 24 dei 26 punti restanti; 25 e 26 restano fuori
FISSI = [tuple([0] + list(range(1 + 4 * i, 5 + 4 * i))) for i in range(6)]
USATE = {c for B in FISSI for c in combinations(B, 2)}

candidati = [S for S in combinations(range(1, 27), 5)
             if not any(c in USATE for c in combinations(S, 2))]
print(f"candidati per filtro: {len(candidati)} (l'altro programma ne costruisce 15104)",
      flush=True)

pool = IDPool()
x = [pool.id(("blocco", i)) for i in range(len(candidati))]
cnf = CNF()

per_coppia: dict[tuple[int, int], list[int]] = {}
per_punto: dict[int, list[int]] = {p: [] for p in range(1, 27)}
for i, S in enumerate(candidati):
    for c in combinations(S, 2):
        per_coppia.setdefault(c, []).append(x[i])
    for p in S:
        per_punto[p].append(x[i])

# ogni coppia in al massimo un blocco
for lits in per_coppia.values():
    if len(lits) > 1:
        cnf.extend(CardEnc.atmost(lits=lits, bound=1, vpool=pool,
                                  encoding=EncType.seqcounter).clauses)
# grado: un punto sta in al massimo 6 blocchi; 1..24 ne hanno gia' uno fisso
for p, lits in per_punto.items():
    cnf.extend(CardEnc.atmost(lits=lits, bound=5 if p <= 24 else 6, vpool=pool,
                              encoding=EncType.seqcounter).clauses)

# almeno K blocchi: contatore sequenziale scritto a mano.
# s[i][j] vero  =>  fra i primi i candidati almeno j sono scelti.
K = 26
n = len(x)
s = [[None] * (K + 1) for _ in range(n + 1)]
for i in range(1, n + 1):
    for j in range(1, min(i, K) + 1):
        s[i][j] = pool.id(("conta", i, j))
for i in range(1, n + 1):
    xi = x[i - 1]
    for j in range(1, min(i, K) + 1):
        prima = s[i - 1][j] if j <= i - 1 else None          # almeno j fra i primi i-1
        prima_meno = s[i - 1][j - 1] if j >= 2 else None      # almeno j-1 fra i primi i-1
        # s[i][j] -> prima OR x_i
        cnf.append([-s[i][j], xi] + ([prima] if prima else []))
        # s[i][j] -> prima OR (almeno j-1 fra i primi i-1)
        if j >= 2:
            cnf.append([-s[i][j]] + ([prima] if prima else []) + [prima_meno])
cnf.append([s[n][K]])

print(f"variabili {pool.top}, clausole {len(cnf.clauses)}", flush=True)


def verifica_da_capo(blocchi) -> tuple[bool, str]:
    viste = set()
    for B in blocchi:
        if len(set(B)) != 5 or not all(0 <= v < 27 for v in B):
            return False, f"blocco malformato {B}"
        for c in combinations(sorted(B), 2):
            if c in viste:
                return False, f"coppia {c} ripetuta"
            viste.add(c)
    return True, f"{len(blocchi)} blocchi, {len(viste)} coppie distinte"


esito = {"formulazione": "SAT indipendente", "candidati": len(candidati),
         "variabili": pool.top, "clausole": len(cnf.clauses)}
t0 = time.time()
for nome in ("cadical195", "cadical153", "glucose4"):
    try:
        solutore = Solver(name=nome, bootstrap_with=cnf.clauses)
        break
    except Exception as e:                                    # noqa: BLE001
        print(f"solutore {nome} non disponibile: {e}", flush=True)
esito["solutore"] = nome
print(f"solutore: {nome}. Limite {SECONDI:.0f} s.", flush=True)
timer = threading.Timer(SECONDI, solutore.interrupt)
timer.start()
risposta = solutore.solve_limited(expect_interrupt=True)
timer.cancel()
esito["secondi"] = round(time.time() - t0, 1)

if risposta is None:
    esito["stato"] = "NON CONCLUSO (limite di tempo)"
elif risposta is False:
    esito["stato"] = "UNSAT"
    esito["significato"] = ("nessun pacchetto di 32 in forma canonica; poiche' ogni "
                            "pacchetto di 32 si porta in forma canonica, D(27,5,2) <= 31. "
                            "NON ANNUNCIARE: docs/04 e confronto con l'ILP.")
else:
    modello = set(v for v in solutore.get_model() if v > 0)
    scelti = [candidati[i] for i in range(n) if x[i] in modello]
    blocchi = FISSI + scelti
    ok, dettaglio = verifica_da_capo(blocchi)
    esito.update({"stato": "SAT", "blocchi": blocchi, "verifica": ok,
                  "dettaglio": dettaglio,
                  "significato": "pacchetto di 32 trovato. NON ANNUNCIARE: docs/04."})
solutore.delete()
print(json.dumps({k: v for k, v in esito.items() if k != "blocchi"}, indent=1), flush=True)
(RADICE / "dati_ricerca" / "pacchetto27_sat.json").write_text(json.dumps(esito, indent=1))
