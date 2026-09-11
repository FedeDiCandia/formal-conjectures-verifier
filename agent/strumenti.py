"""
I due strumenti che l'agente puo' usare.

  * `lean_explore` — compila un file Lean di prova e restituisce TUTTI i
                     messaggi. Serve a ispezionare: `#print`, `#check`,
                     `exact?`, errori completi. Non e' un giudizio.
  * `lean_check`   — sottopone un file Lean al verificatore e riporta l'esito.
                     E' l'unico giudizio che conta.
  * `run_python`   — esegue codice Python in un ambiente isolato (niente rete,
                     niente scritture fuori dalla sua cartella, con timeout).

Perche' `lean_explore` esiste separato: nel primo collaudo l'agente ha usato
NOVE verifiche su nove per ispezionare l'API di Mathlib, non per consegnare una
dimostrazione. Usare il giudice per quello costa 33 secondi invece di 8 e
restituisce un verdetto ("rifiutato: il teorema non c'e'") che non e'
l'informazione cercata.

Perche' `run_python`: cercare una dimostrazione spesso richiede di fare conti
(controllare un'ipotesi su piccoli casi, cercare un controesempio, calcolare una
costante). Farli "a mente" e' il modo piu' rapido per sbagliare.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import esplora as esploratore   # noqa: E402
import verify as verificatore   # noqa: E402


# ---------------------------------------------------------------------------
# Strumento 0: lean_explore
# ---------------------------------------------------------------------------

SCHEMA_LEAN_EXPLORE = {
    "name": "lean_explore",
    "description": (
        "Compila un file Lean 4 di prova e restituisce TUTTI i messaggi di Lean, "
        "non troncati. Serve a ISPEZIONARE, non a consegnare una dimostrazione: "
        "non e' un giudizio e non conta come tentativo.\n\n"
        "Funziona tutto quello che stampa qualcosa:\n"
        "  #print NomeDefinizione     - il corpo di una definizione o i campi di "
        "una struttura\n"
        "  #check @nomeLemma          - il tipo, con tutti gli argomenti impliciti\n"
        "  example ... := by exact?   - cerca un lemma che chiuda l'obiettivo\n"
        "  example ... := by apply?   - idem, per applicazione\n"
        "  #reduce e                  - riduce un termine (attenzione ai tempi)\n"
        "e gli errori arrivano completi, con lo stato degli obiettivi.\n\n"
        "A differenza di lean_check, qui PUOI importare il modulo del problema "
        "(per esempio `import FormalConjectures.Wikipedia.Selfridge`) e ispezionare "
        "le sue definizioni.\n\n"
        "Circa 8-10 secondi, contro i 30 di lean_check. Usa questo per capire, "
        "quello per consegnare."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "codice_lean": {
                "type": "string",
                "description": "Il file Lean di prova. Non serve che contenga il "
                               "teorema del problema.",
            }
        },
        "required": ["codice_lean"],
        "additionalProperties": False,
    },
}


def esegui_lean_explore(codice_lean: str, timeout: int = 240, slot: int = 0) -> str:
    r = esploratore.esplora(codice_lean, timeout=timeout, slot=slot)
    return r.render()


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
        "Una verifica richiede circa 30 secondi.\n\n"
        "Puoi usarlo anche per ESPLORARE, non solo per consegnare: i messaggi "
        "informativi di Lean ti vengono restituiti, quindi funzionano "
        "`#check nomeCostante`, `#print nomeDefinizione`, `example ... := by exact?` "
        "e `open ... in #check ...`. Il file verra' rifiutato (manca il teorema "
        "richiesto) ma riceverai comunque cio' che hai chiesto di ispezionare."
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
        # NON si tronca qui: il messaggio di Lean e' l'informazione piu' utile
        # che questo strumento restituisce, e un `unsolved goals` con lo stato
        # degli obiettivi puo' essere lungo. Il limite vero e' in
        # verify._lean_errors, dichiarato e ampio.
        righe.append(r.errors)
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
        "Librerie disponibili: la libreria standard piu' `numpy`, `sympy` e "
        "`numba`. Per la teoria dei numeri `sympy` ha `isprime`, `factorint`, "
        "`nextprime`, `divisors`, `totient`.\n\n"
        "La CARTELLA DI LAVORO SOPRAVVIVE fra le chiamate: i file che scrivi "
        "restano, quindi una ricerca lunga puo' salvare un checkpoint in un "
        "file JSON e la chiamata successiva puo' riprenderlo. Le variabili in "
        "memoria invece no: ogni esecuzione e' un processo nuovo.\n\n"
        "Limiti: nessun accesso alla rete; puoi scrivere solo nella cartella di "
        "lavoro; c'e' un tempo massimo per ogni esecuzione, quindi per una "
        "ricerca lunga conviene procedere a blocchi salvando il punto "
        "raggiunto. Stampa i risultati con print()."
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

    Si usa l'ambiente di CALCOLO (`.venv-calcolo`), che ha `numpy`, `sympy` e
    `numba`, non quello del progetto: il codice generato non deve vedere le
    librerie dell'agente ne' la sua chiave. L'isolamento non viene dalla
    poverta' dell'ambiente — viene da `sandbox-exec` (niente rete, scrittura
    solo nella cartella di lavoro), dall'ambiente ridotto senza chiave API e
    dall'opzione `-I`. Chi ha misurato il benchmark OEIS Open dava al modello
    perfino SageMath: senza librerie di calcolo un problema da confutare non si
    affronta.

    Si evita `/usr/bin/python3` perche' e' il wrapper `xcrun`, che dentro la
    sandbox stampa errori spuri.
    """
    calcolo = ROOT / ".venv-calcolo" / "bin" / "python"
    if calcolo.is_file():
        return str(calcolo)
    base = Path(sys.base_prefix) / "bin" / "python3"
    if base.is_file():
        return str(base)
    return shutil.which("python3") or sys.executable


def esegui_run_python(codice: str, timeout: int = 30, max_output: int = 20_000,
                      cartella: Path | str | None = None) -> str:
    """Esegue il codice dentro la sandbox e ne restituisce l'output.

    Se `cartella` e' data, quella cartella NON viene distrutta all'uscita: i
    file scritti dal programma restano disponibili alla chiamata successiva.
    Serve per le ricerche in piu' passi — senza persistenza un programma non
    puo' salvare un checkpoint, e ogni chiamata ricomincia da zero.
    """
    if not shutil.which("sandbox-exec"):
        return ("ERRORE: `sandbox-exec` non e' disponibile su questo sistema, "
                "quindi non posso eseguire il codice in isolamento. "
                "Lo strumento run_python e' disattivato.")

    if cartella is not None:
        fissa = Path(cartella).resolve()
        fissa.mkdir(parents=True, exist_ok=True)
        contesto = contextlib.nullcontext(str(fissa))
    else:
        contesto = tempfile.TemporaryDirectory(prefix="fcs_py_")

    with contesto as lavoro:
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
        if cartella is not None:
            resti = sorted(p.name for p in Path(lavoro_reale).iterdir()
                           if p.name not in ("programma.py", "sandbox.sb"))
            if resti:
                risultato += ("\n--- file nella cartella di lavoro (restano "
                              "disponibili alla prossima chiamata) ---\n"
                              + ", ".join(resti[:40]))
        if len(risultato) > max_output:
            risultato = risultato[:max_output] + f"\n... [output troncato a {max_output} caratteri]"
        return risultato
