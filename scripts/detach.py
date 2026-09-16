"""
Avvia un comando DISTACCATO dal processo che lo lancia.

Perche' serve: `nohup ... &` da una shell che poi esce non basta sempre — su
macOS il gruppo di processi viene comunque terminato quando la shell chiamante
muore. `start_new_session=True` mette il comando in una sessione tutta sua, e
li' sopravvive.

Uso:
    python scripts/distacca.py NOME_LAVORO -- comando e argomenti
Il log finisce in runs/lavori/NOME.log, il PID in runs/lavori/NOME.pid.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
LAVORI = RADICE / "runs" / "lavori"


def main() -> int:
    if "--" not in sys.argv:
        print(__doc__)
        return 2
    taglio = sys.argv.index("--")
    nome = sys.argv[1]
    comando = sys.argv[taglio + 1:]
    if not comando:
        print("manca il comando dopo --")
        return 2

    LAVORI.mkdir(parents=True, exist_ok=True)
    log = LAVORI / f"{nome}.log"
    pid_file = LAVORI / f"{nome}.pid"

    # se ne sta girando uno con lo stesso nome, non si raddoppia
    if pid_file.is_file():
        try:
            vecchio = int(pid_file.read_text().strip())
            os.kill(vecchio, 0)
            print(f"il lavoro '{nome}' sta gia' girando (PID {vecchio})")
            return 1
        except (ValueError, ProcessLookupError, PermissionError):
            pass

    with open(log, "a", encoding="utf-8") as f:
        proc = subprocess.Popen(
            comando, stdout=f, stderr=subprocess.STDOUT,
            cwd=str(RADICE), start_new_session=True,
            env=dict(os.environ))
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    print(f"avviato '{nome}' (PID {proc.pid})")
    print(f"  log:  {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
