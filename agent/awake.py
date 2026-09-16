"""
The Mac has to stay awake and on mains power for a whole agent run.

WHY
---
On the night of 12–13 September the run on known proofs suffered eight network
interruptions across twelve problems. It was not the network: the system log
(`pmset -g log`) shows the Mac in "Maintenance Sleep" on 8–13 minute cycles and,
at 03:17, in "Clamshell Sleep". Every sleep closed the streaming connection to the
API; calls that finished normally lasted 2 to 64 seconds, the interrupted ones from
11 minutes to over an hour.

`caffeinate -i -s -m -w PID` prevents sleep as long as the process lives. The `-s`
option only applies on mains power, which is why the power source is checked too.
No option prevents sleep with the lid closed and no external monitor: that has to
be said to whoever launches the run.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time


def power_source(power_text: str) -> str:
    """From `pmset -g batt`: 'mains', 'battery' or 'unknown'."""
    if "'AC Power'" in power_text:
        return "mains"
    if "'Battery Power'" in power_text:
        return "battery"
    return "unknown"


def caffeinate_running(assertions_text: str, caffeinate_pid: int | None) -> bool:
    """From `pmset -g assertions`: the given caffeinate process is preventing sleep."""
    if caffeinate_pid is None:
        return False
    return re.search(rf"pid {caffeinate_pid}\(caffeinate\):.*Prevent(UserIdle)?SystemSleep",
                     assertions_text) is not None


def problems(power_text: str, assertions_text: str, caffeinate_pid: int | None) -> list[str]:
    """The reasons NOT to start, in plain words. An empty list means: go ahead."""
    reasons = []
    source = power_source(power_text)
    if source != "mains":
        reasons.append(f"the Mac is not plugged in (current source: {source}). "
                       f"Connect the charger: on battery, caffeinate does not prevent sleep.")
    if not caffeinate_running(assertions_text, caffeinate_pid):
        reasons.append("caffeinate does not appear to be running: the Mac could go to sleep "
                       "half-way through a call, as it did on the night of 13 September.")
    return reasons


def _pmset(*arguments: str) -> str:
    return subprocess.run(["pmset", *arguments], capture_output=True, text=True,
                          timeout=20).stdout


def start_job(pid_to_protect: int) -> subprocess.Popen:
    """Start caffeinate bound to the given process: it ends when that process ends."""
    return subprocess.Popen(["caffeinate", "-i", "-s", "-m", "-w", str(pid_to_protect)])


def check(caffeinate_process: subprocess.Popen | None) -> list[str]:
    """Check mains power and caffeinate on the real system. Outside macOS: nothing."""
    if sys.platform != "darwin":
        return []
    pid = caffeinate_process.pid if caffeinate_process is not None else None
    assertions = ""
    for _ in range(15):       # the assertion appears after a few tenths of a second
        assertions = _pmset("-g", "assertions")
        if caffeinate_running(assertions, pid):
            break
        time.sleep(0.2)
    return problems(_pmset("-g", "batt"), assertions, pid)


def on_mains_power() -> bool:
    """For the check before each problem."""
    return sys.platform != "darwin" or power_source(_pmset("-g", "batt")) == "mains"
