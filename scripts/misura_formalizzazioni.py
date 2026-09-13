#!/usr/bin/env python3
"""
Legge il rapporto di un giro dell'agente sulle prove note e ne ricava i numeri
del punto 2 (misura) e del punto 3 (proiezione).

Ogni numero viene dal rapporto JSON scritto da agent/agente.py o dall'elenco dei
candidati di scripts/scegli_formalizzazioni.py: niente ricopiato a mano.

LIMITE DICHIARATO DI QUESTO GIRO: e' stato lanciato con `--silenzioso`, quindi
il registro non contiene i messaggi di errore di Lean. La diagnosi dei fallimenti
si fa sulla natura delle verifiche consegnate (non compila / compila con un buco /
enunciato diverso) e sul riassunto del ragionamento del modello, iterazione per
iterazione, che il rapporto conserva.

Uso:
  .venv/bin/python scripts/misura_formalizzazioni.py runs/formalizzazioni-lotto20.json
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATI = ROOT / "dati_ricerca" / "formalizzazioni_candidati.json"

#: segni, nel ragionamento del modello, di un ostacolo di API e non di matematica
_API = re.compile(r"unknown (identifier|constant)|not found|doesn't exist|does not exist|"
                  r"deprecated|renamed|failed to synthesize|instance|coercion|cast|"
                  r"Mathlib (lemma|name|API)|lemma name|exact\?|apply\?|simp lemma|"
                  r"typeclass|elaborat|universe|Decidable", re.I)
#: segni di un ostacolo matematico
_MATE = re.compile(r"(don't|do not|can't|cannot) (see|find) (a|the|how)|need(s)? a (proof|argument)|"
                   r"key (step|lemma|difficulty)|not (true|obvious)|counterexample|"
                   r"hard(er)? than|deep|requires? (a|the) (theorem|result)|"
                   r"false as stated|misformaliz", re.I)


def fascia(c: dict) -> str:
    m = set(c["motivi"])
    duro = m & {"fonte: articolo", "fonte: teorema profondo",
                "enunciato: infinito/analisi", "calcolo grande"}
    if "fonte: prova corta" in m and not duro:
        return "A"
    if c["categoria"] == "textbook" and not duro:
        return "B"
    if not duro:
        return "C"
    if duro == {"fonte: articolo"}:
        return "D"
    return "E"


DESCRIZIONE = {
    "A": "la fonte dice che la prova e' corta, niente di duro",
    "B": "textbook, niente di duro",
    "C": "research solved senza segnali",
    "D": "prova citata da un articolo",
    "E": "segnali duri (teorema profondo, infinito/analisi, calcolo grande)",
}


def ostacolo(t: dict) -> str:
    """Matematica, API di Mathlib, o indeterminato, dal ragionamento e dalle verifiche."""
    if t["risolto"]:
        return "-"
    testo = " ".join(it.get("ragionamento", "") for it in t["iterazioni_dettaglio"])
    api, mate = len(_API.findall(testo)), len(_MATE.findall(testo))
    nat = t.get("verifiche_per_natura") or {}
    if not t["verifiche"]:
        base = "nessun candidato consegnato"
    elif nat.get("buco_o_assioma") or nat.get("enunciato_sbagliato"):
        base = "ha compilato, la prova non c'era"
    else:
        base = "i candidati non compilavano"
    if api > 2 * max(mate, 1):
        verdetto = "API di Mathlib"
    elif mate > api:
        verdetto = "matematica"
    else:
        verdetto = "misto"
    return f"{verdetto} ({base}; segni API {api}, segni matematica {mate})"


def main() -> int:
    rapporto = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    candidati = json.loads(CANDIDATI.read_text(encoding="utf-8"))
    per_nome = {c["problema"]: c for c in candidati}
    tentativi = rapporto["tentativi"]

    print(f"modello {rapporto['modello']}, effort {rapporto['effort']}, istruzioni "
          f"{rapporto['istruzioni']}, tetto ${rapporto['tetto_problema']:.2f}, "
          f"budget ${rapporto['budget']:.2f}")
    print(f"spesa misurata: ${rapporto['speso']:.4f}\n")
    print(f"{'#':>2} {'fascia':6} {'esito':11} {'costo':>7} {'it':>3} {'ver':>3}  problema")
    for i, t in enumerate(tentativi, 1):
        f = fascia(per_nome[t["problema"]]) if t["problema"] in per_nome else "?"
        print(f"{i:2d} {f:6} {'ACCETTATO' if t['risolto'] else 'non chiuso':11} "
              f"${t['costo']:6.3f} {t['iterazioni']:3d} {t['verifiche']:3d}  {t['problema']}")
        if not t["risolto"]:
            print(f"{'':26}{t['motivo'][:90]}")
            print(f"{'':26}ostacolo: {ostacolo(t)}")

    risolti = [t for t in tentativi if t["risolto"]]
    spesa = sum(t["costo"] for t in tentativi)
    print(f"\nACCETTATI DAL VERIFICATORE: {len(risolti)} su {len(tentativi)} tentati")
    if risolti:
        print(f"costo per successo (spesa totale / successi): ${spesa / len(risolti):.3f}")
        print(f"costo medio di un successo, da solo: "
              f"${sum(t['costo'] for t in risolti) / len(risolti):.3f}")
    falliti = [t for t in tentativi if not t["risolto"]]
    if falliti:
        print(f"costo medio di un fallimento: ${sum(t['costo'] for t in falliti) / len(falliti):.3f}")

    # --- proiezione
    tasso: dict[str, tuple[int, int]] = {}
    for t in tentativi:
        if t["problema"] in per_nome:
            f = fascia(per_nome[t["problema"]])
            ok, n = tasso.get(f, (0, 0))
            tasso[f] = (ok + t["risolto"], n + 1)
    conta = collections.Counter(fascia(c) for c in candidati)
    print("\nPROIEZIONE PER FASCIA")
    for f in "ABCDE":
        ok, n = tasso.get(f, (0, 0))
        misurato = f"{ok}/{n} misurati" if n else "non misurata"
        print(f"  {f} {conta[f]:5d} candidati  {misurato:15s}  {DESCRIZIONE[f]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
