"""
Espansione dei codici pubblicati dal format `$EXEC orbit`.

PERCHÉ SERVE, E COSA CI INSEGNA
-------------------------------
I codici record delle tables di Brouwer non sono pubblicati come elenchi di
words: sono pubblicati come **generators di un group di permutazioni più alcune
words seed**, e il code è l'unione delle orbits dei seeds below il group. Un
code di 5558 words sta in venticinque lines.

Questo non è only un format: è il **method** con cui quasi all_items questi record
sono stati found. Non si cercano 5558 words one per one — si search_for un group
adatto e poche words seed, e il group fa il resto. È l'informazione più utile
che abbiamo raccolto sulla strada A, e viene gratis dal leggere la source.

FORMATO
-------
    $EXEC orbit
    (23,2,8)(22,1,7)...        <- un generatore per line, in notazione ciclica
    ...
    ..                         <- separatore
    000111111111111000000000   <- words seed, one per line
    ...
"""
from __future__ import annotations

import re
from pathlib import Path

_CICLO = re.compile(r"\(([^)]*)\)")


def read_permutation(line: str, n: int) -> tuple[int, ...]:
    """Da notazione ciclica a one tupla `p` con `p[i]` = immagine di `i`."""
    p = list(range(n))
    for body in _CICLO.findall(line):
        points = [int(x) for x in body.replace(",", " ").split()]
        for a, b in zip(points, points[1:] + points[:1]):
            if not (0 <= a < n and 0 <= b < n):
                raise ValueError(f"punto outside intervallo in {line!r} (n={n})")
            p[a] = b
    return tuple(p)


def closure(generators: list[tuple[int, ...]], n: int,
             maximum: int = 2_000_000) -> list[tuple[int, ...]]:
    """Il group generato, per visita in ampiezza. Include l'identità."""
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
                        raise ValueError(f"group troppo grande (> {maximum})")
        frontier = new
    return sorted(seen)


def apply(p: tuple[int, ...], word: int) -> int:
    """Permuta le positions di one word: il bit in `i` finisce in `p[i]`.

    La position 0 e' il carattere **piu' a destra** della stringa di bit: e' la
    lettura binaria normale, ed e' la convenzione dei file di Brouwer. Provate
    all_items e quattro le combinazioni (stringa diritta o rovesciata, permutazione o
    inversa), only questa riproduce il record pubblicato A(24,6,12) >= 5558; le
    other_items danno 8750 words con pairs a distance 4. La convenzione non e'
    documentata sul sito: e' stata dedotta verificando.
    """
    outside = 0
    for i in range(len(p)):
        if word >> i & 1:
            outside |= 1 << p[i]
    return outside


def blocks(n: int, declared: list[int]) -> list[int]:
    """Le sizes dei blocks, completate fino a coprire `n`.

    L'header `$EXEC cycle k1 k2 ...` list_them le sizes dei blocks
    consecutivi, e la loro total_sum deve fare n. Quando ne e' elencata one sola (o
    poche) e la total_sum e' minore di n, l'latest si ripete fino a riempire: e' il
    caso di `$EXEC cycle 16` con n=32, che vuol dire 16+16. Un resto piu' piccolo
    dell'latest size diventa un block a se'. Senza arguments: un only block
    lungo n, cioe' la rotation ciclica di tutta la word.
    """
    if not declared:
        return [n]
    sizes = list(declared)
    if sum(sizes) > n:
        raise ValueError(f"blocks {sizes} piu' lunghi di n={n}")
    latest = sizes[-1]
    while n - sum(sizes) >= latest:
        sizes.append(latest)
    # il resto, piu' short dell'latest size, e' fatto di positions ferme: e'
    # cosi' che tornano A(22,10,7) e A(23,10,9), che con un block short finale
    # davano orbits troppo grandi e non valide.
    sizes.extend([1] * (n - sum(sizes)))
    return sizes


def rotation(n: int, sizes: list[int]) -> tuple[int, ...]:
    """Ruota di one, contemporaneamente, ogni block. I blocks di 1 sono fermi.

    I blocks si contano da **sinistra nella stringa di bit**, cioe' dalle
    positions alte: `cycle 1 24` su n=25 vuol dire che il first carattere scritto
    e' fisso e i 24 seguenti ruotano. Contandoli dall'altra parte i conteggi
    tornano ma i codici risultano non validi — e' cosi' che l'error e' venuto
    outside.
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
    """Il format `$EXEC cycle k1 k2 ...`: orbit below la rotation a blocks.

    Le words sono scritte a groups separati da spazi (`11100 10010 ... 00`), che
    sono proprio i blocks: gli spazi vanno tolti, non ignorati per caso.
    """
    lines = [r.rstrip() for r in Path(path).read_text().splitlines()]
    lines = [r for r in lines if r.strip()]
    declared = [int(x) for x in lines[0].split()[2:]]
    seed_text = ["".join(r.split()) for r in lines[1:]
                  if r.strip() and r.strip() != ".."]
    seed_text = [r for r in seed_text if r and all(c in "01" for c in r)]
    if not seed_text:
        raise ValueError(f"{path}: nessun seed leggibile")
    n = max(len(r) for r in seed_text)
    discarded = [r for r in seed_text if len(r) != n]
    seed_text = [r for r in seed_text if len(r) == n]
    sizes = blocks(n, declared)
    group = closure([rotation(n, sizes)], n)
    words = set()
    for s in (int(r, 2) for r in seed_text):
        for p in group:
            words.add(apply(p, s))
    info = {"n": n, "generators": 1, "ordine_gruppo": len(group),
            "seeds": len(seed_text), "words": len(words), "blocks": sizes,
            "righe_scartate": len(discarded)}
    return sorted(words), n, info


def expand(path: str | Path) -> tuple[list[int], int, dict]:
    """Legge un file `$EXEC orbit` e restituisce (words, n, informazioni)."""
    lines = [r.rstrip() for r in Path(path).read_text().splitlines()]
    lines = [r for r in lines if r.strip()]
    if not lines or not lines[0].lower().startswith("$exec"):
        raise ValueError(f"{path}: non è un file $EXEC")
    try:
        sep = next(i for i, r in enumerate(lines) if r.strip() == "..")
    except StopIteration:
        raise ValueError(f"{path}: manca il separatore '..'") from None

    # un second `..` in fondo e' only un terminatore: si ignora
    seed_text = [r.strip() for r in lines[sep + 1:] if r.strip() and r.strip() != ".."]
    if not seed_text or any(c not in "01" for c in seed_text[0]):
        raise ValueError(f"{path}: i seeds non sono stringhe di bit")
    n = len(seed_text[0])
    seeds = []
    for r in seed_text:
        if len(r) != n or any(c not in "01" for c in r):
            raise ValueError(f"{path}: seed di length diversa: {r[:40]!r}")
        seeds.append(int(r, 2))

    gen = [read_permutation(r, n) for r in lines[1:sep] if "(" in r]
    group = closure(gen, n) if gen else [tuple(range(n))]

    words = set()
    for s in seeds:
        for p in group:
            words.add(apply(p, s))
    info = {"n": n, "generators": len(gen), "ordine_gruppo": len(group),
            "seeds": len(seeds), "words": len(words)}
    return sorted(words), n, info
