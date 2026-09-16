"""
Start a command DETACHED from the process that launches it.

Why it is needed: `nohup ... &` from a shell that then exits is not always enough —
on macOS the process group is killed anyway when the calling shell dies.
`start_new_session=True` puts the command in a session of its own, where it
survives.

Usage:
    python scripts/detach.py JOB_NAME -- command and arguments
The log goes to runs/jobs/NAME.log, the PID to runs/jobs/NAME.pid.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "runs" / "jobs"


def main() -> int:
    if "--" not in sys.argv:
        print(__doc__)
        return 2
    cut = sys.argv.index("--")
    name = sys.argv[1]
    command = sys.argv[cut + 1:]
    if not command:
        print("the command after -- is missing")
        return 2

    JOBS.mkdir(parents=True, exist_ok=True)
    log = JOBS / f"{name}.log"
    pid_file = JOBS / f"{name}.pid"

    # if one with the same name is already running, do not start a second
    if pid_file.is_file():
        try:
            old = int(pid_file.read_text().strip())
            os.kill(old, 0)
            print(f"the job '{name}' is already running (PID {old})")
            return 1
        except (ValueError, ProcessLookupError, PermissionError):
            pass

    with open(log, "a", encoding="utf-8") as f:
        proc = subprocess.Popen(
            command, stdout=f, stderr=subprocess.STDOUT,
            cwd=str(ROOT), start_new_session=True,
            env=dict(os.environ))
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    print(f"avviato '{name}' (PID {proc.pid})")
    print(f"  log:  {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
