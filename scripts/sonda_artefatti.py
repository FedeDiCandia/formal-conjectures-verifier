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
    ("simp_arith",       "simp +arith",                   True),
    ("decide",           "decide",                        True),
    ("norm_num",         "norm_num",                      True),
    ("omega",            "omega",                         True),
    ("aesop",            "aesop",                         True),
    ("trivial",          "trivial",                       True),
    ("plausible",        "plausible",                     True),
]


def costruisci(problema, heartbeats: int) -> tuple[str, dict[str, tuple[str, bool]]]:
    """Il file con tutte le prove, e la mappa nome del teorema -> (tattica, negato).

    Dopo ogni prova il file chiede a Lean **gli assiomi** di quella prova. È il
    criterio decisivo, ed è lo stesso del verificatore: una tattica ha chiuso
    davvero l'enunciato solo se la dichiarazione che ne risulta NON dipende da
    `sorryAx`. Contare i messaggi di errore non basta — una tattica che falliva
    produceva a volte un errore attribuito a un'altra riga, e la prova sembrava
    riuscita. Con `#print axioms` la risposta arriva per nome, non per posizione.
    """
    righe = [f"import {config_verificatore.modulo_utilita()}",
             f"import {problema.module}", ""]
    mappa: dict[str, tuple[str, bool]] = {}
    tipo = f"type_of% {problema.theorem}"
    for nome, tattica, anche_negato in TATTICHE:
        for negato in (False, True) if anche_negato else (False,):
            enunciato = f"¬ ({tipo})" if negato else tipo
            teorema = f"sonda_{nome}{'_neg' if negato else ''}"
            mappa[teorema] = (nome, negato)
            righe.append(f"set_option maxHeartbeats {heartbeats} in")
            righe.append(f"theorem {teorema} : {enunciato} := by")
            righe.append(f"  {tattica}")
            righe.append(f"#print axioms {teorema}")
            righe.append("")
    return "\n".join(righe) + "\n", mappa


#: `#print axioms nome` stampa una riga di questa forma.
_RE_ASSIOMI = re.compile(r"'(\S+)' depends on axioms: \[([^\]]*)\]")
_RE_SENZA = re.compile(r"'(\S+)' does not depend on any axioms")
_RE_CONTROESEMPIO = re.compile(r"Found a counter-example", re.I)


def leggi(uscita: str, mappa: dict[str, tuple[str, bool]]) -> dict:
    """Assegna a ogni tattica il suo esito leggendo gli assiomi, per nome.

    Regola: una tattica ha CHIUSO l'enunciato se la dichiarazione corrispondente
    esiste e non dipende da `sorryAx`. Se dipende da `sorryAx` la tattica non ha
    dimostrato niente — è il caso di `plausible`, che quando non trova
    controesempi lascia un `sorry` e fa compilare il file comunque. Se la
    dichiarazione non compare fra gli assiomi stampati, la prova è fallita prima
    di arrivare a esistere.
    """
    assiomi: dict[str, set[str]] = {}
    for riga in uscita.split("\n"):
        m = _RE_ASSIOMI.search(riga)
        if m:
            assiomi[m.group(1)] = {a.strip() for a in m.group(2).split(",") if a.strip()}
            continue
        m = _RE_SENZA.search(riga)
        if m:
            assiomi[m.group(1)] = set()
    controesempio = bool(_RE_CONTROESEMPIO.search(uscita))

    esiti = []
    for teorema, (nome, negato) in mappa.items():
        ax = assiomi.get(teorema)
        if ax is None:
            esito, dettaglio = "aperta", "la dichiarazione non esiste: la tattica ha fallito"
        elif "sorryAx" in ax:
            esito, dettaglio = "aperta", "dipende da sorryAx: non ha dimostrato niente"
        else:
            esito = "confutata" if negato else "chiusa"
            dettaglio = "assiomi: " + (", ".join(sorted(ax)) or "nessuno")
        esiti.append({"tattica": nome, "negato": negato, "esito": esito,
                      "dettaglio": dettaglio})
    if controesempio:
        esiti.append({"tattica": "plausible", "negato": None,
                      "esito": "controesempio",
                      "dettaglio": "plausible ha esibito un controesempio: "
                                   "vedi i messaggi grezzi"})
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
                voce["messaggi_grezzi"] = r.messaggi[:4000]
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
