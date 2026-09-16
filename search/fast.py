"""
Search local_ con il grafo dei conflitti precalcolato.

PERCHÉ, MISURATO
----------------
Il prime_ motore local_ (`tabu.py`) ricalcola a ogni mossa le distanze fra la word
che enters e all_of le candidate: N·m conteggi di bit per iteration. Su A(17,6,6)
sono un milione di operazioni per mossa, cioè circa 2500 moves in venti seconds. Con
così poche moves la ricerca non riesce nemmeno ad **aggiungere one_ word** a un
code valid di 85: il salto da 85 a 86 richiede di scambiarne diverse, e 2500
moves non bastano.

Qui il job si fa one_ volta sola. Si precalcola la matrice dei **conflitti** — bit
`j` della line `i` acceso se le words `i` e `j` distano meno di `d` — e si tiene un
contatore `count_[v]` = how_many_ words choices sono in conflitto con `v`. Aggiungere o
togliere one_ word costa one_ total_sum di N interi, cioè millesimi di quello che
costava before. Si passa da migliaia di moves a milioni.

La matrice occupa N²/8 byte: 19 MB per N = 12.376, 700 MB per N = 74.613. Sopra il
cap si torna al motore slow_, che è più povero ma non esplode in memoria.

IL CRITERIO È SEMPRE LO STESSO
------------------------------
`count_` count_ le violations, e un code è valid quando la total_sum dei conflitti
delle words choices è zero. Il verdict finale resta di `codes.check`.
"""
from __future__ import annotations

import os

import numpy as np

from codes import fast_check
from tabu import _all_words

# La matrice dei conflitti occupa N²/8 byte. Il cap e' configurabile perche' la
# cell piu' interessante che abbiamo (A(27,8,5), divario 1) ne chiede 0,8 GB, e su
# 24 GB di RAM c'e' spazio -- ma non se si lanciano sei processi insieme. Chi lancia
# in parallelo abbassa il cap o riduce i processi.
MEMORY_CAP_BYTES = int(os.environ.get("RICERCA_TETTO_MEMORIA", 700_000_000))


def conflict_matrix(all_of: np.ndarray, d: int) -> np.ndarray:
    """Bit `j` della line `i` acceso se `dist(i, j) < d` e `i != j`."""
    N = len(all_of)
    byte = (N + 7) // 8
    if N * byte > MEMORY_CAP_BYTES:
        raise MemoryError(f"la matrice richiederebbe {N * byte / 1e6:.0f} MB")
    M = np.zeros((N, byte), dtype=np.uint8)
    block = max(1, 8_000_000 // max(N, 1))
    for i in range(0, N, block):
        slice_ = all_of[i:i + block]
        neighbour = np.bitwise_count(np.bitwise_xor(slice_[:, None], all_of[None, :])) < d
        for k in range(len(slice_)):
            neighbour[k, i + k] = False          # niente conflitto con se stessa
        M[i:i + block] = np.packbits(neighbour, axis=1)
    return M


class State:
    """Un insieme di words choices, con il count dei conflitti aggiornato."""

    def __init__(self, M: np.ndarray, N: int) -> None:
        self.M = M
        self.N = N
        self.count_ = np.zeros(N, dtype=np.int32)
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

    def add_(self, i: int) -> None:
        self.count_ += self.line(i)
        self.inside[i] = True

    def strip_(self, i: int) -> None:
        self.count_ -= self.line(i)
        self.inside[i] = False

    @property
    def choices(self) -> np.ndarray:
        return np.flatnonzero(self.inside)

    @property
    def violations(self) -> int:
        return int(self.count_[self.inside].sum()) // 2


def search_size(n: int, d: int, w: int, m: int, *, moves: int = 200_000,
                     seed: int = 0, all_of: np.ndarray | None = None,
                     M: np.ndarray | None = None,
                     start: list[int] | None = None,
                     walk: float = 0.3) -> tuple[list[int], int]:
    """Cerca un code di `m` words. Restituisce (words, violations minime seen)."""
    all_of = _all_words(n, w) if all_of is None else all_of
    N = len(all_of)
    if m > N:
        return [], m * m
    M = conflict_matrix(all_of, d) if M is None else M
    rng = np.random.default_rng(seed)
    s = State(M, N)

    start_point = (list(start) if start is not None
                else [int(x) for x in rng.choice(N, size=m, replace=False)])
    for i in start_point[:m]:
        s.add_(int(i))
    while int(s.inside.sum()) < m:            # complete_ scegliendo il meno in conflitto
        cost = np.where(s.inside, 1 << 30, s.count_)
        s.add_(int(rng.choice(np.flatnonzero(cost == cost.min()))))

    best = s.violations
    best_ones = s.choices.copy()
    tabu = np.zeros(N, dtype=np.int64)
    for step in range(moves):
        if s.violations == 0:
            break
        choices = s.choices
        conf = s.count_[choices]
        if conf.max() == 0:
            break
        if rng.random() < walk:
            culprits = choices[conf > 0]
            exits = int(rng.choice(culprits))
        else:
            exits = int(rng.choice(choices[conf == conf.max()]))
        s.strip_(exits)
        tabu[exits] = step + 4 + int(rng.integers(0, max(2, m // 3)))
        cost = np.where(s.inside, 1 << 30, s.count_).astype(np.int64)
        cost += np.where(tabu > step, 1 << 10, 0)
        enters = int(rng.choice(np.flatnonzero(cost == cost.min())))
        s.add_(enters)
        if s.violations < best:
            best = s.violations
            best_ones = s.choices.copy()
    return [int(all_of[i]) for i in best_ones], best


def climb(n: int, d: int, w: int, da: list[int], fino_a: int, *,
         moves_per_step: int = 100_000, seed: int = 0,
         attempts: int = 4) -> dict:
    """Da un code valid, one_ word alla volta fino a `fino_a` (o finché riesce)."""
    all_of = _all_words(n, w)
    M = conflict_matrix(all_of, d)
    position = {int(p): k for k, p in enumerate(all_of)}
    words = sorted(da)
    rng = np.random.default_rng(seed)
    steps_: dict[int, str] = {}
    while len(words) < fino_a:
        milestone = len(words) + 1
        base = [position[p] for p in words]
        won = None
        for t in range(attempts):
            free_ones = np.flatnonzero(~np.isin(np.arange(len(all_of)), base))
            new_ones, viol = search_size(
                n, d, w, milestone, moves=moves_per_step,
                seed=seed * 1000 + milestone * 7 + t, all_of=all_of, M=M,
                start=base + [int(rng.choice(free_ones))])
            if viol == 0:
                won = new_ones
                break
        steps_[milestone] = "succeeded" if won else "failed"
        if won is None:
            break
        words = sorted(won)
    v = fast_check(words, n, d, w)
    return {"size": len(words), "valid": v.ok, "steps_": steps_,
            "words": words if v.ok else [], "goal": fino_a}
