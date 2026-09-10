"""
Configurazione centrale del verificatore.

Qui stanno TUTTI i percorsi e i parametri regolabili. Ogni valore puo' essere
sovrascritto con una variabile d'ambiente, cosi' non serve modificare il codice.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Percorsi ---------------------------------------------------------------

#: Radice del progetto (la cartella che contiene verifier/, tests/, external/...)
ROOT = Path(__file__).resolve().parent.parent

def _path(env_var: str, default: Path) -> Path:
    return Path(os.environ.get(env_var, default)).resolve()

#: L'archivio dei problemi, gia' compilato con `lake build`.
ARCHIVE = _path("FCS_ARCHIVE", ROOT / "external" / "formal-conjectures")

#: Il binario di comparator, il "giudice" delle dimostrazioni.
COMPARATOR = _path("FCS_COMPARATOR", ROOT / "external" / "comparator" / ".lake" / "build" / "bin" / "comparator")

#: lean4export: esporta l'ambiente Lean in formato testo, perche' comparator
#: non si fidi degli .olean. DEVE essere compilato con la stessa versione di
#: Lean dell'archivio.
LEAN4EXPORT = _path("FCS_LEAN4EXPORT", ROOT / "external" / "lean4export-427" / ".lake" / "build" / "bin" / "lean4export")

#: Lo shim di landrun per macOS (su Linux si puo' puntare al vero landrun).
LANDRUN = _path("FCS_LANDRUN", ROOT / "tools" / "bin" / "landrun")

#: Cartella dei binari di elan/Lean.
ELAN_BIN = _path("FCS_ELAN_BIN", Path.home() / ".elan" / "bin")

#: Dove verify.py crea i moduli Lean temporanei da compilare.
#: Deve stare dentro l'albero dei sorgenti dell'archivio, perche' `lake` possa
#: trovarli: la libreria `FormalConjectures` copre il glob `FormalConjectures.+`.
SANDBOX_SUBDIR = "FormalConjectures/_Judge"

#: Il nome del modulo Lean corrispondente.
SANDBOX_MODULE_PREFIX = "FormalConjectures._Judge"

#: Dove viene salvato l'indice dei problemi (generato una volta sola).
INDEX_FILE = _path("FCS_INDEX", ROOT / "verifier" / "problem_index.json")


# --- Parametri di esecuzione ------------------------------------------------

#: Quanti processi Lean al massimo in parallelo.
MAX_PARALLEL = int(os.environ.get("FCS_MAX_PARALLEL", "4"))

#: Tempo massimo per una singola verifica, in secondi.
TIMEOUT_SECONDS = int(os.environ.get("FCS_TIMEOUT", "900"))

#: Gli unici assiomi ammessi. Sono i tre della logica di Lean/Mathlib:
#:   propext         - due proposizioni equivalenti sono uguali
#:   Classical.choice- assioma della scelta
#:   Quot.sound      - i quozienti si comportano bene
#: Qualunque altro assioma (compreso `sorryAx`, prodotto da `sorry`, e
#: `Lean.ofReduceBool`, prodotto da `native_decide`) fa fallire la verifica.
PERMITTED_AXIOMS = ["propext", "Classical.choice", "Quot.sound"]


def lean_env() -> dict:
    """Ambiente per i sottoprocessi Lean: elan e i binari del giudice nel PATH."""
    env = dict(os.environ)
    extra = f"{LANDRUN.parent}:{ELAN_BIN}"
    env["PATH"] = extra + ":" + env.get("PATH", "")
    env["COMPARATOR_LANDRUN"] = str(LANDRUN)
    env["COMPARATOR_LEAN4EXPORT"] = str(LEAN4EXPORT)
    # Fa fallire subito Lean su un panic interno invece di proseguire.
    env["LEAN_ABORT_ON_PANIC"] = "1"
    return env


def check_installation() -> list[str]:
    """Ritorna la lista dei problemi di installazione (vuota se tutto a posto)."""
    problems = []
    if not ARCHIVE.is_dir():
        problems.append(f"Archivio non trovato: {ARCHIVE}")
    elif not (ARCHIVE / ".lake" / "build" / "lib").is_dir():
        problems.append(f"Archivio non compilato (manca .lake/build): esegui `lake build` in {ARCHIVE}")
    for name, path in [("comparator", COMPARATOR), ("lean4export", LEAN4EXPORT), ("landrun", LANDRUN)]:
        if not path.is_file() or not os.access(path, os.X_OK):
            problems.append(f"{name} mancante o non eseguibile: {path}")
    if not (ELAN_BIN / "lake").is_file():
        problems.append(f"lake non trovato in {ELAN_BIN}")
    return problems
