"""
I due strumenti che l'agente puo' usare.

  * `lean_check`  — sottopone un file Lean al verificatore e riporta l'esito.
  * `run_python`  — esegue codice Python in un ambiente isolato (niente rete,
                    niente scritture fuori dalla sua cartella, con timeout).

Perche' `run_python`: cercare una dimostrazione spesso richiede di fare conti
(controllare un'ipotesi su piccoli casi, cercare un controesempio, calcolare una
costante). Farli "a mente" e' il modo piu' rapido per sbagliare.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import verify as verificatore   # noqa: E402


# ---------------------------------------------------------------------------
# Strumento 1: lean_check
# ---------------------------------------------------------------------------

SCHEMA_LEAN_CHECK = {
    "name": "lean_check",
    "description": (
        "Sottopone un file Lean 4 completo al verificatore ufficiale e riporta "
        "l'esito. Il file deve essere autosufficiente: import, namespace, "
        "eventuali definizioni ausiliarie e il teorema richiesto con una "
        "dimostrazione completa.\n\n"
        "Il verificatore accetta SOLO se: il file compila; non contiene sorry, "
        "admit, dichiarazioni axiom o native_decide; il tipo del teorema e' "
        "IDENTICO a quello dell'enunciato originale; le definizioni "
        "dell'archivio non sono state ridefinite; gli unici assiomi usati sono "
        "propext, Classical.choice e Quot.sound.\n\n"
        "Usalo tutte le volte che vuoi: e' l'unico giudice che conta. "
        "Una verifica richiede circa 30 secondi."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "codice_lean": {
                "type": "string",
                "description": "Il contenuto completo del file Lean da verificare.",
            }
        },
        "required": ["codice_lean"],
        "additionalProperties": False,
    },
}


def esegui_lean_check(problema: str, codice_lean: str, timeout: int | None = None) -> tuple[str, bool]:
    """Ritorna (rapporto testuale per il modello, accettato)."""
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, encoding="utf-8") as f:
        f.write(codice_lean)
        percorso = Path(f.name)
    try:
        r = verificatore.verify(problema, percorso, timeout=timeout)
    finally:
        percorso.unlink(missing_ok=True)

    righe = [f"ESITO: {r.status}"]
    for c in r.checks:
        righe.append(f"  [{'ok' if c.passed else 'FALLITO'}] {c.name}"
                     + (f" — {c.detail}" if c.detail and not c.passed else ""))
    if r.message:
        righe.append("")
        righe.append(r.message)
    if r.errors:
        righe.append("")
        righe.append("Messaggi di Lean / comparator:")
        righe.append(r.errors[:6000])
    return "\n".join(righe), r.accepted


# ---------------------------------------------------------------------------
# Strumento 2: run_python
# ---------------------------------------------------------------------------

SCHEMA_RUN_PYTHON = {
    "name": "run_python",
    "description": (
        "Esegue codice Python 3 in un ambiente isolato e restituisce quello che "
        "il codice stampa. Utile per fare conti, cercare controesempi, "
        "verificare un'ipotesi su casi piccoli.\n\n"
        "Limiti: nessun accesso alla rete; puoi scrivere file solo nella "
        "cartella di lavoro temporanea; la libreria standard e' disponibile ma "
        "non ci sono pacchetti esterni; ogni esecuzione riparte da zero (le "
        "variabili non sopravvivono tra una chiamata e l'altra); c'e' un tempo "
        "massimo. Stampa i risultati con print()."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "codice": {"type": "string", "description": "Il codice Python da eseguire."},
        },
        "required": ["codice"],
        "additionalProperties": False,
    },
}


#: Profilo della sandbox di macOS. `sandbox-exec` e' deprecato ma funzionante
#: ed e' l'unico isolamento a livello di kernel disponibile senza container.
_PROFILO_SANDBOX = """(version 1)
(allow default)

; --- niente rete: e' il requisito principale
(deny network*)

; --- niente scritture, tranne nella cartella di lavoro
(deny file-write*)
(allow file-write*
  (subpath "{lavoro}")
  (literal "/dev/null")
  (literal "/dev/urandom")
  (literal "/dev/random")
  (literal "/dev/dtracehelper"))

; --- niente lettura dei segreti
(deny file-read*
  (subpath "{home}/.ssh")
  (subpath "{home}/.aws")
  (subpath "{home}/.gnupg")
  (subpath "{home}/.config/anthropic")
  (subpath "{home}/.anthropic")
  (literal "{progetto}/.env"))
"""


def _interprete_python() -> str:
    """Il Python da usare dentro la sandbox.

    Usiamo l'interprete di base (non quello del venv) per non dare al codice
    generato l'accesso ai pacchetti del progetto, e per evitare il wrapper
    `xcrun` di /usr/bin/python3, che dentro la sandbox stampa errori spuri.
    """
    base = Path(sys.base_prefix) / "bin" / "python3"
    if base.is_file():
        return str(base)
    return shutil.which("python3") or sys.executable


def esegui_run_python(codice: str, timeout: int = 30, max_output: int = 20_000) -> str:
    if not shutil.which("sandbox-exec"):
        return ("ERRORE: `sandbox-exec` non e' disponibile su questo sistema, "
                "quindi non posso eseguire il codice in isolamento. "
                "Lo strumento run_python e' disattivato.")

    with tempfile.TemporaryDirectory(prefix="fcs_py_") as lavoro:
        lavoro_reale = str(Path(lavoro).resolve())
        script = Path(lavoro_reale) / "programma.py"
        script.write_text(codice, encoding="utf-8")
        profilo = Path(lavoro_reale) / "sandbox.sb"
        profilo.write_text(_PROFILO_SANDBOX.format(
            lavoro=lavoro_reale, home=str(Path.home()), progetto=str(ROOT)), encoding="utf-8")

        # Ambiente ridotto: soprattutto NIENTE chiave API.
        ambiente = {
            "PATH": "/usr/bin:/bin",
            "HOME": lavoro_reale,
            "TMPDIR": lavoro_reale,
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        try:
            p = subprocess.run(
                ["sandbox-exec", "-f", str(profilo), _interprete_python(), "-I", str(script)],
                cwd=lavoro_reale, env=ambiente, capture_output=True, text=True,
                timeout=timeout, start_new_session=True,
            )
        except subprocess.TimeoutExpired:
            return f"ERRORE: il codice ha superato il tempo massimo di {timeout} secondi ed e' stato interrotto."

        parti = []
        if p.stdout:
            parti.append(p.stdout)
        if p.stderr:
            parti.append("--- stderr ---\n" + p.stderr)
        if p.returncode != 0:
            parti.append(f"--- il programma e' terminato con codice {p.returncode} ---")
        risultato = "\n".join(parti) if parti else "(il codice non ha stampato nulla)"
        if len(risultato) > max_output:
            risultato = risultato[:max_output] + f"\n... [output troncato a {max_output} caratteri]"
        return risultato
