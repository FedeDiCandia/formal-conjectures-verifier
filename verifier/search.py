"""
Running long searches: isolated, with checkpoints and resumption.

WHAT IT IS FOR
--------------
Looking for a counterexample to a conjecture can take hours or days. A search
like that has three needs an ordinary script does not cover:

  * ISOLATION — the search program is written by a language model and has no
    reason to touch the network or the rest of the disk. It runs inside
    `sandbox-exec`, like everything else in this project.
  * CHECKPOINTS — if the machine dies after six hours, starting again from the
    beginning is unacceptable. The program saves how far it has got at regular
    intervals, and resumes from there.
  * A REPORT — a search that finds nothing is not a failure: it says "up to N
    there is nothing", which is information. It has to be recorded.

The search program has to honour a small contract, set out in `CONTRACT` below:
it reads where to resume from, prints progress as JSON, and stops gracefully when
it receives the stop signal.
"""
from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import sandbox


CONTRACT = """
CONTRACT FOR A SEARCH PROGRAM
=============================
Your program receives two environment variables:

  SEARCH_CHECKPOINT   path to a JSON file. If it exists, it holds the point to
                      resume from, in whatever shape you chose.
  SEARCH_STATE        path to WRITE the updated checkpoint to.

You must:

1. At startup, if SEARCH_CHECKPOINT exists, read it and resume from there.
   Otherwise start from the beginning.

2. Every so often (at least every 30 seconds) write to SEARCH_STATE a JSON
   object with at least these fields:
       {"position": <how far you have got>, "examined": <how many cases>,
        "found": [<any results>]}
   Write it to a temporary file first and then rename it, so that an interruption
   half-way through does not leave a corrupted checkpoint.

3. Print one JSON line on stdout for every significant step:
       {"event": "progress", "position": ..., "examined": ...}
       {"event": "found", "detail": {...}}
   Lines that are not valid JSON are kept in the log but ignored.

4. Handle SIGTERM: save the checkpoint and exit with code 0.
   The runner sends SIGTERM when the user stops the search.

5. Do not use the network (it is blocked) and do not write outside your own
   directory.
"""


@dataclass
class SearchResult:
    name: str
    completed: bool = False
    interrupted: bool = False
    seconds: float = 0.0
    position: object = None
    examined: int = 0
    found: list = field(default_factory=list)
    exit_code: int | None = None
    error: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, default=str)


class Search:
    """One long, isolated, resumable search."""

    def __init__(self, name: str, program: str, folder: Path | None = None,
                 interpreter: Path | None = None, variables: dict | None = None):
        self.name = name
        self.program = program
        #: Parameters passed to the program as environment variables.
        #: The child process's environment is deliberately minimal (no API key,
        #: none of the project's PATH), so parameters have to be passed
        #: explicitly here: whatever is in the launcher's environment does NOT
        #: reach the search program.
        self.variables = dict(variables or {})
        self.folder = (folder or (config.ROOT / "runs" / "hunt" / name))
        self.folder.mkdir(parents=True, exist_ok=True)
        #: the computation environment, with numpy, sympy and numba
        self.interpreter = interpreter or (config.ROOT / ".venv-compute" / "bin" / "python")
        if not self.interpreter.is_file():
            self.interpreter = Path(sys.base_prefix) / "bin" / "python3"

    # --- files
    @property
    def program_file(self) -> Path:
        return self.folder / "program.py"

    @property
    def checkpoint_file(self) -> Path:
        return self.folder / "checkpoint.json"

    @property
    def log_file(self) -> Path:
        return self.folder / "search.log"

    @property
    def result_file(self) -> Path:
        return self.folder / "result.json"

    # --- execution
    def _profile(self, tmp: Path) -> Path | None:
        if not (config.USE_SANDBOX and sandbox.available()):
            return None
        writable = [self.folder, tmp]
        for d in writable:
            d.mkdir(parents=True, exist_ok=True)
        return sandbox.write_profile(tmp / "search.sb", writable, config.ROOT)

    def run(self, *, max_seconds: float | None = None,
            resume: bool = True, verbose: bool = True) -> SearchResult:
        self.program_file.write_text(self.program, encoding="utf-8")
        result = SearchResult(name=self.name)

        if not resume:
            self.checkpoint_file.unlink(missing_ok=True)

        new_state = self.folder / "state.json"
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.folder),
            "TMPDIR": str(self.folder),
            "LANG": "C.UTF-8",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "SEARCH_CHECKPOINT": str(self.checkpoint_file),
            "SEARCH_STATE": str(new_state),
        }
        environment.update({k: str(v) for k, v in self.variables.items()})

        import tempfile
        with tempfile.TemporaryDirectory(prefix=f"search{self.name}_") as tmp:
            tmp_dir = Path(tmp)
            profile = self._profile(tmp_dir)
            command = [str(self.interpreter), "-u", str(self.program_file)]
            if profile is not None:
                command = sandbox.wrap(command, profile)

            start = time.time()
            with open(self.log_file, "a", encoding="utf-8") as log:
                log.write(f"\n=== start {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                log.flush()
                proc = subprocess.Popen(
                    command, cwd=str(self.folder), env=environment,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, start_new_session=True, bufsize=1)

                def terminate(_s=None, _f=None):
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass

                original = signal.getsignal(signal.SIGTERM)
                try:
                    signal.signal(signal.SIGTERM, terminate)
                except ValueError:
                    pass   # not on the main thread

                try:
                    for line in proc.stdout:
                        log.write(line)
                        log.flush()
                        line = line.strip()
                        if verbose and line:
                            print(f"  [{self.name}] {line[:150]}", flush=True)
                        try:
                            event = json.loads(line)
                        except Exception:
                            event = None
                        if isinstance(event, dict):
                            if event.get("event") == "found":
                                result.found.append(event.get("detail"))
                            if "position" in event:
                                result.position = event["position"]
                            if "examined" in event:
                                result.examined = event["examined"]
                        if max_seconds and time.time() - start > max_seconds:
                            result.interrupted = True
                            terminate()
                            break
                    proc.wait(timeout=60)
                except KeyboardInterrupt:
                    result.interrupted = True
                    terminate()
                    proc.wait(timeout=60)
                finally:
                    try:
                        signal.signal(signal.SIGTERM, original)
                    except ValueError:
                        pass

            result.exit_code = proc.returncode
            result.seconds = time.time() - start

        # the checkpoint the program wrote becomes the one to resume from
        if new_state.is_file():
            shutil.move(str(new_state), str(self.checkpoint_file))
        if self.checkpoint_file.is_file():
            try:
                data = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
                result.position = data.get("position", result.position)
                result.examined = data.get("examined", result.examined)
                for t in data.get("found", []):
                    if t not in result.found:
                        result.found.append(t)
            except Exception as e:
                result.error = f"unreadable checkpoint: {e}"

        result.completed = (result.exit_code == 0 and not result.interrupted)
        self.result_file.write_text(result.to_json(), encoding="utf-8")
        return result
