"""
A105020: esistono pairs (i, j) NON canoniche con a(i)=2n+1, a(j)=2n+3, j=i+n+1?

Controllo per computation della dimostrazione in docs/segnalazioni/A105020.md. Due ricerche
esaustive, scritte in way diverso, con la funzione `a` copiata dalla definition
dell'archive (antidiagonalIndex con la root intera, poi k, i, m e m^2 - i^2).

  indices   scorre TUTTI gli indices N < limit: per ogni a(N) dispari >= 3 guarda
           j = N + n + 1 e count_ le pairs, canoniche (N = T_n) e no.
  valori   scorre le fattorizzazioni u = d(2s-d) con d dispari >= 3, cioe' TUTTI gli
           indices non canonici con value_ <= limit, e controlla also_ che a(i) = u
           (la parametrizzazione usata nella dimostrazione).
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
def by_indices(fino, block):
    nb_ = (fino + block - 1) // block
    pairs = np.zeros(nb_, np.int64)
    noncan = np.zeros(nb_, np.int64)
    example = np.full(nb_, -1, np.int64)
    for b in nb.prange(nb_):
        lo = b * block
        hi = min(fino, lo + block)
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
    way, limit = sys.argv[1], int(float(sys.argv[2]))
    t0 = time.time()
    if way == "indices":
        pairs, noncan, example = by_indices(limit, 50_000_000)
        expected_ = sum(1 for n in range(1, 10**7) if n * (n + 1) // 2 < limit)
        es = {"way": way, "indici_fino_a": limit, "pairs": int(pairs.sum()),
              "coppie_canoniche_attese": expected_, "non_canoniche": int(noncan.sum()),
              "esempi": [int(x) for x in example if x >= 0][:10]}
    else:
        # shakedown con d = 1 su un intervallo piccolo: one_ coppia canonica per ogni n
        ds1, c1, e1, g1, _ = by_values(2_000_001, 1)
        shakedown = {"canoniche_trovate_con_d1": int(c1[0]),
                    "expected_": (2_000_001 - 1) // 2, "errori_parametrizzazione": int(e1.sum())}
        ds, shots, errors, rounds, example = by_values(limit, 3)
        es = {"way": way, "valori_fino_a": limit, "collaudo_d1": shakedown,
              "fattorizzazioni_esaminate": int(rounds.sum()),
              "errori_parametrizzazione": int(errors.sum()),
              "coppie_non_canoniche": int(shots.sum()),
              "esempi": [int(x) for x in example if x >= 0][:10]}
    es["seconds"] = round(time.time() - t0, 1)
    print(json.dumps(es, indent=1), flush=True)
    (ROOT / "research_data" / f"a105020_{way}.json").write_text(json.dumps(es, indent=1))


if __name__ == "__main__":
    main()
