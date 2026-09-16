"""
"Negated" challenges for problems with a propositional `answer(sorry)`.

THE PROBLEM
-----------
As explained in docs/01-the-archive.md, the archive's default option
(`google.answer = always_true`) turns `answer(sorry)` into `True` when the
expected type is a proposition. So an open question formalised like this:

    /-- Does P hold? -/
    theorem conjecture : answer(sorry) ↔ P := by sorry

elaborates as `True ↔ P`, that is, as the assertion that **the answer is YES**.
563 of the archive's still-open problems are like that in the benchmark tag, 634
on the `main` snapshot (counted from the index: `research open`, `answer(sorry)`
in the source, no `sorry` left in the elaborated statement).

The consequence: if for one of them the right answer were NO, the theorem as
written would be FALSE, and nobody could prove it. Whoever found the refutation
would have no way to have it verified: they would have to change the statement to
`answer(False) ↔ P`, and the verifier would reject it — rightly, because that is a
different statement.

THE SOLUTION
------------
For each of those problems one can generate the **negated** challenge: the same
archive file with `answer(sorry)` replaced by `answer(False)`, so that the
statement becomes `False ↔ P`, which is logically `¬P`.

The essential point is WHO generates that file. We do, mechanically, from the
archive's source: it is a **trusted** file, exactly as the original module is. It
is not written by whoever proposes the proof. If it were, they could put anything
they liked in it.

So an open problem has two challenges, both trusted and both verifiable:

    strict      True  ↔ P     "the answer is yes"   (the archive's statement)
    refutation  False ↔ P     "the answer is no"

and they are different statements: a proof of one is rejected by the other. The
tests check exactly that.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from index import Problem   # noqa: E402


#: `answer(sorry)` with any spacing between the pieces.
_PLACEHOLDER = re.compile(r"answer\s*\(\s*sorry\s*\)")


class NotNegatable(ValueError):
    """The problem admits no negated challenge."""


@dataclass
class NegatedChallenge:
    problem: str
    #: the text of the Lean file to compile as the Challenge
    text: str
    #: how many substitutions were made
    substitutions: int
    #: the name of the theorem to prove in the challenge. On the `answer( )` route
    #: it is the problem's own name (the statement changes, the name does not); on
    #: the `type_of%` route it is a derived name.
    target: str = ""
    #: which of the two routes was used, for the report
    route: str = "answer"


def can_be_negated(problem: Problem) -> tuple[bool, str]:
    """Say whether generating the negated challenge makes sense, and if not, why."""
    if not problem.answer_placeholder_in_source:
        return False, ("the statement contains no `answer(sorry)`: there is no "
                       "question whose answer could be inverted. A statement without "
                       "`answer( )` asserts a proposition directly, and its negation "
                       "is not a problem of the archive")
    if problem.statement_has_sorry:
        return False, ("the `answer( )` hole is not propositional: the answer is an "
                       "object (a number, a set), not a yes/no. There is no direction "
                       "to invert, there is a value to supply")
    return True, ""


#: Suffix of the theorem generated on the `type_of%` route.
SUFFIX = "_refutation"


def generate_by_kind(problem: Problem) -> NegatedChallenge:
    """The negated challenge for ANY statement, via the `type_of%` route.

    This is for problems that have no `answer(sorry)` to invert, which is most of
    them. Instead of rewriting the statement — a fragile operation on a statement
    with quantifiers and binders spread over several lines — we ask Lean for the
    type of the original theorem and declare its negation:

        import <the problem's module>
        theorem <name>_refutation : ¬ (type_of% @<name>) := sorry

    The candidate has to declare the same theorem and prove it. It is allowed to
    import the problem's module — which the strict mode forbids — and the reason
    this is NOT a loophole is that in an open problem the original theorem is
    proved with `sorry`: using it introduces `sorryAx` and the axiom check
    rejects it. That is, the candidate may read the statement but cannot lean on
    its fake proof.

    It is the same construction used by Epoch AI's OEIS Open benchmark, where 43%
    of the accepted solutions are refutations: without this route, that half of
    the possible results would not even be verifiable.
    """
    if problem.statement_has_sorry:
        raise NotNegatable(
            f"{problem.theorem}: the statement contains a `sorry` (a "
            f"non-propositional `answer( )` hole), so its negation is not a "
            f"well-posed assertion")
    name = f"{problem.theorem}{SUFFIX}"
    text = (
        "-- Negated challenge, generated automatically by verifier/negation.py.\n"
        "-- This is not a file of the archive: it is the target of a refutation.\n"
        f"import {problem.module}\n"
        "\n"
        f"/-- The negation of `{problem.theorem}`. Proving this theorem refutes\n"
        f"the problem as the archive formalises it. -/\n"
        f"theorem {name} : ¬ (type_of% @{problem.theorem}) := sorry\n")
    return NegatedChallenge(problem=problem.theorem, text=text, substitutions=0,
                            target=name, route="type_of%")


def generate(problem: Problem) -> NegatedChallenge:
    """Build the text of the negated challenge from the archive's source."""
    ok, why_not = can_be_negated(problem)
    if not ok:
        raise NotNegatable(f"{problem.theorem}: {why_not}")

    text = problem.source_file.read_text(encoding="utf-8")
    r = problem.range
    if not r:
        raise NotNegatable(f"{problem.theorem}: position in the source is unknown")

    lines = text.split("\n")
    start, end = r["startLine"] - 1, r["endLine"] - 1

    # The substitution must be made ONLY inside the target theorem's declaration:
    # the same file may hold other problems with their own `answer(sorry)`, and
    # inverting all of them would give a different challenge from the intended one.
    block = "\n".join(lines[start:end + 1])
    new_block, n = _PLACEHOLDER.subn("answer(False)", block)
    if n == 0:
        raise NotNegatable(
            f"{problem.theorem}: `answer(sorry)` not found in the declaration. "
            f"The index says it is there, so the index is stale: rebuild it with "
            f"`python verifier/index.py --build`")
    lines[start:end + 1] = new_block.split("\n")

    header = (
        "/-\n"
        "  NEGATED CHALLENGE — generated automatically, not written by hand.\n"
        "\n"
        f"  Problem:  {problem.theorem}\n"
        f"  Original: {problem.module}\n"
        "\n"
        "  This is the archive's file with `answer(sorry)` replaced by\n"
        "  `answer(False)` in the target theorem's declaration only.\n"
        "  The statement therefore goes from `True ↔ P` (the answer is yes) to\n"
        "  `False ↔ P` (the answer is no, that is ¬P).\n"
        "\n"
        "  Generated by verifier/negation.py from the archive's source: it is a\n"
        "  TRUSTED file, not supplied by whoever proposes the proof.\n"
        "-/\n")
    return NegatedChallenge(problem=problem.theorem,
                            text=header + "\n".join(lines),
                            substitutions=n,
                            target=problem.theorem, route="answer")
