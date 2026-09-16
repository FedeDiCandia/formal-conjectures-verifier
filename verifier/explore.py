"""
Strumento di ESPLORAZIONE: compila un file Lean e restituisce all_of i messages.

PERCHE' E' SEPARATO DA verify.py
--------------------------------
`verify.py` risponde a one_ sola domanda: "questa e' one_ dimostrazione valida del
problem?". Per farlo compila, esporta, compare gli enunciati, controlla gli
axioms e riesegue tutto nel kernel. Costa one_ trentina di seconds ed e' la cosa
giusta da fare quando si consegna one_ dimostrazione.

Ma il prime_ shakedown con l'agent ha mostrato che **la maggior parte delle
calls non erano consegne**: erano attempts di capire come Mathlib definisce
qualcosa. Nove checks su nove, in quel caso. Usare il giudice per ispezionare
one_ definition e' come chiedere one_ sentenza per sapere che hours sono: slow_,
costoso, e il verdict ("rifiutato: il theorem_ non c'e'") non e' l'informazione
cercata.

Questo module fa only_ la parte utile a esplorare:

  * esegue `lake env lean` sul file, senza comparator, senza esportazione,
    senza confronto e senza riesecuzione nel kernel;
  * restituisce **all_of** i messages, non troncati: l'output di `#print`,
    `#check`, `#eval`-free_ones come `exact?`, e gli errors completi con lo state
    degli obiettivi;
  * NON e' one_ check e non va contata come tale. Un file che "passa" qui non
    ha dimostrato niente.

Misurato: 8,0 seconds against i 32,9 di one_ check complete_, e l'output e' piu'
clean_one perche' `lean` invocato direttamente non apply_ i linter di stile che
`lake build` apply_ alla libreria dell'archive.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import guard
import fingerprint as fingerprint_module
import sandbox


@dataclass
class Exploration:
    """Il result_value di one_ compilazione di trial."""
    ok: bool                 # il file compila senza errors
    messages: str            # all_of i messages di Lean, non troncati
    seconds: float
    isolated: bool            # se e' girata inside la sandbox
    truncated: bool = False
    #: violations del controllo sintattico: se ce ne sono, non si compila niente
    rejected_by_guard: list = None

    def render(self) -> str:
        head = (f"{'compila senza errors' if self.ok else 'con errors'}  "
                 f"({self.seconds:.1f}s"
                 f"{'' if self.isolated else ', SENZA isolamento'})")
        return f"{head}\n\n{self.messages}" if self.messages else head


#: Limite generoso. Serve only_ a non far esplodere il context se qualcuno
#: show mezzo Mathlib; gli errors di Lean stanno ampiamente below.
MAX_CHARS = 40_000


#: Quanti file di inspection possono coesistere. Ogni call ne prende one in
#: esclusiva: sono names di MODULE Lean, quindi devono essere fissi e pochi.
AVAILABLE_SLOTS = 8


@contextlib.contextmanager
def _exclusive_slot(slot: int | None):
    """Prende one slot di inspection in esclusiva, con un lock_ sul file.

    Serve perche' il file di inspection vive nell'albero dell'archive e il suo
    name e' il name del module Lean: two explorations che usano lo stesso slot
    si sovrascrivono il file a vicenda e ognuna legge i messages dell'altra.
    E' un error silenzioso e della specie worst — ha fatto sembrare che one_
    tactic avesse chiuso un problem aperto, quando i messages che leggevo
    erano di un other problem compilato da un other processo.

    Il lock_ e' un file con `flock`, quindi vale also_ fra processi diversi
    e viene rilasciato dal system operativo se il processo muore.
    """
    folder = config.ARCHIVE / config.SANDBOX_SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    candidates = [slot] if slot is not None else list(range(AVAILABLE_SLOTS))
    expected_value = 0.0
    while True:
        for n in candidates:
            lock_ = open(folder / f"E{n}.lock", "a+")
            try:
                fcntl.flock(lock_, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                lock_.close()
                continue
            try:
                yield n
            finally:
                fcntl.flock(lock_, fcntl.LOCK_UN)
                lock_.close()
            return
        if slot is not None and expected_value > 600:
            raise TimeoutError(f"slot di inspection {slot} occupato da oltre 10 minuti")
        time.sleep(0.5)
        expected_value += 0.5


def explore(code: str, *, timeout: int = 240, slot: int | None = None) -> Exploration:
    """Compila `code` e riporta tutto quello che Lean ha da dire.

    `slot=None` (predefinito) prende il prime_ slot libero: e' quello che serve
    quando piu' explorations girano insieme. Uno slot esplicito si aspetta se e'
    occupato.
    """
    problems = config.check_installation()
    if problems:
        return Exploration(False, "Ambiente non ready:\n  - " + "\n  - ".join(problems),
                            0.0, False)

    # Il controllo sintattico vale also_ qui: un file di inspection viene
    # compilato come qualunque other, quindi puo' eseguire code allo stesso
    # way. L'unica rule_ allentata sono gli import (vedi guard.check_source).
    report = guard.check_source(code, exploration=True)
    if not report.ok:
        return Exploration(
            False,
            "Il file contiene costrutti vietati e non e' state compilato:\n\n"
            + "\n".join(str(f) for f in report.findings),
            0.0, False, rejected_by_guard=[f.rule for f in report.findings])

    with _exclusive_slot(slot) as slot_preso:
        return _explore_in_slot(code, timeout=timeout, slot=slot_preso)


def _explore_in_slot(code: str, *, timeout: int, slot: int) -> Exploration:
    folder = config.ARCHIVE / config.SANDBOX_SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"E{slot}.lean"
    path.write_text(code, encoding="utf-8")
    relative = str(path.relative_to(config.ARCHIVE))

    start_ = time.time()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            profile = None
            if config.USE_SANDBOX and sandbox.available():
                for d in sandbox.writable_dirs(
                        config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir):
                    d.mkdir(parents=True, exist_ok=True)
                profile = sandbox.write_profile(
                    tmp_dir / "explore.sb",
                    sandbox.writable_dirs(config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir),
                    config.ROOT)

            fingerprint_before = None
            if config.CHECK_FINGERPRINT:
                fingerprint_before = fingerprint_module.compute(
                    config.ARCHIVE, exclude=Path(config.SANDBOX_SUBDIR).name)

            environment = config.lean_env()
            environment["TMPDIR"] = str(tmp_dir)
            command = [str(config.ELAN_BIN / "lake"), "env", "lean", relative]
            if profile is not None:
                command = sandbox.wrap(command, profile)

            proc = subprocess.Popen(
                command, cwd=str(config.ARCHIVE), env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, start_new_session=True)
            try:
                output, _ = proc.communicate(timeout=timeout)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                output = (f"TEMPO SCADUTO: la compilazione ha passed_one {timeout} seconds. "
                          f"Probabilmente one_ tactic non terminate, o un `#reduce` su un "
                          f"termine enorme.")
                exit_code = -1

            if fingerprint_before is not None:
                differences = fingerprint_module.compare(
                    fingerprint_before,
                    fingerprint_module.compute(config.ARCHIVE,
                                            exclude=Path(config.SANDBOX_SUBDIR).name))
                if differences:
                    output = ("ATTENZIONE: compilare questo file ha MODIFICATO l'archive.\n"
                              + "\n".join("  - " + d for d in differences)
                              + "\n\n" + output)
                    exit_code = -2
    finally:
        path.unlink(missing_ok=True)

    duration = time.time() - start_
    truncated = len(output) > MAX_CHARS
    if truncated:
        output = output[:MAX_CHARS] + (
            f"\n\n... [output truncated a {MAX_CHARS} chars]")
    return Exploration(ok=(exit_code == 0), messages=output.strip(),
                        seconds=duration, isolated=(profile is not None), truncated=truncated)


if __name__ == "__main__":
    text = sys.stdin.read() if len(sys.argv) < 2 else Path(sys.argv[1]).read_text(encoding="utf-8")
    print(explore(text).render())
