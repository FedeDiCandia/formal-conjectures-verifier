"""
I gruppi sotto cui cercare.

PERCHÉ IL GRUPPO È TUTTO
------------------------
Dalla lettura dei codici pubblicati (vedi `orbite.py`) viene la lezione centrale
della strada A: **i record non si trovano cercando parole, si trovano scegliendo
un gruppo.** Un codice di 5558 parole di lunghezza 24 è descritto da un gruppo di
ordine 504 e 19 semi. Cercare fra 2,7 milioni di parole è senza speranza; cercare
fra 113 mila orbite è un problema normale; cercare fra le orbite di un gruppo
grande è un problema piccolo.

Un codice invariante sotto G si costruisce così: si prendono le orbite delle
parole di peso w, si scartano quelle che al loro interno violano la distanza, e fra
le rimanenti si cerca un insieme a due a due compatibile di peso totale massimo.
È un problema di clique massima pesata, e per gruppi abbastanza grandi è piccolo.

QUALI GRUPPI
------------
  ciclico(n)         x → x+1 mod n. Ordine n. Il più usato in letteratura.
  affine(n, a)       x → a·x+b mod n, con a in ⟨a⟩ ≤ (Z/n)*. Ordine n·ord(a).
  blocchi(taglie)    rotazione simultanea di blocchi consecutivi: è il gruppo del
                     formato `$EXEC cycle`, utile quando n non è primo.
"""
from __future__ import annotations

from math import gcd


def _chiudi(generatori: list[tuple[int, ...]], n: int) -> list[tuple[int, ...]]:
    ident = tuple(range(n))
    visti = {ident}
    frontiera = [ident]
    while frontiera:
        nuova = []
        for q in frontiera:
            for g in generatori:
                r = tuple(g[q[i]] for i in range(n))
                if r not in visti:
                    visti.add(r)
                    nuova.append(r)
        frontiera = nuova
    return sorted(visti)


def ciclico(n: int) -> list[tuple[int, ...]]:
    return _chiudi([tuple((i + 1) % n for i in range(n))], n)


def affine(n: int, a: int) -> list[tuple[int, ...]]:
    """x → x+1 e x → a·x modulo n. Richiede gcd(a, n) = 1."""
    if gcd(a, n) != 1:
        raise ValueError(f"{a} non è invertibile modulo {n}")
    somma = tuple((i + 1) % n for i in range(n))
    molt = tuple((a * i) % n for i in range(n))
    return _chiudi([somma, molt], n)


def blocchi(taglie: list[int]) -> list[tuple[int, ...]]:
    n = sum(taglie)
    p = list(range(n))
    base = 0
    for k in taglie:
        for i in range(k):
            p[base + i] = base + (i + 1) % k
        base += k
    return _chiudi([tuple(p)], n)


def nome_gruppi(n: int) -> dict[str, list[tuple[int, ...]]]:
    """Un repertorio ragionevole di gruppi da provare per una data lunghezza n."""
    fuori: dict[str, list] = {f"Z{n}": ciclico(n)}
    for a in range(2, n):
        if gcd(a, n) != 1:
            continue
        # ordine moltiplicativo di a
        ordine, x = 1, a % n
        while x != 1:
            x = x * a % n
            ordine += 1
            if ordine > n:
                break
        if 2 <= ordine <= n and f"Z{n}:{ordine}" not in fuori:
            fuori[f"Z{n}:{ordine}"] = affine(n, a)
    for k in (2, 3, 4, 5, 6, 7):
        if n % k == 0 and k < n:
            fuori[f"blocchi{k}x{n // k}"] = blocchi([n // k] * k)
    return fuori
