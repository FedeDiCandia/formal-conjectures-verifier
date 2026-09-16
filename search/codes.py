"""
Exact verification of binary codes.

WHY THIS FILE IS THE MOST IMPORTANT PART OF THIS ROUTE
------------------------------------------------------
Everything in the project so far has leaned on a complicated verifier: Lean, the
kernel, comparator, the sandbox, the archive's fingerprint. Five times it has had to
stop our own machine when it said "found".

Here the verifier is **this file**, and it can be read in five minutes. A binary
constant-weight code is a list of words; it is valid if every word has the right
length and weight and every pair is at distance at least `d`. These are comparisons
between integers: there is nothing to interpret, nothing to elaborate, no environment
that could be misconfigured, no tactic that could leave a `sorry`.

**The rule for this file: never optimise for speed at the cost of clarity.** If speed
is needed it goes in another file, and this one stays the judge.

A word of length n is an `int`: bit i (value 2^i) says whether position i is 1. The
weight is `int.bit_count()`. The Hamming distance between two words is the weight of
their XOR.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path


@dataclass
class Result:
    """The verdict. `ok` is true only if there is no finding."""
    ok: bool
    size: int
    findings: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.ok:
            return f"VALIDO, {self.size} words"
        return (f"INVALID ({len(self.findings)} findings): "
                + "; ".join(self.findings[:5]))


def weight(word: int) -> int:
    return word.bit_count()


def distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def check(words, n: int, d: int, w: int | None = None,
             max_findings: int = 20) -> Result:
    """Exact verification of a binary code.

    `w` not None: a constant-weight code. No shortcuts, no heuristics: **every** pair
    is checked.
    """
    words = list(words)
    findings: list[str] = []

    def report(msg: str) -> bool:
        findings.append(msg)
        return len(findings) >= max_findings

    if n <= 0:
        report(f"invalid length n={n}")
    limit = 1 << n
    seen: dict[int, int] = {}
    for i, p in enumerate(words):
        if not isinstance(p, int) or p < 0:
            if report(f"word {i}: not a non-negative integer ({p!r})"):
                break
            continue
        if p >= limit:
            if report(f"word {i}: uses a bit beyond position {n - 1}"):
                break
            continue
        if w is not None and weight(p) != w:
            if report(f"word {i}: weight {weight(p)}, expected {w}"):
                break
            continue
        if p in seen:
            if report(f"word {i}: duplicate of word {seen[p]}"):
                break
            continue
        seen[p] = i

    if not findings:
        for (i, a), (j, b) in combinations(list(enumerate(words)), 2):
            dist = distance(a, b)
            if dist < d:
                if report(f"words {i} and {j}: distance {dist} < {d}"):
                    break

    return Result(ok=not findings, size=len(words), findings=findings)


# ------------------------------------------------------------- reading files

def read(path: str | Path, n: int | None = None) -> tuple[list[int], int]:
    """Read a code from a text file and return (words, n).

    It recognises the two formats in which these codes circulate:

      * **positions**: each line is the list of positions set to 1, e.g.
        `1 2 3 7` or `1,2,3,7`;
      * **bits**: each line is a string of `0`s and `1`s of the same length.

    The format is recognised from the first useful line and then applied to all of
    them: a mixed file is an error, not an occasion for guessing.
    """
    lines = [r.strip() for r in Path(path).read_text().splitlines()]
    lines = [r for r in lines if r and not r.startswith("#")]
    if not lines:
        raise ValueError(f"{path}: no useful line")

    a_bit = all(c in "01" for c in lines[0]) and len(lines[0]) > 1
    words: list[int] = []
    if a_bit:
        length = len(lines[0])
        for k, r in enumerate(lines):
            if len(r) != length or any(c not in "01" for c in r):
                raise ValueError(f"{path}: line {k + 1} is not a string of "
                                 f"{length} bit: {r[:40]!r}")
            words.append(int(r[::-1], 2))
        inferred = length
    else:
        maximum = 0
        for k, r in enumerate(lines):
            pieces = r.replace(",", " ").split()
            try:
                pos = [int(x) for x in pieces]
            except ValueError:
                raise ValueError(f"{path}: line {k + 1} is not a list of "
                                 f"positions: {r[:40]!r}") from None
            if len(set(pos)) != len(pos):
                raise ValueError(f"{path}: line {k + 1} repeats a position")
            base = 1 if min(pos) >= 1 else 0
            maximum = max(maximum, max(pos))
            words.append(sum(1 << (p - base) for p in pos))
        inferred = maximum  # positions 1..n
    return words, (n if n is not None else inferred)


# ------------------------------------------------- a fast check, and an exact one
#
# For large codes, checking every pair is too slow in Python: 50,000 words are 1.25
# billion pairs. But there is an **equivalent** and almost instantaneous criterion,
# valid for constant-weight codes.
#
# Two distinct words of weight w at Hamming distance `dist` satisfy
#
#     dist = 2 · (w − |A ∩ B|)
#
# where A and B are their supports: every position in A but not in B, and vice
# versa, contributes 1. So, for even d,
#
#     dist ≥ d   ⟺   |A ∩ B| ≤ w − d/2 =: t
#
# and a violation means |A ∩ B| ≥ t+1, that is **the two words share a subset of t+1
# positions**. So it suffices to list, for each word, all its subsets of size t+1: the
# code is valid if and only if no subset appears twice. The cost is m · C(w, t+1)
# instead of m²/2, and for the cases of interest that is four orders of magnitude
# less.
#
# It is neither a heuristic nor an approximation: it is the same criterion,
# rewritten. The test `test_fast_and_slow_agree` compares it with the judge on
# thousands of random cases, and `check` remains the judge for the results we
# declare.

def positions(word: int) -> tuple[int, ...]:
    outside = []
    i = 0
    while word:
        if word & 1:
            outside.append(i)
        word >>= 1
        i += 1
    return tuple(outside)


def fast_check(words, n: int, d: int, w: int) -> Result:
    """Like `check`, for constant-weight codes with even d, but for large m."""
    if d % 2:
        raise ValueError(f"the criterion holds for even d, got d={d}")
    words = list(words)
    t = w - d // 2
    if t < 0:
        return Result(ok=False, size=len(words),
                     findings=[f"d={d} is too large for w={w}"])
    if t >= w:
        return check(words, n, d, w)      # no useful constraint: use the judge

    findings: list[str] = []
    limit = 1 << n
    for i, p in enumerate(words):
        if not isinstance(p, int) or p < 0 or p >= limit:
            findings.append(f"word {i}: outside the range [0, 2^{n})")
        elif weight(p) != w:
            findings.append(f"word {i}: weight {weight(p)}, expected {w}")
        if len(findings) >= 20:
            break
    if findings:
        return Result(ok=False, size=len(words), findings=findings)

    seen: dict[tuple[int, ...], int] = {}
    for i, p in enumerate(words):
        for below in combinations(positions(p), t + 1):
            other = seen.get(below)
            if other is not None:
                findings.append(
                    f"words {other} and {i}: they share the {t + 1} positions "
                    f"{list(below)}, so they are at distance at most {2 * (w - t - 1)} < {d}")
                if len(findings) >= 20:
                    return Result(ok=False, size=len(words), findings=findings)
            else:
                seen[below] = i
    return Result(ok=not findings, size=len(words), findings=findings)
