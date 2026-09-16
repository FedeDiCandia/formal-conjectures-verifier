"""
Nasconde le dimostrazioni gia' presenti nell'archive.

Per collaudare onestamente un agent su un problem gia' solved bisogna
togliergli la answer. Questo module prende il file source_text di un problem e
sostituisce OGNI dimostrazione con `sorry`, ottenendo esattamente l'aspetto che
il file avrebbe se il problem fosse ancora aperto.

Si sostituiscono all_items le dimostrazioni del file, non only quella del theorem
target: i lemmi neighbours sono spesso i passaggi intermedi della solution e
lasciarli sarebbe come lasciare mezzo compito svolto.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
from index import ProblemIndex, Problem   # noqa: E402


#: Coppie di delimitatori: inside di esse un `:=` non separa la dimostrazione.
_OPENERS = "([{⟨"
_CLOSERS = ")]}⟩"


def _separator_position(text: str) -> int | None:
    """Indice del `:=` che separa l'statement dalla dimostrazione.

    Va cercato al level esterno: in `theorem f (n : ℕ := 3) : P := trial` il
    first `:=` sta inside le parentesi e non c'enters.

    E vanno saltati i COMMENTI. Le positions che Lean riporta per one
    declaration partono dal docstring, non dalla word `theorem`, e un
    docstring puo' contenere code di example con inside un `:=`. Senza questo
    accorgimento il cut finirebbe inside la documentazione.
    """
    depth = 0
    i, n = 0, len(text)
    while i < n - 1:
        c = text[i]
        # commento di line
        if c == "-" and text[i + 1] == "-":
            while i < n and text[i] != "\n":
                i += 1
            continue
        # commento a block, annidabile; comprende i docstring /-- ... -/
        if c == "/" and text[i + 1] == "-":
            level = 0
            while i < n - 1:
                if text[i] == "/" and text[i + 1] == "-":
                    level += 1; i += 2; continue
                if text[i] == "-" and text[i + 1] == "/":
                    level -= 1; i += 2
                    if level == 0:
                        break
                    continue
                i += 1
            continue
        # stringa
        if c == '"':
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2; continue
                if text[i] == '"':
                    i += 1; break
                i += 1
            continue
        if c in _OPENERS:
            depth += 1
        elif c in _CLOSERS:
            depth -= 1
        elif c == ":" and text[i + 1] == "=" and depth == 0:
            if not _is_binder(text, i):
                return i
        i += 1
    return None


#: Parole che introducono one LEGATURA, non la dimostrazione. Un `:=` che le
#: segue appartiene a loro.
_BINDERS = ("let", "have", "set", "obtain", "suffices", "calc", "fun", "where",
             "if", "then", "else", "with", "do", "match")


def _is_binder(text: str, pos: int) -> bool:
    """Dice se il `:=` a `pos` appartiene a un `let`, un `have` e simili.

    Serve perche' un statement puo' contenere un `let A : Set α := ...` al
    level esterno delle parentesi, e prenderlo per l'start della
    dimostrazione TRONCA l'statement. E' successo davvero, su
    WrittenOnTheWallII.GraphConjecture65.conjecture65, e il controllo di
    onesta' l'ha intercettato.
    """
    line_start = text.rfind("\n", 0, pos) + 1
    segment = text[line_start:pos]
    words = segment.replace("(", " ").replace(")", " ").split()
    if not words:
        # il `:=` sta a start line: si guarda la line precedente
        prec = text.rfind("\n", 0, max(0, line_start - 1)) + 1
        words = text[prec:line_start].replace("(", " ").replace(")", " ").split()
    # Si guarda a ritroso la before word significativa. Un punto e virgola
    # CHIUDE la legatura (`let a := 1; resto`), quindi la scansione si ferma li':
    # senza, il `:=` finale di `theorem t : (let a := 1; a = 1) := by rfl`
    # veniva scambiato per quello del `let`.
    for word in reversed(words):
        if ";" in word:
            return False
        if word in _BINDERS:
            return True
        if word in ("theorem", "lemma", "def", "abbrev", "instance", "example"):
            return False
    return False


def replace_proof(declaration: str) -> str:
    """`theorem f : P := <trial>`  ->  `theorem f : P := by\\n  sorry`"""
    pos = _separator_position(declaration)
    if pos is None:
        return declaration
    return declaration[:pos].rstrip() + " := by\n  sorry"


def file_without_proofs(problem: Problem, index: ProblemIndex) -> str:
    """Il file del problem con all_items le dimostrazioni sostituite da `sorry`."""
    text = problem.source_file.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Tutti i theorems che stanno in questo file, dal fondo verso l'high, cosi'
    # le substitutions non spostano le positions di quelli ancora da trattare.
    nel_file = [p for p in index.problems if p.module == problem.module and p.range]
    nel_file.sort(key=lambda p: (p.range["startLine"], p.range["startCol"]), reverse=True)

    for p in nel_file:
        r = p.range
        line_start, line_end = r["startLine"] - 1, r["endLine"] - 1
        block = lines[line_start:line_end + 1]
        if not block:
            continue
        # ritaglia esattamente la declaration
        queue = block[-1][r["endCol"]:]
        block[-1] = block[-1][:r["endCol"]]
        head = block[0][:r["startCol"]]
        block[0] = block[0][r["startCol"]:]
        new_item = replace_proof("\n".join(block))
        new_lines = (head + new_item + queue).split("\n")
        lines[line_start:line_end + 1] = new_lines

    return "\n".join(lines)


def check_it_is_hidden(problem: Problem, hidden_text: str) -> None:
    """Verifica che la dimostrazione del theorem BERSAGLIO sia stata sostituita.

    Un shakedown in cui la answer trapela non misura niente, quindi questo
    controllo deve esserci. Ma va fatto sulla DICHIARAZIONE GIUSTA: la before
    versione cercava il text della dimostrazione in tutto il file, e dava
    falso allarme quando un other theorem dello stesso file aveva la stessa
    dimostrazione di one line. E' successo con
    DiophantineTuple.fermat_4_tuple, dove three theorems condividono
    `by norm_num [IsDiophantineTuple]`: il shakedown si e' interrotto pur
    essendo tutto in order.
    """
    short = problem.theorem.split(".")[-1]
    # la declaration del target inside il text nascosto
    m = re.search(rf"(?:theorem|lemma)\s+[\w'.«»]*{re.escape(short)}(?![\w']) ?[\s\S]*?"
                  rf"(?=\n(?:@\[|/--|theorem |lemma |def |abbrev |instance |end |namespace |"
                  rf"variable |open |section )|\Z)",
                  hidden_text)
    if m is None:
        raise AssertionError(
            f"Nel text consegnato all'agent non trovo la declaration di "
            f"{problem.theorem}: il problem non sarebbe proponibile.")
    declaration = m.group(0)
    pos = _separator_position(declaration)
    if pos is None:
        raise AssertionError(
            f"Non riesco a individuare la dimostrazione di {problem.theorem} "
            f"nel text nascosto.")
    # Si togliono i commenti: la declaration estratta puo' portarsi dietro
    # one line di commento che segue (per example "-- Sanity checks"), e
    # confrontarla come se fosse dimostrazione dava un falso allarme.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
    from guard import strip_comments_and_strings
    trial = " ".join(strip_comments_and_strings(declaration[pos + 2:]).split())
    if trial not in ("by sorry", "sorry"):
        raise AssertionError(
            f"La dimostrazione di {problem.theorem} NON e' stata nascosta: al "
            f"suo slot c'e' ancora {trial[:120]!r}. Il shakedown non sarebbe valid.")
