"""
Hide the proofs the archive already contains.

To exercise an agent honestly on a problem that is already solved, the answer has
to be taken away from it. This module takes a problem's source file and replaces
EVERY proof with `sorry`, producing exactly the file it would be if the problem
were still open.

All the proofs in the file are replaced, not only the target theorem's: the
neighbouring lemmas are often the intermediate steps of the solution, and leaving
them would be like leaving half the exercise done.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
from index import ProblemIndex, Problem   # noqa: E402


#: Delimiter pairs: inside them, a `:=` does not separate the proof.
_OPENERS = "([{⟨"
_CLOSERS = ")]}⟩"


def _separator_position(text: str) -> int | None:
    """Index of the `:=` that separates the statement from the proof.

    It has to be looked for at the outer level: in
    `theorem f (n : ℕ := 3) : P := proof` the first `:=` is inside the brackets and
    is nothing to do with it.

    And COMMENTS have to be skipped. The positions Lean reports for a declaration
    start at the docstring, not at the word `theorem`, and a docstring can contain
    example code with a `:=` inside it. Without this precaution the cut would land
    inside the documentation.
    """
    depth = 0
    i, n = 0, len(text)
    while i < n - 1:
        c = text[i]
        # line comment
        if c == "-" and text[i + 1] == "-":
            while i < n and text[i] != "\n":
                i += 1
            continue
        # block comment, nestable; this includes docstrings /-- ... -/
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
        # string
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


#: Words that introduce a BINDER, not the proof. A `:=` that follows one of them
#: belongs to it.
_BINDERS = ("let", "have", "set", "obtain", "suffices", "calc", "fun", "where",
             "if", "then", "else", "with", "do", "match")


def _is_binder(text: str, pos: int) -> bool:
    """Say whether the `:=` at `pos` belongs to a `let`, a `have` or the like.

    This is needed because a statement can contain a `let A : Set α := ...` at the
    outer bracket level, and taking that for the start of the proof TRUNCATES the
    statement. It really happened, on
    WrittenOnTheWallII.GraphConjecture65.conjecture65, and the honesty check caught
    it.
    """
    line_start = text.rfind("\n", 0, pos) + 1
    segment = text[line_start:pos]
    words = segment.replace("(", " ").replace(")", " ").split()
    if not words:
        # the `:=` is at the start of a line: look at the previous one
        prec = text.rfind("\n", 0, max(0, line_start - 1)) + 1
        words = text[prec:line_start].replace("(", " ").replace(")", " ").split()
    # Look backwards for the first significant word. A semicolon CLOSES the binder
    # (`let a := 1; rest`), so the scan stops there: without that, the final `:=` of
    # `theorem t : (let a := 1; a = 1) := by rfl` was mistaken for the `let`'s.
    for word in reversed(words):
        if ";" in word:
            return False
        if word in _BINDERS:
            return True
        if word in ("theorem", "lemma", "def", "abbrev", "instance", "example"):
            return False
    return False


def replace_proof(declaration: str) -> str:
    """`theorem f : P := <proof>`  ->  `theorem f : P := by\\n  sorry`"""
    pos = _separator_position(declaration)
    if pos is None:
        return declaration
    return declaration[:pos].rstrip() + " := by\n  sorry"


def file_without_proofs(problem: Problem, index: ProblemIndex) -> str:
    """The problem's file with every proof replaced by `sorry`."""
    text = problem.source_file.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Every theorem in this file, from the bottom upwards, so that the
    # substitutions do not move the positions of those still to be handled.
    in_file = [p for p in index.problems if p.module == problem.module and p.range]
    in_file.sort(key=lambda p: (p.range["startLine"], p.range["startCol"]), reverse=True)

    for p in in_file:
        r = p.range
        line_start, line_end = r["startLine"] - 1, r["endLine"] - 1
        block = lines[line_start:line_end + 1]
        if not block:
            continue
        # cut out exactly the declaration
        tail = block[-1][r["endCol"]:]
        block[-1] = block[-1][:r["endCol"]]
        head = block[0][:r["startCol"]]
        block[0] = block[0][r["startCol"]:]
        new_item = replace_proof("\n".join(block))
        new_lines = (head + new_item + tail).split("\n")
        lines[line_start:line_end + 1] = new_lines

    return "\n".join(lines)


def check_it_is_hidden(problem: Problem, hidden_text: str) -> None:
    """Check that the TARGET theorem's proof has really been replaced.

    An exercise in which the answer leaks measures nothing, so this check has to be
    here. But it has to be done on the RIGHT declaration: the first version looked
    for the proof's text anywhere in the file, and raised a false alarm when another
    theorem in the same file had the same one-line proof. It happened with
    DiophantineTuple.fermat_4_tuple, where three theorems share
    `by norm_num [IsDiophantineTuple]`: the run stopped even though everything was
    in order.
    """
    short = problem.theorem.split(".")[-1]
    # the target's declaration inside the hidden text
    m = re.search(rf"(?:theorem|lemma)\s+[\w'.«»]*{re.escape(short)}(?![\w']) ?[\s\S]*?"
                  rf"(?=\n(?:@\[|/--|theorem |lemma |def |abbrev |instance |end |namespace |"
                  rf"variable |open |section )|\Z)",
                  hidden_text)
    if m is None:
        raise AssertionError(
            f"The declaration of {problem.theorem} cannot be found in the text handed "
            f"to the agent: the problem could not be posed.")
    declaration = m.group(0)
    pos = _separator_position(declaration)
    if pos is None:
        raise AssertionError(
            f"Cannot locate the proof of {problem.theorem} in the hidden text.")
    # Comments are stripped: the extracted declaration can drag along a following
    # comment line (for instance "-- Sanity checks"), and comparing that as though
    # it were the proof raised a false alarm.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
    from guard import strip_comments_and_strings
    proof = " ".join(strip_comments_and_strings(declaration[pos + 2:]).split())
    if proof not in ("by sorry", "sorry"):
        raise AssertionError(
            f"The proof of {problem.theorem} has NOT been hidden: in its place there "
            f"is still {proof[:120]!r}. The exercise would not be valid.")
