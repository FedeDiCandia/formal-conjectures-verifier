"""
Local search with the conflict graph precomputed.

WHY, MEASURED
----------------
The first local engine (`tabu.py`) recomputes at every move the distances between
the entering word and every candidate: N·m bit counts per iteration. On A(17,6,6)
that is a million operations per move, about 2500 moves in twenty seconds. With so
few moves the search cannot even **add one word** to a valid code of 85: the leap
from 85 to 86 requires swapping several, and 2500 moves are not enough.


Here the work is done once. The **conflict** matrix is precomputed — bit `j` of row
`i` set if words `i` and `j` are at distance less than `d` — and a counter
`count[v]` = how many chosen words conflict with `v` is kept. Adding or removing a
word costs a sum of N integers, thousandths of what it cost before. This takes us
from thousands of moves to millions.

The matrix takes N²/8 bytes: 19 MB for N = 12,376, 700 MB for N = 74,613. Above the
cap one falls back to the slow engine, which is poorer but does not explode in memory.

THE CRITERION IS ALWAYS THE SAME
------------------------------
`count` counts the violations, and a code is valid when the sum of the conflicts of
the chosen words is zero. The final verdict still belongs to `codes.check`.
"""
from __future__ import annotations

import os

import numpy as np

from codes import fast_check
from tabu import _all_words

# The conflict matrix takes N²/8 bytes. The cap is configurable because the most
# interesting cell we have (A(27,8,5), gap 1) asks for 0.8 GB, and on 24 GB of RAM
# there is room -- but not if six processes are launched together. Whoever launches
# in parallel lowers the cap or reduces the processes.
MEMORY_CAP_BYTES = int(os.environ.get("SEARCH_MEMORY_CAP", 700_000_000))


def conflict_matrix(all_items: np.ndarray, d: int) -> np.ndarray:
    """Bit `j` of row `i` is set if `dist(i, j) < d` and `i != j`."""
    N = len(all_items)
    byte = (N + 7) // 8
    if N * byte > MEMORY_CAP_BYTES:
        raise MemoryError(f"the matrix would need {N * byte / 1e6:.0f} MB")
    M = np.zeros((N, byte), dtype=np.uint8)
    block = max(1, 8_000_000 // max(N, 1))
    for i in range(0, N, block):
        slice = all_items[i:i + block]
        neighbour = np.bitwise_count(np.bitwise_xor(slice[:, None], all_items[None, :])) < d
        for k in range(len(slice)):
            neighbour[k, i + k] = False          # no conflict with itself
        M[i:i + block] = np.packbits(neighbour, axis=1)
    return M


class State:
    """A set of chosen words, with the conflict count kept up to date."""

    def __init__(self, M: np.ndarray, N: int) -> None:
        self.M = M
        self.N = N
        self.count = np.zeros(N, dtype=np.int32)
        self.inside = np.zeros(N, dtype=bool)
        self.lines: dict[int, np.ndarray] = {}

    def line(self, i: int) -> np.ndarray:
        r = self.lines.get(i)
        if r is None:
            r = np.unpackbits(self.M[i], count=self.N).astype(np.int32)
            if len(self.lines) > 4096:
                self.lines.clear()
            self.lines[i] = r
        return r

    def add(self, i: int) -> None:
        self.count += self.line(i)
        self.inside[i] = True

    def strip(self, i: int) -> None:
        self.count -= self.line(i)
        self.inside[i] = False

    @property
    def choices(self) -> np.ndarray:
        return np.flatnonzero(self.inside)

    @property
    def violations(self) -> int:
        return int(self.count[self.inside].sum()) // 2


def search_size(n: int, d: int, w: int, m: int, *, moves: int = 200_000,
                     seed: int = 0, all_items: np.ndarray | None = None,
                     M: np.ndarray | None = None,
                     start: list[int] | None = None,
                     walk: float = 0.3) -> tuple[list[int], int]:
    """Look for a code of `m` words. Returns (words, fewest violations seen)."""
    all_items = _all_words(n, w) if all_items is None else all_items
    N = len(all_items)
    if m > N:
        return [], m * m
    M = conflict_matrix(all_items, d) if M is None else M
    rng = np.random.default_rng(seed)
    s = State(M, N)

    start_point = (list(start) if start is not None
                else [int(x) for x in rng.choice(N, size=m, replace=False)])
    for i in start_point[:m]:
        s.add(int(i))
    while int(s.inside.sum()) < m:            # complete by choosing the least conflicted
        cost = np.where(s.inside, 1 << 30, s.count)
        s.add(int(rng.choice(np.flatnonzero(cost == cost.min()))))

    best = s.violations
    best_list = s.choices.copy()
    tabu = np.zeros(N, dtype=np.int64)
    for step in range(moves):
        if s.violations == 0:
            break
        choices = s.choices
        conf = s.count[choices]
        if conf.max() == 0:
            break
        if rng.random() < walk:
            culprits = choices[conf > 0]
            exits = int(rng.choice(culprits))
        else:
            exits = int(rng.choice(choices[conf == conf.max()]))
        s.strip(exits)
        tabu[exits] = step + 4 + int(rng.integers(0, max(2, m // 3)))
        cost = np.where(s.inside, 1 << 30, s.count).astype(np.int64)
        cost += np.where(tabu > step, 1 << 10, 0)
        enters = int(rng.choice(np.flatnonzero(cost == cost.min())))
        s.add(enters)
        if s.violations < best:
            best = s.violations
            best_list = s.choices.copy()
    return [int(all_items[i]) for i in best_list], best


def climb(n: int, d: int, w: int, start_from: list[int], up_to: int, *,
         moves_per_step: int = 100_000, seed: int = 0,
         attempts: int = 4) -> dict:
    """From a valid code, one word at a time up to `up_to` (or as far as it can)."""
    all_items = _all_words(n, w)
    M = conflict_matrix(all_items, d)
    position = {int(p): k for k, p in enumerate(all_items)}
    words = sorted(start_from)
    rng = np.random.default_rng(seed)
    steps: dict[int, str] = {}
    while len(words) < up_to:
        milestone = len(words) + 1
        base = [position[p] for p in words]
        won = None
        for t in range(attempts):
            free = np.flatnonzero(~np.isin(np.arange(len(all_items)), base))
            new_items, viol = search_size(
                n, d, w, milestone, moves=moves_per_step,
                seed=seed * 1000 + milestone * 7 + t, all_items=all_items, M=M,
                start=base + [int(rng.choice(free))])
            if viol == 0:
                won = new_items
                break
        steps[milestone] = "succeeded" if won else "failed"
        if won is None:
            break
        words = sorted(won)
    v = fast_check(words, n, d, w)
    return {"size": len(words), "valid": v.ok, "steps": steps,
            "words": words if v.ok else [], "goal": up_to}
