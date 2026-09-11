"""Riscrive i rapporti delle ricerche dai risultati gia' salvati.

Serve quando la regola per scrivere il rapporto cambia mentre una ricerca sta
girando: il processo in corso ha in memoria la versione vecchia del codice e
scrivera' il rapporto con quella. Questo script lo rifa' leggendo `esito.json`,
senza rieseguire niente.

Uso:  python3 scripts/rigenera_rapporti.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))
sys.path.insert(0, str(RADICE / "scripts"))

import caccia
from caccia_programmi import RICERCHE


@dataclass
class EsitoSalvato:
    """Gli stessi campi che `rapporto()` si aspetta, letti da `esito.json`."""
    conclusa: bool
    interrotta: bool
    secondi: float
    posizione: int
    esaminati: int
    trovati: list


def main() -> int:
    rifatti = 0
    for nome, definizione in RICERCHE.items():
        cartella = RADICE / "runs" / "caccia" / nome
        f = cartella / "esito.json"
        if not f.is_file():
            print(f"  {nome}: nessun esito salvato, salto")
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        esito = EsitoSalvato(
            conclusa=d.get("conclusa", False), interrotta=d.get("interrotta", False),
            secondi=d.get("secondi", 0.0), posizione=d.get("posizione", 0),
            esaminati=d.get("esaminati", 0), trovati=d.get("trovati") or [])
        (cartella / "rapporto.md").write_text(
            caccia.rapporto(nome, definizione, esito), encoding="utf-8")
        natura = definizione.get("natura_trovati", "da interpretare")
        print(f"  {nome}: rapporto riscritto "
              f"({len(esito.trovati)} voci, natura: {natura})")
        rifatti += 1
    print(f"\n{rifatti} rapporti riscritti.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
