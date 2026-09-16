"""
Expanding the published codes from the `$EXEC orbit` format.

WHY IT IS NEEDED, AND WHAT IT TEACHES
-------------------------------------
Brouwer's record codes are not published as lists of words: they are published as
**generators of a permutation group plus a few seed words**, and the code is the union
of the seeds' orbits under the group.

This is not only a format: it is the **method** by which nearly all these records were
found. Nobody looks for 5558 words one at a time — one looks for a suitable group and
a few seed words, and the group does the rest. It is the most useful thing we have
gathered about this route, and it comes free from reading the source.
"""
from __future__ import annotations

import re
from pathlib import Path

_CYCLE = re.compile(r"\(([^)]*)\)")


def read_permutation(line: str, n: int) -> tuple[int, ...]:
    """From cycle notation to a tuple `p` with `p[i]` = the image of `i`."""
    p = list(range(n))
    for body in _CYCLE.findall(line):
        points = [int(x) for x in body.replace(",", " ").split()]
        for a, b in zip(points, points[1:] + points[:1]):
            if not (0 <= a < n and 0 <= b < n):
                raise ValueError(f"point out of range in {line!r} (n={n})")
            p[a] = b
    return tuple(p)


def closure(generators: list[tuple[int, ...]], n: int,
             maximum: int = 2_000_000) -> list[tuple[int, ...]]:
    """The group generated, by breadth-first search. It includes the identity."""
    ident = tuple(range(n))
    seen = {ident}
    frontier = [ident]
    while frontier:
        new = []
        for q in frontier:
            for g in generators:
                r = tuple(g[q[i]] for i in range(n))
                if r not in seen:
                    seen.add(r)
                    new.append(r)
                    if len(seen) > maximum:
                        raise ValueError(f"group too large (> {maximum})")
        frontier = new
    return sorted(seen)


def apply(p: tuple[int, ...], word: int) -> int:
    """Permute a word's positions: the bit at `i` ends up at `p[i]`.

    Position 0 is the **rightmost** character of the bit string: that is the
    ordinary binary reading, and it is the convention of Brouwer's files. All four
    combinations were tried (string as written or reversed, permutation or its
    inverse), and only this one reproduces the published record A(24,6,12) >= 5558;
    the others give 8750 words with pairs at distance 4. The convention is not
    documented on the site: it was deduced by checking.
    """
    outside = 0
    for i in range(len(p)):
        if word >> i & 1:
            outside |= 1 << p[i]
    return outside


def blocks(n: int, declared: list[int]) -> list[int]:
    """The block sizes, completed until they cover `n`.

    The header `$EXEC cycle k1 k2 ...` lists the sizes of consecutive blocks, and
    they have to sum to n. When only one (or a few) are listed and the sum is less
    than n, the last one repeats until it fills up: that is the case of
    `$EXEC cycle 16` with n=32, which means 16+16. A remainder smaller than the last
    size becomes a block of its own. With no arguments: a single block of length n,
    that is the cyclic rotation of the whole word.
    """
    if not declared:
        return [n]
    sizes = list(declared)
    if sum(sizes) > n:
        raise ValueError(f"blocks {sizes} longer than n={n}")
    latest = sizes[-1]
    while n - sum(sizes) >= latest:
        sizes.append(latest)
    # the remainder, shorter than the last size, is made of fixed positions: this
    # is what makes A(22,10,7) and A(23,10,9) come out right, which with a short
    # final block gave orbits that were too large and invalid.
    sizes.extend([1] * (n - sum(sizes)))
    return sizes


def rotation(n: int, sizes: list[int]) -> tuple[int, ...]:
    """Rotate every block by one, simultaneously. Blocks of size 1 stay fixed.

    Blocks are counted from the **left of the bit string**, that is from the high
    positions: `cycle 1 24` on n=25 means that the first character written
    stays fixed and the following 24 rotate. Counting them from the other end the
    counts come out right but the codes turn out invalid — that is how the error
    came to light.
    """
    p = list(range(n))
    high = n
    for k in sizes:
        base = high - k
        for i in range(k):
            p[base + i] = base + (i + 1) % k
        high = base
    return tuple(p)


def expand_cyclic(path: str | Path) -> tuple[list[int], int, dict]:
    """The `$EXEC cycle k1 k2 ...` format: the orbit under block rotation.

    The words are written in groups separated by spaces (`11100 10010 ... 00`), and
    those groups are exactly the blocks: the spaces have to be stripped deliberately.
    """
    lines = [r.rstrip() for r in Path(path).read_text().splitlines()]
    lines = [r for r in lines if r.strip()]
    declared = [int(x) for x in lines[0].split()[2:]]
    seed_text = ["".join(r.split()) for r in lines[1:]
                  if r.strip() and r.strip() != ".."]
    seed_text = [r for r in seed_text if r and all(c in "01" for c in r)]
    if not seed_text:
        raise ValueError(f"{path}: no readable seed")
    n = max(len(r) for r in seed_text)
    discarded = [r for r in seed_text if len(r) != n]
    seed_text = [r for r in seed_text if len(r) == n]
    sizes = blocks(n, declared)
    group = closure([rotation(n, sizes)], n)
    words = set()
    for s in (int(r, 2) for r in seed_text):
        for p in group:
            words.add(apply(p, s))
    info = {"n": n, "generators": 1, "group_order": len(group),
            "seeds": len(seed_text), "words": len(words), "blocks": sizes,
            "righe_scartate": len(discarded)}
    return sorted(words), n, info


def expand(path: str | Path) -> tuple[list[int], int, dict]:
    """Read an `$EXEC orbit` file and return (words, n, info)."""
    lines = [r.rstrip() for r in Path(path).read_text().splitlines()]
    lines = [r for r in lines if r.strip()]
    if not lines or not lines[0].lower().startswith("$exec"):
        raise ValueError(f"{path}: not an $EXEC file")
    try:
        sep = next(i for i, r in enumerate(lines) if r.strip() == "..")
    except StopIteration:
        raise ValueError(f"{path}: the '..' separator is missing") from None

    # a second `..` at the end is only a terminator: it is ignored
    seed_text = [r.strip() for r in lines[sep + 1:] if r.strip() and r.strip() != ".."]
    if not seed_text or any(c not in "01" for c in seed_text[0]):
        raise ValueError(f"{path}: the seeds are not bit strings")
    n = len(seed_text[0])
    seeds = []
    for r in seed_text:
        if len(r) != n or any(c not in "01" for c in r):
            raise ValueError(f"{path}: seed of a different length: {r[:40]!r}")
        seeds.append(int(r, 2))

    gen = [read_permutation(r, n) for r in lines[1:sep] if "(" in r]
    group = closure(gen, n) if gen else [tuple(range(n))]

    words = set()
    for s in seeds:
        for p in group:
            words.add(apply(p, s))
    info = {"n": n, "generators": len(gen), "group_order": len(group),
            "seeds": len(seeds), "words": len(words)}
    return sorted(words), n, info
