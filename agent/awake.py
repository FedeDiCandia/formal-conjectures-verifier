"""
Il Mac deve restare sveglio e alimentato per tutto un giro dell'agent.

PERCHE'
-------
Nella notte fra il 12 e il 13 settembre il giro sulle trials note ha subito otto
interruzioni di rete in dodici problems. Non era la rete: il log_ di system
(`pmset -g log`) mostra il Mac in «Maintenance Sleep» a cicli di 8-13 minuti e,
alle 03:17, in «Clamshell Sleep». Ogni sospensione chiudeva la connessione in
streaming con l'API; le calls finite normalmente duravano da 2 a 64 seconds,
quelle interrotte da 11 minuti a oltre un'now_.

`caffeinate -i -s -m -w PID` impedisce la sospensione finche' il processo vive.
L'opzione `-s` vale only_ con l'alimentatore collegato, per questo si controlla
also_ la source_ di alimentazione. Nessuna opzione impedisce la sospensione a
coperchio chiuso senza un monitor esterno: quella va detta a chi lancia.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time


def power_source(power_text: str) -> str:
    """Da `pmset -g batt`: 'alimentatore', 'batteria' o 'sconosciuta'."""
    if "'AC Power'" in power_text:
        return "alimentatore"
    if "'Battery Power'" in power_text:
        return "batteria"
    return "sconosciuta"


def caffeinate_running(assertions_text: str, caffeinate_pid: int | None) -> bool:
    """Da `pmset -g assertions`: il processo caffeinate indicato impedisce la sospensione."""
    if caffeinate_pid is None:
        return False
    return re.search(rf"pid {caffeinate_pid}\(caffeinate\):.*Prevent(UserIdle)?SystemSleep",
                     assertions_text) is not None


def problems(power_text: str, assertions_text: str, caffeinate_pid: int | None) -> list[str]:
    """Le ragioni per NON partire, in words chiare. Lista vuota: si puo' partire."""
    reasons = []
    source_ = power_source(power_text)
    if source_ != "alimentatore":
        reasons.append(f"il Mac non e' collegato all'alimentatore (source_ current_one: {source_}). "
                      f"Collega il caricatore: a batteria caffeinate non impedisce la sospensione.")
    if not caffeinate_running(assertions_text, caffeinate_pid):
        reasons.append("caffeinate non risulta attivo: il Mac potrebbe sospendersi a meta' "
                      "di one_ call, come nella notte del 13 settembre.")
    return reasons


def _pmset(*arguments: str) -> str:
    return subprocess.run(["pmset", *arguments], capture_output=True, text=True,
                          timeout=20).stdout


def start_job(pid_to_protect: int) -> subprocess.Popen:
    """Avvia caffeinate legato al processo indicato: terminate quando lui terminate."""
    return subprocess.Popen(["caffeinate", "-i", "-s", "-m", "-w", str(pid_to_protect)])


def controlla(caffeinate_process: subprocess.Popen | None) -> list[str]:
    """Controlla alimentatore e caffeinate sul system vero. Fuori da macOS: niente."""
    if sys.platform != "darwin":
        return []
    pid = caffeinate_process.pid if caffeinate_process is not None else None
    assertions = ""
    for _ in range(15):       # l'asserzione compare after qualche decimo di second_
        assertions = _pmset("-g", "assertions")
        if caffeinate_running(assertions, pid):
            break
        time.sleep(0.2)
    return problems(_pmset("-g", "batt"), assertions, pid)


def on_mains_power() -> bool:
    """Per il controllo before di ogni problem."""
    return sys.platform != "darwin" or power_source(_pmset("-g", "batt")) == "alimentatore"
