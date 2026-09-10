"""
Isolamento della verifica (macOS).

PERCHE'
-------
Per giudicare una dimostrazione bisogna COMPILARLA, e compilare un file Lean
significa eseguire codice: elaboratori, macro, tattiche. `comparator` su Linux
isola questa fase con `landrun`; su macOS `landrun` non esiste.

Qui usiamo `sandbox-exec`, il meccanismo di isolamento del kernel di macOS.
Deprecato da Apple ma funzionante, ed e' l'unico disponibile senza container.

COSA CONSENTE
-------------
- lettura: tutto (serve a leggere Mathlib, il toolchain, l'archivio);
- scrittura: SOLO le tre cartelle dove `lake` deposita il modulo temporaneo del
  candidato, piu' la cartella dei file temporanei. Misurato sul campo: una
  verifica non tocca nient'altro;
- rete: NIENTE.

Quello che resta fuori dalla sandbox e' il codice del candidato che tentasse di
riscrivere i file compilati dell'archivio: e' esattamente l'attacco descritto
nell'assunto 2 del README di comparator ("non devi aver gia' compilato file
potenzialmente ostili, perche' potrebbero aver alterato il tuo Challenge").
Come seconda rete di sicurezza, `verifier/impronta.py` confronta l'impronta
dell'archivio prima e dopo ogni verifica.
"""
from __future__ import annotations

import shutil
from pathlib import Path

#: `(subpath ...)` in un profilo sandbox richiede percorsi assoluti e reali
#: (senza link simbolici): su macOS /tmp e' un link a /private/tmp, e usare la
#: forma non risolta fa fallire silenziosamente il permesso.
def _reale(p: Path) -> str:
    return str(Path(p).resolve())


PROFILO = """(version 1)
(allow default)

; ---- nessun accesso alla rete
(deny network*)

; ---- nessuna scrittura, tranne dove serve davvero
(deny file-write*)
(allow file-write*
{scrivibili}
  (literal "/dev/null")
  (literal "/dev/zero")
  (literal "/dev/random")
  (literal "/dev/urandom")
  (literal "/dev/dtracehelper")
  (literal "/dev/tty"))

; ---- niente lettura dei segreti
(deny file-read*
  (subpath "{home}/.ssh")
  (subpath "{home}/.aws")
  (subpath "{home}/.gnupg")
  (subpath "{home}/.config/anthropic")
  (subpath "{home}/.anthropic")
  (literal "{env_progetto}"))
"""


def cartelle_scrivibili(archivio: Path, sottocartella_judge: str, tmp: Path) -> list[Path]:
    """Le uniche cartelle che una verifica ha bisogno di modificare.

    Ricavate misurando quali file cambiano durante una verifica riuscita:
    i sorgenti del modulo temporaneo e i due rami di `.lake/build` che lo
    riguardano. Nient'altro.
    """
    lake = archivio / ".lake" / "build"
    return [
        archivio / sottocartella_judge,
        lake / "ir" / sottocartella_judge,
        lake / "lib" / "lean" / sottocartella_judge,
        tmp,
    ]


def scrivi_profilo(destinazione: Path, scrivibili: list[Path], progetto: Path) -> Path:
    righe = "\n".join(f'  (subpath "{_reale(p)}")' for p in scrivibili)
    destinazione.write_text(
        PROFILO.format(scrivibili=righe, home=_reale(Path.home()),
                       env_progetto=_reale(progetto / ".env")),
        encoding="utf-8")
    return destinazione


def disponibile() -> bool:
    return shutil.which("sandbox-exec") is not None


def avvolgi(comando: list[str], profilo: Path) -> list[str]:
    """Antepone `sandbox-exec` al comando."""
    return ["sandbox-exec", "-f", str(profilo)] + comando
