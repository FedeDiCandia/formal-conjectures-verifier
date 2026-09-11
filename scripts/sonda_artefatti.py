"""
Cerca le formalizzazioni che cedono per un difetto, non per matematica.

DA DOVE VIENE QUESTA IDEA
-------------------------
Leggendo le soluzioni ACCETTATE del benchmark OEIS Open di Epoch AI si vede che
il loro 30% di successi non è tutto matematica. Tre esempi reali, dai loro file:

  * `A211420_general_divisibility_conjecture` dimostrato con
    `exact ⟨0, fun n => by simp⟩`: l'enunciato diceva «esiste C tale che per
    ogni n ... divide C * a(n)», e con C = 0 è vero per niente. La congettura
    matematica non è quella.
  * `A262403_conjecture_ii_distinctness` confutato perché π(T 0) = π(T 1) = 0:
    l'iniettività cade su due casi al bordo.
  * `A070823_conjecture` confutato con un controesempio piccolo (n = 20),
    trovato calcolando e verificato con `decide`.

Le prime due sono **formalizzazioni sbagliate**, da segnalare agli autori
dell'archivio e non da spacciare per risultati; la terza è un controesempio
vero. Tutte e tre si trovano con tattiche a costo zero, senza API.

PERCHÉ UN SOLO FILE PER PROBLEMA
--------------------------------
Ogni compilazione paga ~6 secondi di import di Mathlib. Provare venti tattiche
in venti file costa venti volte quell'attesa; metterle nello stesso file la paga
una volta sola. Le dichiarazioni in Lean sono indipendenti: se una non si chiude
l'errore riguarda lei, e le altre proseguono. Si risale da ogni messaggio alla
tattica che l'ha prodotto tramite la riga.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
sys.path.insert(0, str(RADICE / "scripts"))

import config as config_verificatore   # noqa: E402
import esplora                          # noqa: E402
from index import ProblemIndex          # noqa: E402

#: (nome, tattica, anche_sulla_negazione). L'ordine non conta piu': si compila
#: tutto insieme.
TATTICHE = [
    ("testimone_zero",   "exact ⟨0, by simp⟩",            False),
    ("testimone_zero_d", "exact ⟨0, by decide⟩",          False),
    ("testimone_vuoto",  "exact ⟨∅, by simp⟩",            False),
    ("simp",             "simp",                          True),
    ("simp_arith",       "simp_arith",                    True),
    ("decide",           "decide",                        True),
    ("norm_num",         "norm_num",                      True),
    ("omega",            "omega",                         True),
    ("aesop",            "aesop",                         True),
    ("trivial",          "trivial",                       True),
    ("plausible",        "plausible",                     True),
]


def costruisci(problema, heartbeats: int) -> tuple[str, dict[int, tuple[str, bool]]]:
    """Il file con tutte le prove, e la mappa riga -> (tattica, negato)."""
    righe = [f"import {config_verificatore.modulo_utilita()}",
             f"import {problema.module}", ""]
    mappa: dict[int, tuple[str, bool]] = {}
    tipo = f"type_of% {problema.theorem}"
    for nome, tattica, anche_negato in TATTICHE:
        for negato in (False, True) if anche_negato else (False,):
            enunciato = f"¬ ({tipo})" if negato else tipo
            righe.append(f"set_option maxHeartbeats {heartbeats} in")
            righe.append(f"theorem sonda_{nome}{'_neg' if negato else ''} : "
                         f"{enunciato} := by")
            mappa[len(righe)] = (nome, negato)     # riga 1-based della tattica
            righe.append(f"  {tattica}")
            righe.append("")
    return "\n".join(righe) + "\n", mappa


_RE_MESSAGGIO = re.compile(r"^[^:]*:(\d+):\d+:\s*(warning|error|info):\s*(.*)$")


def leggi(uscita: str, mappa: dict[int, tuple[str, bool]]) -> dict:
    """Assegna a ogni tattica il suo esito, guardando le righe dei messaggi.

    Una tattica senza messaggi ha CHIUSO l'enunciato. `plausible`, quando non
    trova controesempi, lascia un `sorry`: il file compila ma non dimostra
    niente, e quel caso va contato come fallito — è l'errore opposto a quello
    da evitare in un progetto come questo.
    """
    fallite: dict[tuple[str, bool], str] = {}
    controesempi: dict[tuple[str, bool], str] = {}
    righe_tattiche = sorted(mappa)
    for riga in uscita.split("\n"):
        m = _RE_MESSAGGIO.match(riga.strip())
        if not m:
            continue
        n, tipo, testo = int(m.group(1)), m.group(2), m.group(3)
        # la dichiarazione a cui appartiene: l'ultima iniziata prima di n
        precedenti = [r for r in righe_tattiche if r <= n + 1]
        if not precedenti:
            continue
        chiave = mappa[precedenti[-1]]
        if tipo == "error" or "uses 'sorry'" in testo or "Unable to find" in testo:
            fallite.setdefault(chiave, testo[:200])
        if "Found a counter-example" in testo or "counterexample" in testo.lower():
            controesempi[chiave] = testo[:300]
    esiti = []
    for riga in righe_tattiche:
        nome, negato = mappa[riga]
        chiave = (nome, negato)
        if chiave in controesempi:
            esito = "controesempio"
        elif chiave in fallite:
            esito = "aperta"
        else:
            esito = "confutata" if negato else "chiusa"
        esiti.append({"tattica": nome, "negato": negato, "esito": esito,
                      "dettaglio": controesempi.get(chiave) or fallite.get(chiave, "")[:120]})
    return {"prove": esiti}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bersagli", default=str(RADICE / "docs/dati/bersagli.json"))
    ap.add_argument("--quanti", type=int, default=0, help="0 = tutti")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--heartbeats", type=int, default=200000)
    ap.add_argument("--uscita", default=str(RADICE / "runs/caccia/artefatti.json"))
    args = ap.parse_args()

    idx = ProblemIndex.load()
    dati = json.loads(Path(args.bersagli).read_text(encoding="utf-8"))
    scelti = []
    for c in dati["candidati"]:
        try:
            scelti.append(idx.get(c["problema"]))
        except Exception:
            continue

    uscita = Path(args.uscita)
    uscita.parent.mkdir(parents=True, exist_ok=True)
    risultati = json.loads(uscita.read_text(encoding="utf-8")) if uscita.is_file() else []
    visti = {v["problema"] for v in risultati}
    scelti = [p for p in scelti if p.theorem not in visti]
    if args.quanti:
        scelti = scelti[:args.quanti]

    print(f"Sondo {len(scelti)} enunciati, {len(TATTICHE)} tattiche in UN file ciascuno.")
    print(f"Gia' fatti: {len(visti)}. Nessuna spesa API.\n", flush=True)

    notevoli = 0
    for i, p in enumerate(scelti, 1):
        t0 = time.time()
        codice, mappa = costruisci(p, args.heartbeats)
        r = esplora.esplora(codice, timeout=args.timeout)
        voce = {"problema": p.theorem, "modulo": p.module,
                "enunciato": p.statement[:300], "secondi": round(time.time() - t0, 1)}
        if r.rifiutato_dal_guard:
            voce["errore"] = f"guard: {r.rifiutato_dal_guard}"
        else:
            voce.update(leggi(r.messaggi, mappa))
            notevole = [x for x in voce["prove"]
                        if x["esito"] in ("chiusa", "confutata", "controesempio")]
            if notevole:
                voce["ATTENZIONE"] = "; ".join(
                    f"{x['tattica']}{' (negata)' if x['negato'] else ''} -> {x['esito']}"
                    for x in notevole)
                notevoli += 1
                print(f"  !!! {p.theorem}: {voce['ATTENZIONE']}", flush=True)
        risultati.append(voce)
        uscita.write_text(json.dumps(risultati, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"[{i}/{len(scelti)}] {p.theorem[:54]:54} "
              f"{'NOTEVOLE' if 'ATTENZIONE' in voce else '.':9} {voce['secondi']:6.0f}s",
              flush=True)

    print(f"\n{'='*70}\nEsaminati {len(scelti)}. Notevoli: {notevoli}\nRisultati in {uscita}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
