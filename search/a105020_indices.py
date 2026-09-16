"""
A105020: are there NON-canonical pairs (i, j) with a(i)=2n+1, a(j)=2n+3, j=i+n+1?

A computational check of the proof in the A105020 note. Two exhaustive searches,
written differently, with the function `a` copied from the archive's definition
(antidiagonalIndex with the integer root, then k, i, m and m^2 - i^2).

  indices  runs over EVERY index N < limit: for each odd a(N) >= 3 it looks at
           j = N + n + 1 and counts the pairs, canonical (N = T_n) and not.
  values   runs over the factorisations u = d(2s-d) with odd d >= 3, that is EVERY
           non-canonical index with value <= limit, and also checks that a(i) = u
           (the parametrisation used in the proof).
"""
import json
import math
import sys
import time
from pathlib import Path

import numba as nb
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


@nb.njit(inline="always")
def isqrt(x):
    r = np.int64(math.sqrt(np.float64(x)))
    while r * r > x:
        r -= 1
    while (r + 1) * (r + 1) <= x:
        r += 1
    return r


@nb.njit(inline="always")
def a(N):
    c = (isqrt(8 * N + 1) - 1) // 2      # antidiagonalIndex
    k = N - c * (c + 1) // 2             # n - triangularNumber c
    i = c - k
    m = c + 1
    return m * m - i * i


@nb.njit(parallel=True)
def by_indices(up_to, block):
    nb_ = (up_to + block - 1) // block
    pairs = np.zeros(nb_, np.int64)
    noncan = np.zeros(nb_, np.int64)
    example = np.full(nb_, -1, np.int64)
    for b in nb.prange(nb_):
        lo = b * block
        hi = min(up_to, lo + block)
        for N in range(lo, hi):
            v = a(N)
            if v >= 3 and v % 2 == 1:
                n = (v - 1) // 2
                if a(N + n + 1) == v + 2:
                    pairs[b] += 1
                    if N != n * (n + 1) // 2:
                        noncan[b] += 1
                        if example[b] < 0:
                            example[b] = N
    return pairs, noncan, example


@nb.njit(parallel=True)
def by_values(U, dmin):
    dmax = isqrt(U)
    ds = np.arange(dmin, dmax + 1, 2)
    shots = np.zeros(len(ds), np.int64)
    errors = np.zeros(len(ds), np.int64)
    rounds = np.zeros(len(ds), np.int64)
    example = np.full(len(ds), -1, np.int64)
    for t in nb.prange(len(ds)):
        d = ds[t]
        s = d
        while True:
            u = d * (2 * s - d)
            if u > U:
                break
            if u >= 3:
                rounds[t] += 1
                r = s - d
                i = s * (s + 1) // 2 - 1 - r
                if a(i) != u:
                    errors[t] += 1
                n = (u - 1) // 2
                if a(i + n + 1) == u + 2:
                    shots[t] += 1
                    if example[t] < 0:
                        example[t] = i
            s += 1
    return ds, shots, errors, rounds, example


def main():
    route, limit = sys.argv[1], int(float(sys.argv[2]))
    t0 = time.time()
    if route == "indices":
        pairs, noncan, example = by_indices(limit, 50_000_000)
        expected = sum(1 for n in range(1, 10**7) if n * (n + 1) // 2 < limit)
        es = {"route": route, "indices_up_to": limit, "pairs": int(pairs.sum()),
              "canonical_pairs_expected": expected, "non_canonical": int(noncan.sum()),
              "examples": [int(x) for x in example if x >= 0][:10]}
    else:
        # shakedown with d = 1 on a small interval: one canonical pair for each n
        ds1, c1, e1, g1, _ = by_values(2_000_001, 1)
        shakedown = {"canonical_found_with_d1": int(c1[0]),
                    "expected": (2_000_001 - 1) // 2, "parametrisation_errors": int(e1.sum())}
        ds, shots, errors, rounds, example = by_values(limit, 3)
        es = {"route": route, "values_up_to": limit, "shakedown_d1": shakedown,
              "factorisations_examined": int(rounds.sum()),
              "parametrisation_errors": int(errors.sum()),
              "non_canonical_pairs": int(shots.sum()),
              "examples": [int(x) for x in example if x >= 0][:10]}
    es["seconds"] = round(time.time() - t0, 1)
    print(json.dumps(es, indent=1), flush=True)
    (ROOT / "research_data" / f"a105020_{route}.json").write_text(json.dumps(es, indent=1))


if __name__ == "__main__":
    main()
