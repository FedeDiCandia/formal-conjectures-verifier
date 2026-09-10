#!/usr/bin/env python3
"""
verify.py — il verificatore delle dimostrazioni.

COSA FA
-------
Riceve un file Lean candidato e il nome del teorema originale dell'archivio, e
risponde ACCETTATO / RIFIUTATO. Accetta solo se TUTTE queste cose sono vere:

  1. il file non contiene costrutti vietati (controllo sintattico preventivo);
  2. il file compila senza errori;
  3. non contiene `sorry`, `admit` ne' nuove dichiarazioni `axiom`;
  4. gli assiomi usati dal teorema sono solo propext, Classical.choice, Quot.sound;
  5. il TIPO del teorema e' identico a quello dell'enunciato originale — il
     confronto avviene sull'albero sintattico di Lean esportato, non sul testo;
  6. il file non ridefinisce ne' modifica le definizioni dell'archivio usate
     nell'enunciato;
  7. il termine di prova e' accettato da una riesecuzione nel kernel di Lean;
  8. non usa opzioni che disattivano i controlli del kernel.

COME LO FA
----------
I punti 2, 4, 5, 6, 7 non sono implementati a mano: li delega a `comparator`
(https://github.com/leanprover/comparator), il "giudice" scritto dal Lean FRO
proprio per validare le dimostrazioni prodotte da modelli linguistici.
comparator compila i due moduli, li esporta in formato testo con `lean4export`
(senza mai fidarsi degli .olean), confronta gli enunciati, controlla gli assiomi
e infine RIESEGUE tutto nel kernel di Lean. E' molto piu' affidabile di
qualunque cosa potremmo scrivere noi.

I punti 1, 3 e 8 sono il controllo sintattico di `guard.py`, che serve da difesa
in profondita' (vedi il commento in cima a quel file).

USO
---
    python3 verifier/verify.py NOME_TEOREMA FILE.lean
    python3 verifier/verify.py NOME_TEOREMA FILE.lean --json
    python3 verifier/verify.py --batch lavori.jsonl --jobs 4
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import guard
from index import ProblemIndex, Problem


# ---------------------------------------------------------------------------
# Risultato
# ---------------------------------------------------------------------------

#: Esiti possibili.
ACCEPTED = "ACCETTATO"
REJECTED = "RIFIUTATO"
ERROR = "ERRORE"
TIMEOUT = "TIMEOUT"
UNVERIFIABLE = "NON_VERIFICABILE"


@dataclass
class Check:
    """Un singolo controllo, con il suo esito."""
    name: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:
        mark = "OK  " if self.passed else "NO  "
        return f"  [{mark}] {self.name}" + (f"\n         {self.detail}" if self.detail else "")


@dataclass
class Result:
    problem: str
    status: str
    checks: list[Check] = field(default_factory=list)
    message: str = ""
    #: errori di compilazione o messaggi di comparator, utili all'agente
    errors: str = ""
    duration_s: float = 0.0
    raw_output: str = ""

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED

    def to_json(self) -> str:
        d = asdict(self)
        d["accepted"] = self.accepted
        return json.dumps(d, ensure_ascii=False, indent=2)

    def render(self) -> str:
        head = f"{self.status}  —  {self.problem}   ({self.duration_s:.1f}s)"
        body = "\n".join(str(c) for c in self.checks)
        out = f"{head}\n{body}"
        if self.message:
            out += f"\n\n{self.message}"
        if self.errors:
            out += f"\n\n--- messaggi di Lean / comparator ---\n{self.errors}"
        return out


# ---------------------------------------------------------------------------
# Gestione degli "slot": limita quanti processi Lean girano insieme
# ---------------------------------------------------------------------------

class SlotPool:
    """Una coda di N posti. Ogni verifica ne occupa uno e usa il proprio nome di
    modulo Lean, cosi' due verifiche in parallelo non si pestano i piedi."""

    def __init__(self, size: int):
        self.size = size
        self._free: queue.Queue[int] = queue.Queue()
        for i in range(size):
            self._free.put(i)

    def acquire(self, timeout: Optional[float] = None) -> int:
        return self._free.get(timeout=timeout)

    def release(self, slot: int) -> None:
        self._free.put(slot)


_default_pool: Optional[SlotPool] = None
_pool_lock = threading.Lock()


def get_pool(size: Optional[int] = None) -> SlotPool:
    global _default_pool
    with _pool_lock:
        if _default_pool is None:
            _default_pool = SlotPool(size or config.MAX_PARALLEL)
        return _default_pool


# ---------------------------------------------------------------------------
# Esecuzione di comparator
# ---------------------------------------------------------------------------

def _run_with_timeout(cmd: list[str], cwd: Path, env: dict, timeout: int) -> tuple[int, str]:
    """Esegue un comando con timeout, uccidendo l'INTERO albero di processi.

    Serve perche' comparator lancia `lake`, che lancia `lean`: uccidere solo il
    padre lascerebbe i figli a consumare CPU per sempre. `start_new_session`
    mette tutto in un gruppo di processi che possiamo terminare in blocco.
    """
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            out, _ = proc.communicate(timeout=30)
        except Exception:
            out = ""
        return -signal.SIGKILL, out or ""


def _classify(output: str) -> tuple[str, str]:
    """Traduce l'output di comparator in (nome del controllo fallito, spiegazione)."""
    m = re.search(r"Illegal axiom detected: '([^']+)'", output)
    if m:
        ax = m.group(1)
        spiega = {
            "sorryAx": "la dimostrazione contiene un `sorry` (un buco), diretto o "
                       "ereditato da un lemma ausiliario",
            "Lean.ofReduceBool": "e' stato usato `native_decide`, che si fida del "
                                 "compilatore invece che del kernel",
            "Lean.trustCompiler": "e' stato chiesto di fidarsi del compilatore",
        }.get(ax, f"il teorema dipende dall'assioma `{ax}`, che non e' fra quelli permessi "
                  f"({', '.join(config.PERMITTED_AXIOMS)})")
        return "assiomi ammessi", f"assioma illecito `{ax}`: {spiega}"

    if "theorem statement do not match" in output:
        return ("tipo identico all'originale",
                "l'enunciato dimostrato NON e' identico a quello dell'archivio. "
                "Puo' essere un enunciato piu' debole, con ipotesi in piu', o "
                "semplicemente scritto in modo che Lean elabora diversamente.")
    if "constant kind don't match" in output:
        return ("tipo identico all'originale",
                "nel candidato la dichiarazione ha una natura diversa (es. `def` invece di `theorem`)")
    if "Solution constant is not a theorem" in output:
        return ("tipo identico all'originale", "nel candidato la dichiarazione non e' un teorema")
    if "Const does not match between challenge and target" in output or \
       "does not match between challenge" in output:
        m2 = re.search(r"target '([^']+)'", output)
        quale = f" (`{m2.group(1)}`)" if m2 else ""
        return ("definizioni dell'archivio intatte",
                f"il candidato RIDEFINISCE in modo diverso una definizione usata "
                f"nell'enunciato{quale}. L'enunciato sembra uguale ma parla di altro.")
    if "Const not found in solution" in output or "Constant not found in solution" in output:
        m2 = re.search(r"in solution:? '([^']+)'", output)
        quale = f" `{m2.group(1)}`" if m2 else ""
        return ("teorema presente", f"il candidato non dichiara{quale}. Il nome deve "
                                    f"coincidere ESATTAMENTE con quello dell'archivio, "
                                    f"namespace compreso.")
    if "kernel rejected the solution" in output:
        return ("accettato dal kernel", "il kernel di Lean ha rifiutato il termine di prova")
    if "error:" in output:
        return ("compila senza errori", "il file non compila")
    if "Child exited with" in output:
        return ("compila senza errori", "la compilazione e' fallita")
    return ("verifica di comparator", "comparator ha rifiutato il candidato")


#: Righe con cui `lake` annuncia lo stato: non sono messaggi di Lean.
_STATO_LAKE = re.compile(r"^(Building |Exporting |Build completed|Running |"
                         r"[✔⚠✖ℹ] |info: \[|error: build failed|trace:)")

#: Inizio di un messaggio di Lean. Il messaggio prosegue sulle righe successive
#: finche' non ne comincia un altro o non compare una riga di stato di lake.
_INIZIO_MESSAGGIO = re.compile(r"^(info|warning|error): ")

#: Linter di STILE dell'archivio: si lamentano che il nostro modulo temporaneo
#: non ha l'intestazione di copyright, non ha il docstring di modulo, ecc.
#: Sono irrilevanti — il file candidato non e' un contributo all'archivio — e
#: ripetono quindici righe di licenza a ogni messaggio, inondando il contesto.
_RUMORE_LINTER = re.compile(
    r"linter\.style\.(copyright|namespace|ams_attribute|category_attribute|moduleDocstring)"
    r"|The copyright header is incorrect"
    r"|missing a module docstring")

#: Messaggi di comparator: righe isolate, senza il prefisso di Lean.
_MESSAGGIO_COMPARATOR = re.compile(
    r"Illegal axiom|do not match|does not match|not found in|Constant not found|"
    r"rejected the solution|uncaught exception|kernel accepts")


def _blocchi_messaggi(output: str) -> list[str]:
    """Ricompone i messaggi di Lean, che sono blocchi su piu' righe."""
    blocchi: list[str] = []
    corrente: list[str] = []

    def chiudi():
        if corrente:
            blocchi.append("\n".join(corrente).rstrip())
            corrente.clear()

    for riga in output.split("\n"):
        if _INIZIO_MESSAGGIO.match(riga):
            chiudi()
            corrente.append(riga.rstrip())
        elif _STATO_LAKE.match(riga):
            chiudi()
        elif corrente:
            corrente.append(riga.rstrip())
        elif _MESSAGGIO_COMPARATOR.search(riga):
            blocchi.append(riga.rstrip())
    chiudi()
    return blocchi


def _lean_errors(output: str, max_caratteri: int = 12_000) -> str:
    """I messaggi di Lean e di comparator, da rimandare a chi ha scritto il file.

    Include DELIBERATAMENTE anche i messaggi `info:`, cioe' l'output di
    `#check`, `#print`, `exact?` e simili: sono il modo normale di ispezionare
    una definizione, e senza di essi chi scrive la dimostrazione e' costretto a
    dedurre le definizioni provocando errori di proposito.

    Toglie invece i linter di stile dell'archivio, che sono puro rumore per un
    file temporaneo e ripetono la licenza a ogni messaggio.
    """
    utili = [b for b in _blocchi_messaggi(output) if not _RUMORE_LINTER.search(b)]

    # Toglie i duplicati esatti mantenendo l'ordine (Lean ripete lo stesso
    # messaggio una volta per ogni passata di compilazione).
    visti, unici = set(), []
    for b in utili:
        if b not in visti:
            visti.add(b)
            unici.append(b)

    testo = "\n\n".join(unici)
    if len(testo) > max_caratteri:
        testo = testo[:max_caratteri] + f"\n\n... [messaggi troncati a {max_caratteri} caratteri]"
    return testo


# ---------------------------------------------------------------------------
# Verifica di un singolo candidato
# ---------------------------------------------------------------------------

def verify(problem_id: str, candidate: Path | str, *,
           index: Optional[ProblemIndex] = None,
           timeout: Optional[int] = None,
           slot: Optional[int] = None,
           keep_workspace: bool = False,
           run_guard: bool = True) -> Result:
    """Verifica `candidate` come dimostrazione del teorema `problem_id`.

    `run_guard=False` salta il controllo sintattico preventivo. Serve SOLO ai
    test, per dimostrare che anche comparator — cioe' il giudice vero, non il
    filtro testuale — rifiuta sorry, assiomi aggiunti e native_decide. In uso
    normale va lasciato attivo.
    """
    started = time.time()
    candidate = Path(candidate)
    timeout = timeout or config.TIMEOUT_SECONDS
    checks: list[Check] = []

    def done(status: str, message: str = "", errors: str = "", raw: str = "") -> Result:
        return Result(problem=problem_id, status=status, checks=checks,
                      message=message, errors=errors,
                      duration_s=time.time() - started, raw_output=raw)

    # --- 0. l'ambiente e' a posto?
    problemi = config.check_installation()
    if problemi:
        return done(ERROR, "Ambiente non pronto:\n  - " + "\n  - ".join(problemi))

    if not candidate.is_file():
        return done(ERROR, f"File candidato non trovato: {candidate}")

    # --- 1. il problema esiste?
    try:
        index = index or ProblemIndex.load()
        problem: Problem = index.get(problem_id)
    except (KeyError, FileNotFoundError) as e:
        return done(ERROR, str(e))
    checks.append(Check("problema riconosciuto",
                        True, f"{problem.module} — categoria: {problem.category}"))

    # --- 2. l'enunciato originale e' verificabile?
    # Se l'enunciato stesso contiene un `sorry` (buco answer( ) non
    # proposizionale) allora NESSUNA dimostrazione onesta e' possibile: il tipo
    # da dimostrare e' incompleto. Va detto, non nascosto.
    if problem.statement_has_sorry:
        checks.append(Check("enunciato completo", False,
                            "l'enunciato originale contiene un buco `answer( )` non "
                            "proposizionale (una risposta da fornire, es. un numero)"))
        return done(UNVERIFIABLE,
                    "Questo problema chiede di FORNIRE UNA RISPOSTA, non solo di dimostrare "
                    "qualcosa: nell'enunciato c'e' `answer(sorry)` con un valore che non e' "
                    "una proposizione.\n"
                    "Finche' la risposta non e' fissata, il tipo da dimostrare contiene un "
                    "buco e qualunque prova dipenderebbe dall'assioma `sorryAx`.\n"
                    "Inoltre — come avvertono sia l'archivio sia comparator — riempire il buco "
                    "e dimostrare l'enunciato NON basta a dire che il problema e' risolto: "
                    "una risposta tautologica passerebbe la verifica formale pur essendo "
                    "matematicamente vuota. Serve un giudizio umano.")
    checks.append(Check("enunciato completo", True, "nessun buco `answer( )` da riempire"))

    # --- 3. controllo sintattico preventivo
    report = guard.check_file(candidate) if run_guard else guard.GuardReport()
    if not report.ok:
        dettagli = "\n".join(str(f) for f in report.findings)
        checks.append(Check("controllo sintattico preventivo", False,
                            f"{len(report.findings)} violazioni"))
        return done(REJECTED,
                    "Il file contiene costrutti vietati:\n\n" + dettagli, errors=dettagli)
    checks.append(Check("controllo sintattico preventivo", run_guard,
                        "niente sorry/admit/axiom/native_decide, nessuna opzione pericolosa, "
                        "import leciti" if run_guard else "SALTATO (modalita' di test)"))

    # --- 4. prepara il modulo Solution dentro l'albero dell'archivio
    pool = get_pool()
    owned_slot = slot is None
    if owned_slot:
        slot = pool.acquire()
    try:
        sandbox_dir = config.ARCHIVE / config.SANDBOX_SUBDIR
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        sol_name = f"S{slot}"
        sol_path = sandbox_dir / f"{sol_name}.lean"
        sol_module = f"{config.SANDBOX_MODULE_PREFIX}.{sol_name}"
        sol_path.write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")

        cfg = {
            "challenge_module": problem.module,
            "solution_module": sol_module,
            "theorem_names": [problem.theorem],
            "permitted_axioms": config.PERMITTED_AXIOMS,
        }
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.json"
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

            code, output = _run_with_timeout(
                [str(config.ELAN_BIN / "lake"), "env", str(config.COMPARATOR), str(cfg_path)],
                cwd=config.ARCHIVE, env=config.lean_env(), timeout=timeout,
            )
    finally:
        if not keep_workspace:
            try:
                sol_path.unlink(missing_ok=True)
                # rimuove anche l'artefatto compilato, per non lasciare spazzatura
                built = (config.ARCHIVE / ".lake" / "build" / "lib" / "lean"
                         / config.SANDBOX_SUBDIR / f"{sol_name}")
                for ext in (".olean", ".ilean", ".trace", ".hash", ".c", ".o"):
                    Path(str(built) + ext).unlink(missing_ok=True)
            except Exception:
                pass
        if owned_slot:
            pool.release(slot)

    # --- 5. esito
    if code == -signal.SIGKILL:
        checks.append(Check("entro il tempo massimo", False, f"superati {timeout}s"))
        return done(TIMEOUT, f"La verifica ha superato il tempo massimo di {timeout} secondi.",
                    errors=_lean_errors(output), raw=output)

    if code == 0 and "Your solution is okay!" in output:
        for nome, dettaglio in [
            ("compila senza errori", "il modulo candidato e' stato compilato da lake"),
            ("tipo identico all'originale",
             "confronto fatto sull'albero sintattico esportato da lean4export, non sul testo"),
            ("definizioni dell'archivio intatte",
             "tutte le costanti usate nell'enunciato coincidono con quelle dell'archivio"),
            ("assiomi ammessi", ", ".join(config.PERMITTED_AXIOMS)),
            ("accettato dal kernel", "termine di prova rieseguito nel kernel di Lean"),
        ]:
            checks.append(Check(nome, True, dettaglio))
        nota = "La dimostrazione e' valida."
        if problem.answer_placeholder_in_source:
            nota += (
                "\n\nATTENZIONE — questo problema e' formalizzato con `answer(sorry)`. "
                "Con l'opzione predefinita dell'archivio quel segnaposto diventa `True`, "
                "quindi l'enunciato dimostrato e' `True ↔ P`, cioe' l'affermazione che la "
                "risposta alla domanda e' SI'. La verifica formale e' corretta, ma il "
                "benchmark ha gia' scelto per te il verso della risposta: se la risposta "
                "giusta fosse NO, questo enunciato sarebbe falso e non dimostrabile.")
        return done(ACCEPTED, nota, raw=output)

    nome_controllo, spiegazione = _classify(output)
    checks.append(Check(nome_controllo, False, spiegazione))
    return done(REJECTED, spiegazione, errors=_lean_errors(output), raw=output)


# ---------------------------------------------------------------------------
# Verifica in parallelo
# ---------------------------------------------------------------------------

def verify_many(jobs: list[tuple[str, Path]], *, jobs_parallel: Optional[int] = None,
                timeout: Optional[int] = None) -> list[Result]:
    """Verifica piu' candidati, con al massimo N processi Lean insieme."""
    n = jobs_parallel or config.MAX_PARALLEL
    pool = SlotPool(n)
    index = ProblemIndex.load()
    results: list[Optional[Result]] = [None] * len(jobs)

    def worker(i: int, problem_id: str, path: Path) -> None:
        s = pool.acquire()
        try:
            results[i] = verify(problem_id, path, index=index, timeout=timeout, slot=s)
        except Exception as e:              # non lasciamo morire un thread in silenzio
            results[i] = Result(problem=problem_id, status=ERROR, message=f"eccezione: {e!r}")
        finally:
            pool.release(s)

    threads = [threading.Thread(target=worker, args=(i, p, f), daemon=True)
               for i, (p, f) in enumerate(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return [r for r in results if r is not None]


# ---------------------------------------------------------------------------
# Riga di comando
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Verifica una dimostrazione Lean contro l'enunciato originale dell'archivio.")
    ap.add_argument("problem", nargs="?", help="nome completo del teorema, es. Erdos10.erdos_10")
    ap.add_argument("file", nargs="?", help="file Lean candidato")
    ap.add_argument("--json", action="store_true", help="stampa il risultato in JSON")
    ap.add_argument("--timeout", type=int, default=None, help="secondi (default: %d)" % config.TIMEOUT_SECONDS)
    ap.add_argument("--jobs", type=int, default=None, help="processi Lean in parallelo (default: %d)" % config.MAX_PARALLEL)
    ap.add_argument("--batch", help="file JSONL con righe {\"problem\":..., \"file\":...}")
    ap.add_argument("--keep-workspace", action="store_true",
                    help="non cancellare il modulo Lean generato (per capire cosa e' successo)")
    args = ap.parse_args()

    if args.batch:
        jobs = []
        for line in Path(args.batch).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                d = json.loads(line)
                jobs.append((d["problem"], Path(d["file"])))
        results = verify_many(jobs, jobs_parallel=args.jobs, timeout=args.timeout)
        if args.json:
            print(json.dumps([json.loads(r.to_json()) for r in results], ensure_ascii=False, indent=2))
        else:
            for r in results:
                print(r.render()); print()
            ok = sum(1 for r in results if r.accepted)
            print(f"=== {ok}/{len(results)} accettati ===")
        return 0 if all(r.accepted for r in results) else 1

    if not args.problem or not args.file:
        ap.print_help()
        return 2

    r = verify(args.problem, args.file, timeout=args.timeout, keep_workspace=args.keep_workspace)
    print(r.to_json() if args.json else r.render())
    return 0 if r.accepted else 1


if __name__ == "__main__":
    sys.exit(main())
