"""
Extract the proof the archive supplies, as a self-contained candidate file.

WHAT IT IS FOR
--------------
Calibrating an agent needs problems whose answer is known. But "the archive has
solved it" is not enough: its proof might use `decide +native` (95 cases) or
depend on a lemma with a hole (17 cases), and our verifier would reject it. Asking
an agent to solve one of those problems means asking it to do BETTER than the
archive, and a failure would say nothing about the agent.

The axiom check (the index's `archiveProofAxioms` field) is a necessary but not
sufficient condition: it does not say whether the proof, extracted from its file
and compiled on its own, really makes it through the verifier. Finding that out
means trying.

This module builds the candidate file the archive itself would submit: the
imports, the local definitions, the auxiliary lemmas that ARE proved, and the
target theorem with its real proof. Only the declarations containing `sorry` are
removed, because the verifier rejects a file that contains any.

Removing ALL the other theorems was the wrong choice: on the first attempt 9
proofs out of 23 failed with "Unknown identifier", because they used a
neighbouring lemma from the same file. The failure was the extractor's, not the
archive's.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from index import Problem, ProblemIndex   # noqa: E402


class NotExtractable(ValueError):
    """No self-contained candidate can be built for this problem."""


@dataclass
class ArchiveProof:
    problem: str
    text: str
    theorems_removed: int


#: Keywords that open a DECLARATION.
_DECLARATIONS = ("theorem", "lemma", "def", "abbrev", "instance", "structure",
                  "inductive", "class", "example", "opaque", "axiom")

#: Modifiers that may precede a keyword.
_MODIFIERS = ("private", "protected", "noncomputable", "partial", "unsafe",
                 "scoped", "local", "nonrec", "public", "meta", "mutual")

#: Structural commands: they open a block but declare nothing.
#: They are matched as WHOLE WORDS. Matching them as prefixes was a real defect:
#: a docstring line beginning "endomorphism of a finite set is surjective. -/"
#: was read as an `end`, the previous theorem's block ended one line too early
#: and the tail of the docstring was left dangling, with "unexpected identifier;
#: expected command". It happened on
#: GottschalkSurjunctivity.isSurjunctive_of_finite.
_STRUCTURAL = ("namespace", "end", "section", "import", "open", "variable",
                "variables", "universe", "set_option", "attribute", "notation",
                "notation3", "deriving", "macro", "macro_rules", "syntax",
                "elab", "elab_rules", "run_cmd")

#: These two, by contrast, attach to their argument (`#check`, `/-!# Title`).
_STRUCTURAL_PREFIX = ("#", "/-!")

_RE_STRUCTURAL = re.compile(
    "^(?:" + "|".join(re.escape(p) for p in _STRUCTURAL) + r")(?![A-Za-z0-9_'])")
# NB: `/-` is NOT here. It was once, and since `/--` begins with `/-` docstrings
# became block openers again: removing a theorem left its docstring dangling, with
# the error "unexpected token '/--'; expected 'lemma'". A docstring always belongs
# to the declaration that follows it, never to itself.


def _opens_declaration(line: str) -> bool:
    if not line or line[0].isspace():
        return False
    words = line.split()
    i = 0
    while i < len(words) and words[i] in _MODIFIERS:
        i += 1
    return i < len(words) and words[i].split(":")[0] in _DECLARATIONS


def _opens_structure(line: str) -> bool:
    if not line or line[0].isspace():
        return False
    if line.startswith(_STRUCTURAL_PREFIX):
        return True
    return bool(_RE_STRUCTURAL.match(line))


def _blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Split the file into top-level blocks: (first line, last line).

    The delicate point: a docstring `/-- ... -/` and an attribute `@[...]` BELONG
    to the declaration that follows them. Treating them as blocks of their own is
    exactly the error that, on the first attempt, left a docstring dangling after
    its theorem had been removed, with "unexpected token '/--'; expected 'lemma'".

    So: first the lines that open a declaration or a structural command are found,
    then each is extended BACKWARDS to absorb the attributes, docstrings and blank
    lines that precede it.
    """
    starts = [i for i, r in enumerate(lines)
             if _opens_declaration(r) or _opens_structure(r)]
    if not starts:
        return [(0, len(lines) - 1)]

    def extend_backwards(i: int, limit: int) -> int:
        """Move the block's start above attributes, docstrings and blank lines."""
        j = i
        while j - 1 > limit:
            prec = lines[j - 1]
            bare = prec.strip()
            if not bare:
                j -= 1
                continue
            # an attribute, possibly spanning several lines
            if bare.endswith("]") and "@[" in "\n".join(lines[max(limit + 1, j - 6):j]):
                k = j - 1
                while k > limit and "@[" not in lines[k]:
                    k -= 1
                if "@[" in lines[k]:
                    j = k
                    continue
            if bare.startswith("@["):
                j -= 1
                continue
            # a docstring or comment closed just above
            if bare.endswith("-/"):
                k = j - 1
                level = 0
                while k > limit:
                    level += lines[k].count("-/") - lines[k].count("/-")
                    if level <= 0 and ("/--" in lines[k] or "/-" in lines[k]):
                        break
                    k -= 1
                j = k
                continue
            break
        return j

    bounds = []
    for k, i in enumerate(starts):
        # The limit of the backwards walk is the line of the PREVIOUS
        # declaration, not the end of its block: the end of the previous block is
        # exactly what we are about to correct. Using that stopped the walk at the
        # first step, and docstrings and attributes stayed attached to the wrong
        # declaration.
        limit = starts[k - 1] if k > 0 else -1
        start = extend_backwards(i, limit)
        end = (starts[k + 1] - 1) if k + 1 < len(starts) else len(lines) - 1
        bounds.append([start, end])
    # tidy the bounds: block n ends where block n+1 begins
    for k in range(len(bounds) - 1):
        bounds[k][1] = bounds[k + 1][0] - 1
    if bounds and bounds[0][0] > 0:
        bounds.insert(0, [0, bounds[0][0] - 1])
    return [(a, b) for a, b in bounds if b >= a]


def _without_comments(text: str) -> str:
    """Strip comments and strings, so that a `sorry` quoted in a comment is not
    mistaken for a real hole."""
    import guard
    return guard.strip_comments_and_strings(text)


def _comment_imbalance(text: str) -> int:
    """How many `-/` closers there are in excess of `/-` openers.

    This matters when a block is removed: if it contained the closer of a comment
    that began higher up, the closer has to be put back, or the comment stays open
    and swallows the rest of the file.
    """
    opens = closes = 0
    i, n = 0, len(text)
    while i < n - 1:
        if text[i] == "-" and text[i + 1] == "-" and opens == closes:
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text[i] == "/" and text[i + 1] == "-":
            opens += 1; i += 2; continue
        if text[i] == "-" and text[i + 1] == "/":
            closes += 1; i += 2; continue
        i += 1
    return closes - opens


def _cut_open_comment(text: str) -> str:
    """Remove a block comment that has been left open.

    Truncating the file after the target theorem can land inside a comment
    `/- ... -/` whose `-/` was further down. Lean then stops with "unterminated
    comment". Here the `/-` left without a closer is found and everything from
    there on is cut: it is only a comment, so nothing mathematical is lost.
    """
    depth = 0
    last_opening = None
    i, n = 0, len(text)
    while i < n - 1:
        if text[i] == "-" and text[i + 1] == "-" and depth == 0:
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text[i] == "/" and text[i + 1] == "-":
            if depth == 0:
                last_opening = i
            depth += 1
            i += 2
            continue
        if text[i] == "-" and text[i + 1] == "/":
            depth = max(0, depth - 1)
            i += 2
            continue
        i += 1
    if depth > 0 and last_opening is not None:
        return text[:last_opening].rstrip() + "\n"
    return text


def _missing_closers(text: str) -> str:
    """The `end` lines needed to close namespaces and sections again.

    Truncating the file after the target theorem leaves the `namespace`s and
    `section`s containing it open, and Lean stops with "Unexpected name after
    `end`" or with an unclosed section. Here a stack of what has been opened is
    kept, and closed in reverse order.
    """
    stack: list[str] = []
    for line in text.split("\n"):
        if line[:1].isspace() or not line.strip():
            continue
        words = line.split()
        if not words:
            continue
        if words[0] == "namespace" and len(words) > 1:
            stack.append(words[1])
        elif words[0] == "section":
            stack.append(words[1] if len(words) > 1 else "")
        elif words[0] == "end":
            if stack:
                stack.pop()
    if not stack:
        return ""
    lines = ["", "-- closers added automatically after the file was truncated"]
    for name in reversed(stack):
        lines.append(f"end {name}".rstrip())
    return "\n".join(lines) + "\n"


def _declared_name(block: str) -> str | None:
    m = re.search(r"^(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|nonrec|noncomputable)\s+)*"
                  r"(?:theorem|lemma)\s+([\w'.\u00ab\u00bb]+)", block, re.M)
    return m.group(1) if m else None


def extract(problem: Problem, index: ProblemIndex) -> ArchiveProof:
    """The archive's file without the other theorems."""
    if not problem.proof_is_complete:
        raise NotExtractable(
            f"{problem.theorem}: the archive supplies no proof of it "
            f"(the proof term contains `sorry`)")
    if not problem.range:
        raise NotExtractable(f"{problem.theorem}: position in the source is unknown")

    text = problem.source_file.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Short name of the target theorem: in the file it is written without the namespace.
    short = problem.theorem.split(".")[-1]
    name_parts = problem.theorem.split(".")

    kept, removed, found = [], 0, False
    for start, end in _blocks(lines):
        block = "\n".join(lines[start:end + 1])
        name = _declared_name(block)
        if name is not None:
            is_target = (name == problem.theorem or name == short
                           or problem.theorem.endswith("." + name)
                           or (name.split(".")[-1] == short
                               and all(x in name_parts for x in name.split("."))))
            if is_target:
                kept.append(block)
                found = True
                # Nothing AFTER the target theorem can be of use to it: a Lean
                # file is read from the top down. Keeping it only caused errors,
                # because those theorems in turn used lemmas we had had to remove.
                break
            clean = _without_comments(block)
            # Neighbouring lemmas that use `native_decide` or `decide +native`
            # are removed too: the verifier rejects the whole file if it finds
            # them, and the target theorem does not need them (if it did, its
            # axioms would not be clean and the problem would not be a candidate).
            if ("sorry" in clean or "native_decide" in clean
                    or re.search(r"\+\s*native", clean)):
                removed += 1
                # If the removed block CLOSED a comment opened higher up,
                # removing it leaves that comment open and the rest of the file —
                # the target included — ends up inside the comment. So the closer
                # is put back in its place.
                deficit = _comment_imbalance(block)
                if deficit > 0:
                    kept.append("-/" * deficit)
                continue
        kept.append(block)

    if not found:
        raise NotExtractable(
            f"{problem.theorem}: could not locate the declaration in the file "
            f"(expected name `{short}`)")

    body = "\n".join(kept)
    # Putting a comment's closer back can leave an EMPTY docstring (`/--`
    # immediately followed by `-/`): Lean rejects that, because a docstring has to
    # document something. So it is removed.
    body = re.sub(r"/--\s*-/\s*\n", "", body)
    body = _cut_open_comment(body)
    body += _missing_closers(body)

    # Safety check: after all this manipulation the target theorem must still be
    # there. If it is not, the file would compile perfectly well and comparator
    # would fail with an obscure PANIC ("Constant not found"): better a clear
    # error now.
    if not re.search(rf"(?:theorem|lemma)\s+{re.escape(short)}(?![\w'])", body) and \
       not re.search(rf"(?:theorem|lemma)\s+\S*{re.escape(short)}(?![\w'])", body):
        raise NotExtractable(
            f"{problem.theorem}: after extraction the target theorem is no longer "
            f"in the file. That is a defect of the extractor, not of the archive.")

    header = (
        "/-\n"
        "  THE ARCHIVE'S PROOF, extracted automatically.\n"
        "\n"
        f"  Problem: {problem.theorem}\n"
        f"  Module:  {problem.module}\n"
        f"  Removed: {removed} theorems from the same file that contained `sorry`\n"
        f"           (auxiliary lemmas that ARE proved were kept: the target's\n"
        f"           proof often uses them)\n"
        "\n"
        "  This exists to establish whether the proof the archive supplies really\n"
        "  passes our verifier. If it does not, the problem cannot be used to\n"
        "  calibrate an agent.\n"
        "-/\n")
    return ArchiveProof(problem=problem.theorem,
                         text=header + body,
                         theorems_removed=removed)
