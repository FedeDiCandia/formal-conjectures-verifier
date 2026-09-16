"""
Avvia un command DISTACCATO dal processo che lo lancia.

Perche' serve: `nohup ... &` da one shell che poi exits non basta sempre — su
macOS il group di processi viene comunque terminato quando la shell chiamante
muore. `start_new_session=True` mette il command in one sessione tutta sua, e
li' sopravvive.

Uso:
    python scripts/distacca.py NOME_LAVORO -- command e arguments
Il log finisce in runs/jobs/NOME.log, il PID in runs/jobs/NOME.pid.
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
        print("manca il command after --")
        return 2

    JOBS.mkdir(parents=True, exist_ok=True)
    log = JOBS / f"{name}.log"
    pid_file = JOBS / f"{name}.pid"

    # se ne sta girando one con lo stesso name, non si raddoppia
    if pid_file.is_file():
        try:
            old = int(pid_file.read_text().strip())
            os.kill(old, 0)
            print(f"il job '{name}' sta gia' girando (PID {old})")
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
