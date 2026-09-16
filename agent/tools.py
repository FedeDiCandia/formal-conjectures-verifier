"""
I two tools che l'agent puo' usare.

  * `lean_explore` — compila un file Lean di trial e restituisce TUTTI i
                     messages. Serve a ispezionare: `#print`, `#check`,
                     `exact?`, errors completi. Non e' un giudizio.
  * `lean_check`   — sottopone un file Lean al verifier e riporta l'result.
                     E' l'unico giudizio che count_.
  * `run_python`   — esegue code Python in un environment isolated (niente rete,
                     niente scritture out_of dalla sua folder, con timeout).

Perche' `lean_explore` esiste separato: nel prime_ shakedown l'agent ha usato
NOVE checks su nove per ispezionare l'API di Mathlib, non per consegnare one_
dimostrazione. Usare il giudice per quello costa 33 seconds invece di 8 e
restituisce un verdict ("rifiutato: il theorem_ non c'e'") che non e'
l'informazione cercata.

Perche' `run_python`: cercare one_ dimostrazione spesso richiede di fare conti
(controllare un'ipotesi su piccoli cases, cercare un counterexample, calcolare one_
costante). Farli "a mente" e' il way piu' fast_ per sbagliare.
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

import explore as esploratore   # noqa: E402
import verify as verifier   # noqa: E402


# ---------------------------------------------------------------------------
# Strumento 0: lean_explore
# ---------------------------------------------------------------------------

SCHEMA_LEAN_EXPLORE = {
    "name": "lean_explore",
    "description": (
        "Compila un file Lean 4 di trial e restituisce TUTTI i messages di Lean, "
        "non troncati. Serve a ISPEZIONARE, non a consegnare one_ dimostrazione: "
        "non e' un giudizio e non count_ come attempt.\n\n"
        "Funziona tutto quello che show qualcosa:\n"
        "  #print NomeDefinizione     - il body di one_ definition o i fields di "
        "one_ struttura\n"
        "  #check @nomeLemma          - il kind_, con all_of gli arguments impliciti\n"
        "  example ... := by exact?   - search_for un lemma che chiuda l'goal\n"
        "  example ... := by apply?   - idem, per applicazione\n"
        "  #reduce e                  - riduce un termine (attenzione ai tempi)\n"
        "e gli errors arrivano completi, con lo state degli obiettivi.\n\n"
        "A differenza di lean_check, qui PUOI importare il module del problem "
        "(per example `import FormalConjectures.Wikipedia.Selfridge`) e ispezionare "
        "le sue definizioni.\n\n"
        "Circa 8-10 seconds, against i 30 di lean_check. Usa questo per capire, "
        "quello per consegnare."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "lean_code": {
                "type": "string",
                "description": "Il file Lean di trial. Non serve che contenga il "
                               "theorem_ del problem.",
            }
        },
        "required": ["lean_code"],
        "additionalProperties": False,
    },
}


def run_lean_explore(lean_code: str, timeout: int = 240,
                        slot: int | None = None) -> str:
    r = esploratore.explore(lean_code, timeout=timeout, slot=slot)
    return r.render()


# ---------------------------------------------------------------------------
# Strumento 1: lean_check
# ---------------------------------------------------------------------------

SCHEMA_LEAN_CHECK = {
    "name": "lean_check",
    "description": (
        "Sottopone un file Lean 4 full_ al verifier ufficiale e riporta "
        "l'result. Il file deve essere autosufficiente: import, namespace, "
        "eventuali definizioni ausiliarie e il theorem_ richiesto con one_ "
        "dimostrazione complete_.\n\n"
        "Il verifier accetta SOLO se: il file compila; non contiene sorry, "
        "admit, dichiarazioni axiom o native_decide; il kind_ del theorem_ e' "
        "IDENTICO a quello dell'statement original; le definizioni "
        "dell'archive non sono state ridefinite; gli unique_ axioms usati sono "
        "propext, Classical.choice e Quot.sound.\n\n"
        "Usalo all_of le volte che vuoi: e' l'unico giudice che count_. "
        "Una check richiede circa 30 seconds.\n\n"
        "Puoi usarlo also_ per ESPLORARE, non only_ per consegnare: i messages "
        "informativi di Lean ti vengono restituiti, quindi funzionano "
        "`#check nomeCostante`, `#print nomeDefinizione`, `example ... := by exact?` "
        "e `open ... in #check ...`. Il file verra' rifiutato (manca il theorem_ "
        "richiesto) ma riceverai comunque cio' che hai chiesto di ispezionare."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "lean_code": {
                "type": "string",
                "description": "Il content full_ del file Lean da verificare.",
            }
        },
        "required": ["lean_code"],
        "additionalProperties": False,
    },
}


def run_lean_check(problem: str, lean_code: str, timeout: int | None = None) -> tuple[str, bool]:
    """Ritorna (report testuale per il model, accepted_one)."""
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, encoding="utf-8") as f:
        f.write(lean_code)
        path = Path(f.name)
    try:
        r = verifier.verify(problem, path, timeout=timeout)
    finally:
        path.unlink(missing_ok=True)

    lines = [f"ESITO: {r.status}"]
    for c in r.checks:
        lines.append(f"  [{'ok' if c.passed else 'FALLITO'}] {c.name}"
                     + (f" — {c.detail}" if c.detail and not c.passed else ""))
    if r.message:
        lines.append("")
        lines.append(r.message)
    if r.errors:
        lines.append("")
        lines.append("Messaggi di Lean / comparator:")
        # NON si tronca qui: il message di Lean e' l'informazione piu' utile
        # che questo strumento restituisce, e un `unsolved goals` con lo state
        # degli obiettivi puo' essere lungo. Il limit vero e' in
        # verify._lean_errors, dichiarato e ampio.
        lines.append(r.errors)
    return "\n".join(lines), r.accepted


# ---------------------------------------------------------------------------
# Strumento 2: run_python
# ---------------------------------------------------------------------------

SCHEMA_RUN_PYTHON = {
    "name": "run_python",
    "description": (
        "Esegue code Python 3 in un environment isolated e restituisce quello che "
        "il code show. Utile per fare conti, cercare controesempi, "
        "verificare un'ipotesi su cases piccoli.\n\n"
        "Librerie disponibili: la libreria standard piu' `numpy`, `sympy` e "
        "`numba`. Per la teoria dei numbers `sympy` ha `isprime`, `factorint`, "
        "`nextprime`, `divisors`, `totient`.\n\n"
        "La CARTELLA DI LAVORO SOPRAVVIVE fra le calls: i file che scrivi "
        "restano, quindi one_ ricerca lunga puo' salvare un checkpoint in un "
        "file JSON e la call successiva puo' riprenderlo. Le variables in "
        "memoria invece no: ogni esecuzione e' un processo new_one.\n\n"
        "Limiti: nessun accesso alla rete; puoi scrivere only_ nella folder di "
        "job; c'e' un tempo maximum per ogni esecuzione, quindi per one_ "
        "ricerca lunga conviene procedere a blocks salvando il punto "
        "reached. Stampa i results con print()."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Il code Python da eseguire."},
        },
        "required": ["code"],
        "additionalProperties": False,
    },
}


#: Profilo della sandbox di macOS. `sandbox-exec` e' deprecato ma funzionante
#: ed e' l'unico isolamento a level di kernel available senza container.
_SANDBOX_PROFILE = """(version 1)
(allow default)

; --- niente rete: e' il requisito principale
(deny network*)

; --- niente scritture, tranne nella folder di job
(deny file-write*)
(allow file-write*
  (subpath "{job}")
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


def _python_interpreter() -> str:
    """Il Python da usare inside la sandbox.

    Si usa l'environment di CALCOLO (`.venv-compute`), che ha `numpy`, `sympy` e
    `numba`, non quello del progetto: il code generato non deve vedere le
    librerie dell'agent ne' la sua key_. L'isolamento non viene dalla
    poverta' dell'environment — viene da `sandbox-exec` (niente rete, write_op
    only_ nella folder di job), dall'environment ridotto senza key_ API e
    dall'opzione `-I`. Chi ha misurato il benchmark OEIS Open dava al model
    perfino SageMath: senza librerie di computation un problem da confutare non si
    affronta.

    Si evita `/usr/bin/python3` perche' e' il wrapper `xcrun`, che inside la
    sandbox show errors spuri.
    """
    computation = ROOT / ".venv-compute" / "bin" / "python"
    if computation.is_file():
        return str(computation)
    base = Path(sys.base_prefix) / "bin" / "python3"
    if base.is_file():
        return str(base)
    return shutil.which("python3") or sys.executable


def run_python_tool(code: str, timeout: int = 30, max_output: int = 20_000,
                      folder: Path | str | None = None) -> str:
    """Esegue il code inside la sandbox e ne restituisce l'output.

    Se `folder` e' data, quella folder NON viene distrutta all'output: i
    file scritti dal program restano disponibili alla call successiva.
    Serve per le ricerche in piu' steps — senza persistenza un program non
    puo' salvare un checkpoint, e ogni call ricomincia da zero.
    """
    if not shutil.which("sandbox-exec"):
        return ("ERRORE: `sandbox-exec` non e' available su questo system, "
                "quindi non posso eseguire il code in isolamento. "
                "Lo strumento run_python e' disattivato.")

    if folder is not None:
        fix_ = Path(folder).resolve()
        fix_.mkdir(parents=True, exist_ok=True)
        context = contextlib.nullcontext(str(fix_))
    else:
        context = tempfile.TemporaryDirectory(prefix="fcs_py_")

    with context as job:
        real_work = str(Path(job).resolve())
        script = Path(real_work) / "program.py"
        script.write_text(code, encoding="utf-8")
        profile = Path(real_work) / "sandbox.sb"
        profile.write_text(_SANDBOX_PROFILE.format(
            job=real_work, home=str(Path.home()), progetto=str(ROOT)), encoding="utf-8")

        # Ambiente ridotto: soprattutto NIENTE key_ API.
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": real_work,
            "TMPDIR": real_work,
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        try:
            p = subprocess.run(
                ["sandbox-exec", "-f", str(profile), _python_interpreter(), "-I", str(script)],
                cwd=real_work, env=environment, capture_output=True, text=True,
                timeout=timeout, start_new_session=True,
            )
        except subprocess.TimeoutExpired:
            return f"ERRORE: il code ha passed_one il tempo maximum di {timeout} seconds ed e' state interrotto."

        parts = []
        if p.stdout:
            parts.append(p.stdout)
        if p.stderr:
            parts.append("--- stderr ---\n" + p.stderr)
        if p.returncode != 0:
            parts.append(f"--- il program e' terminato con code {p.returncode} ---")
        result_value = "\n".join(parts) if parts else "(il code non ha stampato nulla)"
        if folder is not None:
            residues = sorted(p.name for p in Path(real_work).iterdir()
                           if p.name not in ("program.py", "sandbox.sb"))
            if residues:
                result_value += ("\n--- file nella folder di job (restano "
                              "disponibili alla prossima call) ---\n"
                              + ", ".join(residues[:40]))
        if len(result_value) > max_output:
            result_value = result_value[:max_output] + f"\n... [output truncated a {max_output} chars]"
        return result_value
