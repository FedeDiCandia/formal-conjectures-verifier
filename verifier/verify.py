#!/usr/bin/env python3
"""
verify.py — il verifier delle dimostrazioni.

COSA FA
-------
Riceve un file Lean candidato e il name del theorem_ original dell'archive, e
risponde ACCETTATO / RIFIUTATO. Accetta only_ se TUTTE queste cose sono vere:

  1. il file non contiene costrutti vietati (controllo sintattico preventivo);
  2. il file compila senza errors;
  3. non contiene `sorry`, `admit` ne' new_ones dichiarazioni `axiom`;
  4. gli axioms usati dal theorem_ sono only_ propext, Classical.choice, Quot.sound;
  5. il TIPO del theorem_ e' identico a quello dell'statement original — il
     confronto avviene sull'albero sintattico di Lean esportato, non sul text;
  6. il file non ridefinisce ne' modifica le definizioni dell'archive usate
     nell'statement;
  7. il termine di trial e' accepted_one da one_ riesecuzione nel kernel di Lean;
  8. non usa opzioni che disattivano i controlli del kernel.

COME LO FA
----------
I points 2, 4, 5, 6, 7 non sono implementati a mano: li delega a `comparator`
(https://github.com/leanprover/comparator), il "giudice" scritto dal Lean FRO
proprio per validare le dimostrazioni prodotte da modelli linguistici.
comparator compila i two modules, li esporta in format_ text con `lean4export`
(senza mai fidarsi degli .olean), compare gli enunciati, controlla gli axioms
e infine RIESEGUE tutto nel kernel di Lean. E' molto piu' affidabile di
qualunque cosa potremmo scrivere noi.

I points 1, 3 e 8 sono il controllo sintattico di `guard.py`, che serve da difesa
in depth' (vedi il commento in cima a quel file).

USO
---
    python3 verifier/verify.py NOME_TEOREMA FILE.lean
    python3 verifier/verify.py NOME_TEOREMA FILE.lean --json
    python3 verifier/verify.py --batch jobs.jsonl --jobs 4
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
import fingerprint as fingerprint_module
import negation
import sandbox
from index import ProblemIndex, Problem


# ---------------------------------------------------------------------------
# Risultato
# ---------------------------------------------------------------------------

#: Esiti possibili.
#: Modalita' di check.
#:   stretta      -> si check l'statement dell'archive come e' scritto.
#:   confutazione -> si check la NEGAZIONE di un problem con `answer(sorry)`
#:                   proposizionale, against one_ challenge generata da noi (fidata).
#:                   Vedi verifier/negation.py.
STRICT = "stretta"
REFUTATION = "confutazione"

ACCEPTED = "ACCETTATO"
REJECTED = "RIFIUTATO"
ERROR = "ERRORE"
TIMEOUT = "TIMEOUT"
UNVERIFIABLE = "NON_VERIFICABILE"


@dataclass
class Check:
    """Un singolo controllo, con il suo result."""
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
    #: errors di compilazione o messages di comparator, useful all'agent
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
            out += f"\n\n--- messages di Lean / comparator ---\n{self.errors}"
        return out


# ---------------------------------------------------------------------------
# Gestione degli "slot": limita how_many processi Lean girano insieme
# ---------------------------------------------------------------------------

class SlotPool:
    """Una queue di N posti. Ogni check ne occupa one e usa il proprio name di
    module Lean, cosi' two checks in parallelo non si pestano i piedi."""

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

#: Moduli di challenge gia' portati in even, e il lock_ che serializza l'operazione.
#: Serve perche' portare in even un module MODIFICA l'archive, e se lo facesse
#: one_ check mentre un'altra ne sta prendendo l'fingerprint la seconda
#: segnalerebbe (giustamente) che l'archive e' cambiato. Succedeva davvero.
_ready_challenges: set[str] = set()
_challenges_lock = threading.Lock()


def prepare_challenge(module: str, timeout: int) -> tuple[bool, str]:
    """Compila il module dell'statement original, FUORI dalla sandbox.

    E' legittimo: la challenge e' un file dell'archive, o generato da noi dal suo
    source_text, quindi fidato. Lo dice also_ il README di comparator ("as
    Challenge is trusted, both the sandbox and lean4export step for Challenge
    are not necessary").

    E serve: inside la sandbox `lake` non puo' rimuovere gli artefacts
    dell'archive, quindi se il module non e' gia' in even la compilazione si
    ferma con "failed to remove output artifacts".

    Si fa one_ volta per module, below lock_.
    """
    with _challenges_lock:
        if module in _ready_challenges:
            return True, ""
        result, output = _run_with_timeout(
            [str(config.ELAN_BIN / "lake"), "build", module],
            cwd=config.ARCHIVE, env=config.lean_env(), timeout=timeout)
        if result == 0:
            _ready_challenges.add(module)
            return True, output
        return False, output


def get_pool(size: Optional[int] = None) -> SlotPool:
    global _default_pool
    with _pool_lock:
        if _default_pool is None:
            _default_pool = SlotPool(size or config.MAX_PARALLEL)
        return _default_pool


# ---------------------------------------------------------------------------
# Esecuzione di comparator
# ---------------------------------------------------------------------------

def _run_with_timeout(cmd: list[str], cwd: Path, env: dict, timeout: int,
                      sandbox_profile: Optional[Path] = None) -> tuple[int, str]:
    """Esegue un command con timeout, uccidendo l'INTERO albero di processi.

    Serve perche' comparator lancia `lake`, che lancia `lean`: uccidere only_ il
    padre lascerebbe i figli a consumare CPU per sempre. `start_new_session`
    mette tutto in un group di processi che possiamo terminare in block.
    """
    if sandbox_profile is not None:
        cmd = sandbox.wrap(cmd, sandbox_profile)
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


def _clean_leftovers(folder: Path, slot: int) -> None:
    """Toglie gli artefacts rimasti dal PROPRIO slot in esecuzioni finite male.

    Solo il proprio: gli altri slot possono essere in uso da checks che
    girano in parallelo, e cancellarne i file mentre lavorano fa fallire la
    compilazione con "failed to remove output artifacts". E' successo davvero,
    su all_of e dodici le checks di un'esecuzione.
    """
    built_ = config.ARCHIVE / ".lake" / "build"
    for name in (f"S{slot}", f"Sfida{slot}", f"E{slot}"):
        source_text = folder / f"{name}.lean"
        artefacts = [Path(str(built_ / branch / config.SANDBOX_SUBDIR / name) + ext)
                     for branch in ("lib/lean", "ir")
                     for ext in (".olean", ".ilean", ".trace", ".hash", ".c",
                                 ".o", ".c.hash", ".setup.json", ".olean.hash",
                                 ".ilean.hash")]
        # Se il source_text non c'e' ma gli artefacts si', lake si confonde:
        # si toglie tutto e si riparte clean_one.
        if not source_text.is_file():
            for a in artefacts:
                a.unlink(missing_ok=True)


def _classify(output: str) -> tuple[str, str]:
    """Traduce l'output di comparator in (name del controllo failed, explanation)."""
    m = re.search(r"Illegal axiom detected: '([^']+)'", output)
    if m:
        ax = m.group(1)
        spiega = {
            "sorryAx": "la dimostrazione contiene un `sorry` (un buco), diretto o "
                       "ereditato da un lemma ausiliario",
            "Lean.ofReduceBool": "e' state usato `native_decide`, che si fida del "
                                 "compilatore invece che del kernel",
            "Lean.trustCompiler": "e' state chiesto di fidarsi del compilatore",
        }.get(ax, f"il theorem_ dipende dall'assioma `{ax}`, che non e' fra quelli permissions "
                  f"({', '.join(config.PERMITTED_AXIOMS)})")
        return "axioms permitted", f"assioma illecito `{ax}`: {spiega}"

    if "theorem statement do not match" in output:
        return ("kind_ identico all'original",
                "l'statement dimostrato NON e' identico a quello dell'archive. "
                "Puo' essere un statement piu' debole, con ipotesi in piu', o "
                "semplicemente scritto in way che Lean elabora diversamente.")
    if "constant kind don't match" in output:
        return ("kind_ identico all'original",
                "nel candidato la declaration ha one_ kind diversa (es. `def` invece di `theorem`)")
    if "Solution constant is not a theorem" in output:
        return ("kind_ identico all'original", "nel candidato la declaration non e' un theorem_")
    if "Const does not match between challenge and target" in output or \
       "does not match between challenge" in output:
        m2 = re.search(r"target '([^']+)'", output)
        which = f" (`{m2.group(1)}`)" if m2 else ""
        return ("definizioni dell'archive intatte",
                f"il candidato RIDEFINISCE in way diverso one_ definition usata "
                f"nell'statement{which}. L'statement sembra uguale ma parla di other.")
    if "Const not found in solution" in output or "Constant not found in solution" in output:
        m2 = re.search(r"in solution:? '([^']+)'", output)
        which = f" `{m2.group(1)}`" if m2 else ""
        return ("theorem_ presente", f"il candidato non dichiara{which}. Il name deve "
                                    f"coincidere ESATTAMENTE con quello dell'archive, "
                                    f"namespace compreso.")
    if "kernel rejected the solution" in output:
        return ("accepted_one dal kernel", "il kernel di Lean ha rifiutato il termine di trial")
    if "error:" in output:
        return ("compila senza errors", "il file non compila")
    if "Child exited with" in output:
        return ("compila senza errors", "la compilazione e' fallita")
    return ("check di comparator", "comparator ha rifiutato il candidato")


#: Righe con cui `lake` annuncia lo state: non sono messages di Lean.
_LAKE_STATE = re.compile(r"^(Building |Exporting |Build completed|Running |"
                         r"[✔⚠✖ℹ] |info: \[|error: build failed|trace:)")

#: Inizio di un message di Lean. Il message prosegue sulle lines successive
#: finche' non ne comincia un other o non compare one_ line di state di lake.
_MESSAGE_START = re.compile(r"^(info|warning|error): ")

#: Linter di STILE dell'archive: si lamentano che il nostro module temporaneo
#: non ha l'header di copyright, non ha il docstring di module, ecc.
#: Sono irrilevanti — il file candidato non e' un contributo all'archive — e
#: ripetono quindici lines di licenza a ogni message, inondando il context.
_LINTER_NOISE = re.compile(
    r"linter\.style\.(copyright|namespace|ams_attribute|category_attribute|moduleDocstring)"
    r"|The copyright header is incorrect"
    r"|missing a module docstring")

#: Messaggi di comparator: lines isolate, senza il prefisso di Lean.
_COMPARATOR_MESSAGE = re.compile(
    r"Illegal axiom|do not match|does not match|not found in|Constant not found|"
    r"rejected the solution|uncaught exception|kernel accepts")


def _message_blocks(output: str) -> list[str]:
    """Ricompone i messages di Lean, che sono blocks su piu' lines."""
    blocks: list[str] = []
    current: list[str] = []

    def close_():
        if current:
            blocks.append("\n".join(current).rstrip())
            current.clear()

    for line in output.split("\n"):
        if _MESSAGE_START.match(line):
            close_()
            current.append(line.rstrip())
        elif _LAKE_STATE.match(line):
            close_()
        elif current:
            current.append(line.rstrip())
        elif _COMPARATOR_MESSAGE.search(line):
            blocks.append(line.rstrip())
    close_()
    return blocks


def _lean_errors(output: str, max_chars: int = 40_000) -> str:
    """I messages di Lean e di comparator, da rimandare a chi ha scritto il file.

    Include DELIBERATAMENTE also_ i messages `info:`, cioe' l'output di
    `#check`, `#print`, `exact?` e simili: sono il way normale di ispezionare
    one_ definition, e senza di essi chi scrive la dimostrazione e' costretto a
    dedurre le definizioni provocando errors di proposito.

    Toglie invece i linter di stile dell'archive, che sono puro rumore per un
    file temporaneo e ripetono la licenza a ogni message.
    """
    useful = [b for b in _message_blocks(output) if not _LINTER_NOISE.search(b)]

    # Toglie i duplicati esatti mantenendo l'order (Lean ripete lo stesso
    # message one_ volta per ogni passata di compilazione).
    seen, unique_ = set(), []
    for b in useful:
        if b not in seen:
            seen.add(b)
            unique_.append(b)

    text = "\n\n".join(unique_)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n... [messages troncati a {max_chars} chars]"
    return text


# ---------------------------------------------------------------------------
# Verifica di un singolo candidato
# ---------------------------------------------------------------------------

def _tool_error(output: str) -> str | None:
    """Riconosce i fallimenti che riguardano GLI STRUMENTI, non il candidato.

    Misurato il 12 settembre 2026: verificando A105020 sullo snapshot `main` (Lean
    4.33.1) con il `lean4export` per Lean 4.27, comparator si e' fermato con
    `failed to read file ... incompatible header`, e il report diceva «la
    compilazione e' fallita» con result RIFIUTATO. Era falso: il candidato non era mai
    state giudicato. Un fault degli tools deve risultare ERRORE, con la cause.
    """
    if "incompatible header" in output:
        return ("LA VERIFICA NON E' AVVENUTA: comparator ha found file .olean compiled "
                "con one_ versione di Lean diversa da quella dei suoi tools "
                "(`incompatible header`). Non dice niente sul candidato.\n\n"
                "Per lo snapshot `main` (Lean 4.33.1) serve "
                "FCS_LEAN4EXPORT=external/lean4export-433/.lake/build/bin/lean4export.")
    return None


def verify(problem_id: str, candidate: Path | str, *,
           index: Optional[ProblemIndex] = None,
           timeout: Optional[int] = None,
           slot: Optional[int] = None,
           keep_workspace: bool = False,
           run_guard: bool = True,
           mode: str = STRICT) -> Result:
    """Verifica `candidate` come dimostrazione del theorem_ `problem_id`.

    `mode=REFUTATION` check la NEGAZIONE del problem invece del
    problem: serve per i 107 problems open_ formalizzati con `answer(sorry)`
    proposizionale, per i which_ones l'statement dell'archive afferma che la
    answer e' "si'" e one_ confutazione non avrebbe other way di essere
    verificata. Vedi verifier/negation.py.

    `run_guard=False` salta il controllo sintattico preventivo. Serve SOLO ai
    test, per dimostrare che also_ comparator — cioe' il giudice vero, non il
    filtro testuale — rifiuta sorry, axioms added e native_decide. In uso
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

    # --- 0. l'environment e' a slot_?
    problems = config.check_installation()
    if problems:
        return done(ERROR, "Ambiente non ready:\n  - " + "\n  - ".join(problems))

    if not candidate.is_file():
        return done(ERROR, f"File candidato non found: {candidate}")

    # --- 1. il problem esiste?
    try:
        index = index or ProblemIndex.load()
        problem: Problem = index.get(problem_id)
    except (KeyError, FileNotFoundError) as e:
        return done(ERROR, str(e))
    checks.append(Check("problem riconosciuto",
                        True, f"{problem.module} — categoria: {problem.category}"))

    # --- 1bis. mode' di check
    if mode not in (STRICT, REFUTATION):
        return done(ERROR, f"mode' sconosciuta: {mode!r} "
                           f"(sono {STRICT!r} e {REFUTATION!r})")
    negated_challenge = None
    target_ = problem.theorem      # il theorem_ che comparator deve confrontare
    allowed_module = None           # un import in piu', only_ per the route type_of%
    if mode == REFUTATION:
        ok, _perche = negation.can_be_negated(problem)
        try:
            negated_challenge = (negation.generate(problem) if ok
                            else negation.generate_by_kind(problem))
        except negation.NotNegatable as e:
            checks.append(Check("il problem ammette one_ confutazione", False, str(e)))
            return done(ERROR, f"Non si puo' costruire la challenge negata: {e}")
        target_ = negated_challenge.target_ or problem.theorem
        if negated_challenge.route == "answer":
            detail = ("challenge negata generata dal source_text dell'archive: "
                         "`answer(sorry)` sostituito da `answer(False)`, quindi "
                         "l'statement passa da `True ↔ P` a `False ↔ P`, cioe' `¬P`")
        else:
            allowed_module = problem.module
            detail = (f"challenge negata generata con `type_of%`: il target_ e' "
                         f"`{target_}`, cioe' `¬ (type_of% @{problem.theorem})`. "
                         f"Al candidato e' permesso importare `{problem.module}` per "
                         f"leggere l'statement; appoggiarsi alla dimostrazione "
                         f"dell'archive, che e' un `sorry`, viene rifiutato dal "
                         f"controllo degli axioms")
        checks.append(Check("il problem ammette one_ confutazione", True, detail))

    # --- 2. l'statement original e' verificabile?
    # Se l'statement stesso contiene un `sorry` (buco answer( ) non
    # proposizionale) allora NESSUNA dimostrazione onesta e' possibile: il kind_
    # da dimostrare e' incompleto. Va detto, non nascosto.
    if problem.statement_has_sorry:
        checks.append(Check("statement full_", False,
                            "l'statement original contiene un buco `answer( )` non "
                            "proposizionale (one_ answer da fornire, es. un number)"))
        return done(UNVERIFIABLE,
                    "Questo problem chiede di FORNIRE UNA RISPOSTA, non only_ di dimostrare "
                    "qualcosa: nell'statement c'e' `answer(sorry)` con un value_ che non e' "
                    "one_ proposizione.\n"
                    "Finche' la answer non e' fissata, il kind_ da dimostrare contiene un "
                    "buco e qualunque trial dipenderebbe dall'assioma `sorryAx`.\n"
                    "Inoltre — come avvertono sia l'archive sia comparator — riempire il buco "
                    "e dimostrare l'statement NON basta a dire che il problem e' solved_one: "
                    "one_ answer tautologica passerebbe la check formale pur essendo "
                    "matematicamente vuota. Serve un giudizio umano.")
    checks.append(Check("statement full_", True, "nessun buco `answer( )` da riempire"))

    # --- 3. controllo sintattico preventivo
    report = (guard.check_file(candidate, allowed_module=allowed_module)
              if run_guard else guard.GuardReport())
    if not report.ok:
        details = "\n".join(str(f) for f in report.findings)
        checks.append(Check("controllo sintattico preventivo", False,
                            f"{len(report.findings)} violations"))
        return done(REJECTED,
                    "Il file contiene costrutti vietati:\n\n" + details, errors=details)
    checks.append(Check("controllo sintattico preventivo", run_guard,
                        "niente sorry/admit/axiom/native_decide, nessuna opzione pericolosa, "
                        "import leciti" if run_guard else "SALTATO (mode' di test)"))

    # --- 4. prepara il module Solution inside l'albero dell'archive
    pool = get_pool()
    owned_slot = slot is None
    if owned_slot:
        slot = pool.acquire()
    try:
        sandbox_dir = config.ARCHIVE / config.SANDBOX_SUBDIR
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Ripulisce gli avanzi di esecuzioni interrotte. Se un processo viene
        # ucciso a meta', lascia il source_text del module temporaneo senza i suoi
        # artefacts (o viceversa), e al giro after `lake` si ferma con
        # "no such file or directory". Costa niente e toglie di mezzo one_
        # classe intera di guasti misteriosi.
        _clean_leftovers(sandbox_dir, slot)

        sol_name = f"S{slot}"
        sol_path = sandbox_dir / f"{sol_name}.lean"
        sol_module = f"{config.SANDBOX_MODULE_PREFIX}.{sol_name}"
        sol_path.write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")

        # --- which module fa da Challenge
        challenge_path = None
        if negated_challenge is None:
            challenge_module = problem.module          # l'archive, intatto
        else:
            challenge_name = f"Sfida{slot}"
            challenge_path = sandbox_dir / f"{challenge_name}.lean"
            challenge_path.write_text(negated_challenge.text, encoding="utf-8")
            challenge_module = f"{config.SANDBOX_MODULE_PREFIX}.{challenge_name}"
            checks.append(Check("la challenge negata e' stata generata", True, challenge_module))

        cfg = {
            "challenge_module": challenge_module,
            "solution_module": sol_module,
            "theorem_names": [target_],
            "permitted_axioms": config.PERMITTED_AXIOMS,
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cfg_path = tmp_dir / "config.json"
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

            # --- isolamento della compilazione
            profile = None
            if config.USE_SANDBOX and sandbox.available():
                # le folders devono esistere PRIMA: inside la sandbox non si
                # puo' scrivere nella folder genitore per crearle
                for d in sandbox.writable_dirs(
                        config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir):
                    d.mkdir(parents=True, exist_ok=True)
                profile = sandbox.write_profile(
                    tmp_dir / "check.sb",
                    sandbox.writable_dirs(config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir),
                    config.ROOT)
                checks.append(Check("compilazione isolata", True,
                                    "sandbox-exec: niente rete, write_op only_ nella "
                                    "folder del module temporaneo"))
            elif config.USE_SANDBOX:
                checks.append(Check("compilazione isolata", False,
                                    "sandbox-exec non available su questo system: la "
                                    "compilazione del candidato NON e' isolata"))

            # --- si porta in even il module della SFIDA (vedi prepare_challenge)
            ready, prep_output = prepare_challenge(challenge_module, timeout)
            if not ready:
                checks.append(Check("module della challenge ready", False,
                                    "non si riesce a compilare l'statement original"))
                return done(ERROR,
                            "Non riesco a portare in even il module dell'statement "
                            "original. E' un problem dell'archive o della sua "
                            "compilazione, non del candidato.",
                            errors=_lean_errors(prep_output), raw=prep_output)

            # --- fingerprint dell'archive PRIMA della check
            fingerprint_before = None
            if config.CHECK_FINGERPRINT:
                fingerprint_before = fingerprint_module.compute(
                    config.ARCHIVE, exclude=Path(config.SANDBOX_SUBDIR).name)

            environment = config.lean_env()
            environment["TMPDIR"] = str(tmp_dir)

            code, output = _run_with_timeout(
                [str(config.ELAN_BIN / "lake"), "env", str(config.COMPARATOR), str(cfg_path)],
                cwd=config.ARCHIVE, env=environment, timeout=timeout,
                sandbox_profile=profile,
            )

            # --- fingerprint DOPO: l'archive deve essere intatto
            if fingerprint_before is not None:
                differences = fingerprint_module.compare(
                    fingerprint_before,
                    fingerprint_module.compute(config.ARCHIVE,
                                            exclude=Path(config.SANDBOX_SUBDIR).name))
                if differences:
                    checks.append(Check("archive intatto after la check", False,
                                        "; ".join(differences)))
                    return done(ERROR,
                                "LA VERIFICA NON E' ATTENDIBILE: compilare il file "
                                "candidato ha modificato l'archive.\n\n"
                                + "\n".join("  - " + d for d in differences) +
                                "\n\nComparator compare la solution con l'statement "
                                "che legge dai file compiled dell'archive. Se quei file "
                                "cambiano, il confronto avviene against un problem alterato "
                                "e l'result non vuol dire niente (assunto 2 del README di "
                                "comparator). Ripristina l'archive con:\n"
                                f"  cd {config.ARCHIVE} && git checkout . && lake build",
                                errors=_lean_errors(output), raw=output)
                checks.append(Check("archive intatto after la check", True,
                                    f"{fingerprint_before.n_content_files} file dell'archive "
                                    f"invariati (hash del content) e "
                                    f"{fingerprint_before.n_metadata_files} file delle dipendenze "
                                    f"invariati (size e data)"))
    finally:
        if not keep_workspace:
            try:
                sol_path.unlink(missing_ok=True)
                if challenge_path is not None:
                    challenge_path.unlink(missing_ok=True)
                # rimuove also_ l'artefatto compilato, per non lasciare spazzatura
                built = (config.ARCHIVE / ".lake" / "build" / "lib" / "lean"
                         / config.SANDBOX_SUBDIR / f"{sol_name}")
                for ext in (".olean", ".ilean", ".trace", ".hash", ".c", ".o"):
                    Path(str(built) + ext).unlink(missing_ok=True)
            except Exception:
                pass
        if owned_slot:
            pool.release(slot)

    # --- 5. result
    if code == -signal.SIGKILL:
        checks.append(Check("entro il tempo maximum", False, f"passed_ {timeout}s"))
        return done(TIMEOUT, f"La check ha passed_one il tempo maximum di {timeout} seconds.",
                    errors=_lean_errors(output), raw=output)

    if code == 0 and "Your solution is okay!" in output:
        for name, detail in [
            ("compila senza errors", "il module candidato e' state compilato da lake"),
            ("kind_ identico all'original",
             "confronto fatto sull'albero sintattico esportato da lean4export, non sul text"),
            ("definizioni dell'archive intatte",
             "all_of le costanti usate nell'statement coincidono con quelle dell'archive"),
            ("axioms permitted", ", ".join(config.PERMITTED_AXIOMS)),
            ("accepted_one dal kernel", "termine di trial rieseguito nel kernel di Lean"),
        ]:
            checks.append(Check(name, True, detail))
        if negated_challenge is not None:
            if negated_challenge.route == "answer":
                explanation = (
                    f"E' state dimostrato `False ↔ P`, cioe' `¬P`: la answer alla "
                    f"domanda posta da {problem.theorem} e' NO.\n\n"
                    "Questo CONTRADDICE l'statement dell'archive, che con "
                    "`answer(sorry)` afferma che la answer e' si'. Se la "
                    "confutazione e' corretta, la formalizzazione dell'archive va "
                    "aggiornata a `answer(False)`.")
            else:
                explanation = (
                    f"E' state dimostrato `{target_}`, cioe' "
                    f"`¬ (type_of% @{problem.theorem})`: l'statement dell'archive, "
                    f"come e' formalizzato, e' FALSO.\n\n"
                    "Due letture possibili, e vanno distinte before di annunciare "
                    "qualcosa: o la congettura e' falsa, o la formalizzazione non e' "
                    "fedele alla source_ original. Il second_ caso e' il piu' frequente.")
            return done(ACCEPTED,
                        "REFUTATION VALIDA.\n\n" + explanation + "\n\n"
                        "Applicare il protocollo di docs/04-protocollo-ritrovamenti.md "
                        "before di crederci: ricontrollo con un program indipendente, "
                        "confronto con la source_ original, ricerca dello state noto in "
                        "letteratura.", raw=output)
        note = "La dimostrazione e' valida."
        if problem.answer_placeholder_in_source:
            note += (
                "\n\nATTENZIONE — questo problem e' formalizzato con `answer(sorry)`. "
                "Con l'opzione predefinita dell'archive quel segnaposto diventa `True`, "
                "quindi l'statement dimostrato e' `True ↔ P`, cioe' l'affermazione che la "
                "answer alla domanda e' SI'. La check formale e' corretta, ma il "
                "benchmark ha gia' chosen_one per te il verso della answer: se la answer "
                "giusta fosse NO, questo statement sarebbe falso e non dimostrabile.")
        return done(ACCEPTED, note, raw=output)

    fault = _tool_error(output)
    if fault:
        checks.append(Check("tools coerenti con l'archive", False,
                            "file .olean con header incompatibile"))
        return done(ERROR, fault, errors=_lean_errors(output), raw=output)
    check_name, explanation = _classify(output)
    checks.append(Check(check_name, False, explanation))
    return done(REJECTED, explanation, errors=_lean_errors(output), raw=output)


# ---------------------------------------------------------------------------
# Verifica di un theorem_ NUOVO, con one_ challenge scritta a mano
# ---------------------------------------------------------------------------

_RE_CHALLENGE_AXIOM = re.compile(r"^\s*(?:private\s+|protected\s+)?axiom\b", re.MULTILINE)


def verify_free(challenge_text: str, candidate: Path | str, theorems: list[str], *,
                  allowed_modules: tuple[str, ...] = (),
                  timeout: Optional[int] = None,
                  slot: Optional[int] = None,
                  keep_workspace: bool = False) -> Result:
    """Verifica theorems che NON stanno nell'archive, against one_ challenge scritta a mano.

    `verify` compare un candidato con un statement dell'archive. Qui la challenge
    (il module Challenge di comparator) la fornisce chi chiede la check: gli
    enunciati dei theorems `theorems`, con `sorry` come dimostrazione. Il candidato deve
    dichiarare gli stessi theorems e dimostrarli. Il resto e' la stessa catena di
    `verify`: controllo sintattico, compilazione isolata, confronto degli enunciati
    elaborati, axioms permitted, riesecuzione nel kernel, fingerprint dell'archive.

    `allowed_modules` sono i modules dell'archive che il candidato puo' importare per
    leggere definizioni ed enunciati. Appoggiarsi alle loro dimostrazioni, che per i
    problems open_ sono `sorry`, viene rifiutato dal controllo degli axioms: e' lo
    stesso argomento della away `type_of%` delle confutazioni.

    L'AVVERTENZA CHE CONTA: comparator garantisce che il candidato dimostri
    esattamente gli enunciati della challenge. Se la challenge enuncia la cosa sbagliata, la
    check certifica la cosa sbagliata. La challenge va letta da un essere umano, ed e'
    per questo che deve restare corta.
    """
    started = time.time()
    candidate = Path(candidate)
    timeout = timeout or config.TIMEOUT_SECONDS
    checks: list[Check] = []
    label = "challenge libera: " + ", ".join(theorems)

    def done(status: str, message: str = "", errors: str = "", raw: str = "") -> Result:
        return Result(problem=label, status=status, checks=checks,
                      message=message, errors=errors,
                      duration_s=time.time() - started, raw_output=raw)

    problems = config.check_installation()
    if problems:
        return done(ERROR, "Ambiente non ready:\n  - " + "\n  - ".join(problems))
    if not candidate.is_file():
        return done(ERROR, f"File candidato non found: {candidate}")
    if not theorems:
        return done(ERROR, "nessun theorem_ da verificare")
    if _RE_CHALLENGE_AXIOM.search(challenge_text):
        return done(ERROR, "la challenge dichiara un assioma: one_ challenge contiene only_ enunciati")
    missing_ = [t for t in theorems
                if not re.search(r"\btheorem\s+(?:\S*\.)?" + re.escape(t.rsplit(".", 1)[-1])
                                 + r"\b", challenge_text)]
    if missing_:
        return done(ERROR, "la challenge non dichiara: " + ", ".join(missing_))
    checks.append(Check("challenge ben formata", True,
                        f"{len(theorems)} enunciati, nessun assioma dichiarato"))

    report = guard.check_file(candidate, allowed_module=tuple(allowed_modules) or None)
    if not report.ok:
        details = "\n".join(str(f) for f in report.findings)
        checks.append(Check("controllo sintattico preventivo", False,
                            f"{len(report.findings)} violations"))
        return done(REJECTED, "Il file contiene costrutti vietati:\n\n" + details,
                    errors=details)
    checks.append(Check("controllo sintattico preventivo", True,
                        "niente sorry/admit/axiom/native_decide; modules dell'archive "
                        "importabili: " + (", ".join(allowed_modules) or "nessuno")))

    pool = get_pool()
    owned_slot = slot is None
    if owned_slot:
        slot = pool.acquire()
    sandbox_dir = config.ARCHIVE / config.SANDBOX_SUBDIR
    sol_name, challenge_name = f"S{slot}", f"Sfida{slot}"
    sol_path = sandbox_dir / f"{sol_name}.lean"
    challenge_path = sandbox_dir / f"{challenge_name}.lean"
    code, output = None, ""
    try:
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        _clean_leftovers(sandbox_dir, slot)
        sol_path.write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")
        challenge_path.write_text(challenge_text, encoding="utf-8")
        sol_module = f"{config.SANDBOX_MODULE_PREFIX}.{sol_name}"
        challenge_module = f"{config.SANDBOX_MODULE_PREFIX}.{challenge_name}"
        cfg = {"challenge_module": challenge_module, "solution_module": sol_module,
               "theorem_names": list(theorems),
               "permitted_axioms": config.PERMITTED_AXIOMS}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cfg_path = tmp_dir / "config.json"
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

            profile = None
            if config.USE_SANDBOX and sandbox.available():
                for d in sandbox.writable_dirs(
                        config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir):
                    d.mkdir(parents=True, exist_ok=True)
                profile = sandbox.write_profile(
                    tmp_dir / "check.sb",
                    sandbox.writable_dirs(config.ARCHIVE, config.SANDBOX_SUBDIR, tmp_dir),
                    config.ROOT)
                checks.append(Check("compilazione isolata", True,
                                    "sandbox-exec: niente rete, write_op only_ nella "
                                    "folder del module temporaneo"))
            elif config.USE_SANDBOX:
                checks.append(Check("compilazione isolata", False,
                                    "sandbox-exec non available: compilazione NON isolata"))

            ready, prep_output = prepare_challenge(challenge_module, timeout)
            if not ready:
                checks.append(Check("module della challenge ready", False,
                                    "la challenge non compila"))
                return done(ERROR, "La SFIDA non compila: va corretto il text della challenge, "
                                   "non il candidato.",
                            errors=_lean_errors(prep_output), raw=prep_output)
            checks.append(Check("module della challenge ready", True, challenge_module))

            fingerprint_before = None
            if config.CHECK_FINGERPRINT:
                fingerprint_before = fingerprint_module.compute(
                    config.ARCHIVE, exclude=Path(config.SANDBOX_SUBDIR).name)
            environment = config.lean_env()
            environment["TMPDIR"] = str(tmp_dir)
            code, output = _run_with_timeout(
                [str(config.ELAN_BIN / "lake"), "env", str(config.COMPARATOR), str(cfg_path)],
                cwd=config.ARCHIVE, env=environment, timeout=timeout,
                sandbox_profile=profile,
            )
            if fingerprint_before is not None:
                differences = fingerprint_module.compare(
                    fingerprint_before,
                    fingerprint_module.compute(config.ARCHIVE,
                                            exclude=Path(config.SANDBOX_SUBDIR).name))
                if differences:
                    checks.append(Check("archive intatto after la check", False,
                                        "; ".join(differences)))
                    return done(ERROR,
                                "LA VERIFICA NON E' ATTENDIBILE: l'archive e' cambiato "
                                "durante la check.\n"
                                + "\n".join("  - " + d for d in differences),
                                errors=_lean_errors(output), raw=output)
                checks.append(Check("archive intatto after la check", True,
                                    f"{fingerprint_before.n_content_files} file dell'archive e "
                                    f"{fingerprint_before.n_metadata_files} delle dipendenze invariati"))
    finally:
        if not keep_workspace:
            for name, path in ((sol_name, sol_path), (challenge_name, challenge_path)):
                try:
                    path.unlink(missing_ok=True)
                    built = (config.ARCHIVE / ".lake" / "build" / "lib" / "lean"
                             / config.SANDBOX_SUBDIR / name)
                    for ext in (".olean", ".ilean", ".trace", ".hash", ".c", ".o"):
                        Path(str(built) + ext).unlink(missing_ok=True)
                except Exception:
                    pass
        if owned_slot:
            pool.release(slot)

    if code == -signal.SIGKILL:
        checks.append(Check("entro il tempo maximum", False, f"passed_ {timeout}s"))
        return done(TIMEOUT, f"La check ha passed_one il tempo maximum di {timeout} seconds.",
                    errors=_lean_errors(output), raw=output)
    if code == 0 and "Your solution is okay!" in output:
        for name, detail in [
            ("compila senza errors", "il module candidato e' state compilato da lake"),
            ("enunciati identici alla challenge",
             "confronto sull'albero sintattico esportato da lean4export, non sul text"),
            ("definizioni usate intatte",
             "le costanti usate negli enunciati coincidono con quelle della challenge e "
             "dell'archive"),
            ("axioms permitted", ", ".join(config.PERMITTED_AXIOMS)),
            ("accepted_one dal kernel", "termini di trial rieseguiti nel kernel di Lean"),
        ]:
            checks.append(Check(name, True, detail))
        return done(ACCEPTED,
                    "Tutti gli enunciati della challenge sono dimostrati.\n\n"
                    "Quello che la check NON dice: che la challenge enunci la cosa giusta. "
                    "Va letta.", raw=output)
    fault = _tool_error(output)
    if fault:
        checks.append(Check("tools coerenti con l'archive", False,
                            "file .olean con header incompatibile"))
        return done(ERROR, fault, errors=_lean_errors(output), raw=output)
    check_name, explanation = _classify(output)
    checks.append(Check(check_name, False, explanation))
    return done(REJECTED, explanation, errors=_lean_errors(output), raw=output)


# ---------------------------------------------------------------------------
# Verifica in parallelo
# ---------------------------------------------------------------------------

def verify_many(jobs: list[tuple[str, Path]], *, jobs_parallel: Optional[int] = None,
                timeout: Optional[int] = None) -> list[Result]:
    """Verifica piu' candidates, con al maximum N processi Lean insieme."""
    n = jobs_parallel or config.MAX_PARALLEL
    pool = SlotPool(n)
    index = ProblemIndex.load()

    # Tutte le sfide si portano in even PRIMA di cominciare: e' l'unico step
    # che modifica l'archive, e farlo mentre le checks girano in parallelo
    # falsa il controllo dell'fingerprint.
    for problema_id, _ in jobs:
        try:
            prepare_challenge(index.get(problema_id).module, timeout or config.TIMEOUT_SECONDS)
        except KeyError:
            pass
    results: list[Optional[Result]] = [None] * len(jobs)

    def worker(i: int, problem_id: str, path: Path) -> None:
        s = pool.acquire()
        try:
            results[i] = verify(problem_id, path, index=index, timeout=timeout, slot=s)
        except Exception as e:              # non lasciamo morire un thread in silence
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
# Riga di command
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Verifica one_ dimostrazione Lean against l'statement original dell'archive.")
    ap.add_argument("problem", nargs="?", help="name full_ del theorem_, es. Erdos10.erdos_10")
    ap.add_argument("file", nargs="?", help="file Lean candidato")
    ap.add_argument("--json", action="store_true", help="show il result_value in JSON")
    ap.add_argument("--timeout", type=int, default=None, help="seconds (default: %d)" % config.TIMEOUT_SECONDS)
    ap.add_argument("--jobs", type=int, default=None, help="processi Lean in parallelo (default: %d)" % config.MAX_PARALLEL)
    ap.add_argument("--batch", help="file JSONL con lines {\"problem\":..., \"file\":...}")
    ap.add_argument("--confutazione", action="store_true",
                    help="check la NEGAZIONE del problem (only_ per i problems con "
                         "answer(sorry) proposizionale): l'statement diventa `False ↔ P`")
    ap.add_argument("--keep-workspace", action="store_true",
                    help="non cancellare il module Lean generato (per capire cosa e' successo)")
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

    r = verify(args.problem, args.file, timeout=args.timeout,
               keep_workspace=args.keep_workspace,
               mode=REFUTATION if args.confutazione else STRICT)
    print(r.to_json() if args.json else r.render())
    return 0 if r.accepted else 1


if __name__ == "__main__":
    sys.exit(main())
