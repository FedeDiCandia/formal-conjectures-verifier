"""
Il Mac deve restare sveglio e alimentato per tutto un giro dell'agent.

PERCHE'
-------
Nella notte fra il 12 e il 13 settembre il giro sulle prove note ha subito otto
interruzioni di rete in dodici problemi. Non era la rete: il registro di sistema
(`pmset -g log`) mostra il Mac in «Maintenance Sleep» a cicli di 8-13 minuti e,
alle 03:17, in «Clamshell Sleep». Ogni sospensione chiudeva la connessione in
streaming con l'API; le chiamate finite normalmente duravano da 2 a 64 secondi,
quelle interrotte da 11 minuti a oltre un'ora.

`caffeinate -i -s -m -w PID` impedisce la sospensione finche' il processo vive.
L'opzione `-s` vale solo con l'alimentatore collegato, per questo si controlla
anche la fonte di alimentazione. Nessuna opzione impedisce la sospensione a
coperchio chiuso senza un monitor esterno: quella va detta a chi lancia.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time


def fonte_alimentazione(testo_batt: str) -> str:
    """Da `pmset -g batt`: 'alimentatore', 'batteria' o 'sconosciuta'."""
    if "'AC Power'" in testo_batt:
        return "alimentatore"
    if "'Battery Power'" in testo_batt:
        return "batteria"
    return "sconosciuta"


def caffeinate_attivo(testo_assertions: str, pid_caffeinate: int | None) -> bool:
    """Da `pmset -g assertions`: il processo caffeinate indicato impedisce la sospensione."""
    if pid_caffeinate is None:
        return False
    return re.search(rf"pid {pid_caffeinate}\(caffeinate\):.*Prevent(UserIdle)?SystemSleep",
                     testo_assertions) is not None


def problemi(testo_batt: str, testo_assertions: str, pid_caffeinate: int | None) -> list[str]:
    """Le ragioni per NON partire, in parole chiare. Lista vuota: si puo' partire."""
    motivi = []
    fonte = fonte_alimentazione(testo_batt)
    if fonte != "alimentatore":
        motivi.append(f"il Mac non e' collegato all'alimentatore (fonte attuale: {fonte}). "
                      f"Collega il caricatore: a batteria caffeinate non impedisce la sospensione.")
    if not caffeinate_attivo(testo_assertions, pid_caffeinate):
        motivi.append("caffeinate non risulta attivo: il Mac potrebbe sospendersi a meta' "
                      "di una chiamata, come nella notte del 13 settembre.")
    return motivi


def _pmset(*argomenti: str) -> str:
    return subprocess.run(["pmset", *argomenti], capture_output=True, text=True,
                          timeout=20).stdout


def avvia(pid_da_proteggere: int) -> subprocess.Popen:
    """Avvia caffeinate legato al processo indicato: termina quando lui termina."""
    return subprocess.Popen(["caffeinate", "-i", "-s", "-m", "-w", str(pid_da_proteggere)])


def controlla(processo_caffeinate: subprocess.Popen | None) -> list[str]:
    """Controlla alimentatore e caffeinate sul sistema vero. Fuori da macOS: niente."""
    if sys.platform != "darwin":
        return []
    pid = processo_caffeinate.pid if processo_caffeinate is not None else None
    assertions = ""
    for _ in range(15):       # l'asserzione compare dopo qualche decimo di secondo
        assertions = _pmset("-g", "assertions")
        if caffeinate_attivo(assertions, pid):
            break
        time.sleep(0.2)
    return problemi(_pmset("-g", "batt"), assertions, pid)


def alimentatore_collegato() -> bool:
    """Per il controllo prima di ogni problema."""
    return sys.platform != "darwin" or fonte_alimentazione(_pmset("-g", "batt")) == "alimentatore"
