"""
The groups to search under.

WHY THE GROUP IS EVERYTHING
------------------------
Reading the published codes (see `orbits.py`) gives the central lesson of this
route: **records are not found by looking for words, they are found by choosing a
group.** A code of 5558 words of length 24 is described by a group of order 504 and
19 seeds. Searching among 2.7 million words is hopeless; searching among 113
thousand orbits is an ordinary problem; searching among the orbits of a large group
is a small problem.

An invariant code under G is built like this: take the orbits of the words of weight
w, discard those that violate the distance internally, and among the rest look for a
pairwise compatible set of maximum total weight.
It is a maximum weighted clique problem, and for large enough groups it is small.

WHICH GROUPS
------------
  cyclic(n)         x → x+1 mod n. Order n. The commonest in the literature.
  affine(n, a)      x → a·x+b mod n, with a in ⟨a⟩ ≤ (Z/n)*. Order n·ord(a).
  blocks(sizes)     simultaneous rotation of consecutive blocks: the group of the
                    `$EXEC cycle` format, useful when n is not prime.
"""
from __future__ import annotations

from math import gcd


def _close(generators: list[tuple[int, ...]], n: int) -> list[tuple[int, ...]]:
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
        frontier = new
    return sorted(seen)


def cyclic(n: int) -> list[tuple[int, ...]]:
    return _close([tuple((i + 1) % n for i in range(n))], n)


def affine(n: int, a: int) -> list[tuple[int, ...]]:
    """x → x+1 and x → a·x mod n. Requires gcd(a, n) = 1."""
    if gcd(a, n) != 1:
        raise ValueError(f"{a} is not invertible mod {n}")
    total_sum = tuple((i + 1) % n for i in range(n))
    mult = tuple((a * i) % n for i in range(n))
    return _close([total_sum, mult], n)


def blocks(sizes: list[int]) -> list[tuple[int, ...]]:
    n = sum(sizes)
    p = list(range(n))
    base = 0
    for k in sizes:
        for i in range(k):
            p[base + i] = base + (i + 1) % k
        base += k
    return _close([tuple(p)], n)


def group_names(n: int) -> dict[str, list[tuple[int, ...]]]:
    """A reasonable repertoire of groups to try for a given length n."""
    outside: dict[str, list] = {f"Z{n}": cyclic(n)}
    for a in range(2, n):
        if gcd(a, n) != 1:
            continue
        # multiplicative order of a
        order, x = 1, a % n
        while x != 1:
            x = x * a % n
            order += 1
            if order > n:
                break
        if 2 <= order <= n and f"Z{n}:{order}" not in outside:
            outside[f"Z{n}:{order}"] = affine(n, a)
    for k in (2, 3, 4, 5, 6, 7):
        if n % k == 0 and k < n:
            outside[f"blocks{k}x{n // k}"] = blocks([n // k] * k)
    return outside


# ------------------------------------------- finite fields: n = a power of p
#
# On 27 points the natural group of design theory is not Z27 (cyclic) but the
# additive group of F_27, which is elementary abelian (Z3)^3, and its extensions by
# multiplication by a generator of F_27* (order 26). They are different groups and
# give different orbits: the classical design constructions live here.

def _field(p: int, k: int):
    """F_{p^k} as integers 0..p^k-1, with sum and product. The polynomial is chosen by
    trial: the first monic irreducible one in lexicographic order."""
    q = p ** k

    def digits(x):
        c = []
        for _ in range(k):
            c.append(x % p)
            x //= p
        return c

    def number(c):
        x = 0
        for i in reversed(range(k)):
            x = x * p + c[i]
        return x

    def total_sum(a, b):
        return number([(x + y) % p for x, y in zip(digits(a), digits(b))])

    def product_mod(a, b, module):
        ca, cb = digits(a), digits(b)
        raw = [0] * (2 * k - 1)
        for i, x in enumerate(ca):
            for j, y in enumerate(cb):
                raw[i + j] = (raw[i + j] + x * y) % p
        for i in reversed(range(k, 2 * k - 1)):
            c = raw[i]
            if c:
                raw[i] = 0
                for j in range(k):
                    raw[i - k + j] = (raw[i - k + j] - c * module[j]) % p
        return number(raw[:k])

    for cand in range(q):
        module = digits(cand)              # x^k = module (as a polynomial of degree < k)
        prodotto = lambda a, b, m=module: product_mod(a, b, m)
        # the polynomial is good if x generates a group of order q-1 (primitive)
        x = p
        seen, y, order = set(), x, 0
        while True:
            y = prodotto(y, 1) if order == 0 else prodotto(y, x)
            order += 1
            if y in seen or y == 0:
                break
            seen.add(y)
            if y == 1:
                break
        if y == 1 and order == q - 1:
            return total_sum, prodotto, x
    raise ValueError(f"no primitive polynomial found for F_{p}^{k}")


def affine_field(p: int, k: int, multiplicative_order: int | None = None):
    """Translations of F_{p^k}, optionally with multiplication by g^m.

    With no argument: the additive group alone, elementary abelian of order p^k.
    With `multiplicative_order = h`: multiplication by an element of order h is
    added, giving a group of order p^k * h.
    """
    q = p ** k
    total_sum, prodotto, g = _field(p, k)
    # The additive group of F_{p^k} is elementary abelian of order p^k: it is NOT
    # generated by adding 1 (which gives only a cycle of order p, the characteristic).
    # Translations by every basis element 1, x, x^2, ... are needed.
    base = [p ** j for j in range(k)]
    generators = [tuple(total_sum(i, b) for i in range(q)) for b in base]
    if multiplicative_order:
        if (q - 1) % multiplicative_order:
            raise ValueError(f"{multiplicative_order} does not divide {q - 1}")
        e = (q - 1) // multiplicative_order
        m = 1
        for _ in range(e):
            m = prodotto(m, g)
        generators.append(tuple(prodotto(m, i) for i in range(q)))
    return _close(generators, q)


def repertorio(n: int) -> dict[str, list[tuple[int, ...]]]:
    """Every group worth trying on n points, with descriptive names."""
    outside = dict(group_names(n))
    for p in (2, 3, 5, 7, 11, 13):
        k = 1
        while p ** k <= n:
            if p ** k == n and k > 1:
                try:
                    outside[f"F{n}+"] = affine_field(p, k)
                    for h in range(2, n):
                        if (n - 1) % h == 0:
                            outside[f"F{n}:{h}"] = affine_field(p, k, h)
                except ValueError:
                    pass
            k += 1
    return outside
