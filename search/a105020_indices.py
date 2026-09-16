"""
A105020: esistono coppie (i, j) NON canoniche con a(i)=2n+1, a(j)=2n+3, j=i+n+1?

Controllo per calcolo della dimostrazione in docs/segnalazioni/A105020.md. Due ricerche
esaustive, scritte in modo diverso, con la funzione `a` copiata dalla definizione
dell'archivio (antidiagonalIndex con la radice intera, poi k, i, m e m^2 - i^2).

  indici   scorre TUTTI gli indici N < limite: per ogni a(N) dispari >= 3 guarda
           j = N + n + 1 e conta le coppie, canoniche (N = T_n) e no.
  valori   scorre le fattorizzazioni u = d(2s-d) con d dispari >= 3, cioe' TUTTI gli
           indici non canonici con valore <= limite, e controlla anche che a(i) = u
           (la parametrizzazione usata nella dimostrazione).
"""
import json
import math
import sys
import time
from pathlib import Path

import numba as nb
import numpy as np

RADICE = Path(__file__).resolve().parent.parent


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
def per_indici(fino, blocco):
    nb_ = (fino + blocco - 1) // blocco
    coppie = np.zeros(nb_, np.int64)
    noncan = np.zeros(nb_, np.int64)
    esempio = np.full(nb_, -1, np.int64)
    for b in nb.prange(nb_):
        lo = b * blocco
        hi = min(fino, lo + blocco)
        for N in range(lo, hi):
            v = a(N)
            if v >= 3 and v % 2 == 1:
                n = (v - 1) // 2
                if a(N + n + 1) == v + 2:
                    coppie[b] += 1
                    if N != n * (n + 1) // 2:
                        noncan[b] += 1
                        if esempio[b] < 0:
                            esempio[b] = N
    return coppie, noncan, esempio


@nb.njit(parallel=True)
def per_valori(U, dmin):
    dmax = isqrt(U)
    ds = np.arange(dmin, dmax + 1, 2)
    colpi = np.zeros(len(ds), np.int64)
    errori = np.zeros(len(ds), np.int64)
    giri = np.zeros(len(ds), np.int64)
    esempio = np.full(len(ds), -1, np.int64)
    for t in nb.prange(len(ds)):
        d = ds[t]
        s = d
        while True:
            u = d * (2 * s - d)
            if u > U:
                break
            if u >= 3:
                giri[t] += 1
                r = s - d
                i = s * (s + 1) // 2 - 1 - r
                if a(i) != u:
                    errori[t] += 1
                n = (u - 1) // 2
                if a(i + n + 1) == u + 2:
                    colpi[t] += 1
                    if esempio[t] < 0:
                        esempio[t] = i
            s += 1
    return ds, colpi, errori, giri, esempio


def main():
    modo, limite = sys.argv[1], int(float(sys.argv[2]))
    t0 = time.time()
    if modo == "indici":
        coppie, noncan, esempio = per_indici(limite, 50_000_000)
        attese = sum(1 for n in range(1, 10**7) if n * (n + 1) // 2 < limite)
        es = {"modo": modo, "indici_fino_a": limite, "coppie": int(coppie.sum()),
              "coppie_canoniche_attese": attese, "non_canoniche": int(noncan.sum()),
              "esempi": [int(x) for x in esempio if x >= 0][:10]}
    else:
        # collaudo con d = 1 su un intervallo piccolo: una coppia canonica per ogni n
        ds1, c1, e1, g1, _ = per_valori(2_000_001, 1)
        collaudo = {"canoniche_trovate_con_d1": int(c1[0]),
                    "attese": (2_000_001 - 1) // 2, "errori_parametrizzazione": int(e1.sum())}
        ds, colpi, errori, giri, esempio = per_valori(limite, 3)
        es = {"modo": modo, "valori_fino_a": limite, "collaudo_d1": collaudo,
              "fattorizzazioni_esaminate": int(giri.sum()),
              "errori_parametrizzazione": int(errori.sum()),
              "coppie_non_canoniche": int(colpi.sum()),
              "esempi": [int(x) for x in esempio if x >= 0][:10]}
    es["secondi"] = round(time.time() - t0, 1)
    print(json.dumps(es, indent=1), flush=True)
    (RADICE / "research_data" / f"a105020_{modo}.json").write_text(json.dumps(es, indent=1))


if __name__ == "__main__":
    main()
