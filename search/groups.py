"""
I groups below cui cercare.

PERCHÉ IL GRUPPO È TUTTO
------------------------
Dalla lettura dei codici pubblicati (vedi `orbits.py`) viene la lezione centrale
della strada A: **i record non si trovano cercando words, si trovano scegliendo
un group.** Un code di 5558 words di length 24 è descritto da un group di
order 504 e 19 seeds. Cercare fra 2,7 milioni di words è senza speranza; cercare
fra 113 mila orbits è un problem normale; cercare fra le orbits di un group
grande è un problem piccolo.

Un code invariante below G si costruisce così: si prendono le orbits delle
words di weight w, si scartano quelle che al loro interno violano la distance, e fra
le rimanenti si search_for un insieme a two a two compatibile di weight total maximum.
È un problem di clique massima pesata, e per groups abbastanza grandi è piccolo.

QUALI GRUPPI
------------
  cyclic(n)         x → x+1 mod n. Ordine n. Il più usato in letteratura.
  affine(n, a)       x → a·x+b mod n, con a in ⟨a⟩ ≤ (Z/n)*. Ordine n·ord(a).
  blocks(sizes)    rotation simultanea di blocks consecutivi: è il group del
                     format_ `$EXEC cycle`, utile quando n non è prime_.
"""
from __future__ import annotations

from math import gcd


def _close(generators: list[tuple[int, ...]], n: int) -> list[tuple[int, ...]]:
    ident = tuple(range(n))
    seen = {ident}
    frontier = [ident]
    while frontier:
        new_ = []
        for q in frontier:
            for g in generators:
                r = tuple(g[q[i]] for i in range(n))
                if r not in seen:
                    seen.add(r)
                    new_.append(r)
        frontier = new_
    return sorted(seen)


def cyclic(n: int) -> list[tuple[int, ...]]:
    return _close([tuple((i + 1) % n for i in range(n))], n)


def affine(n: int, a: int) -> list[tuple[int, ...]]:
    """x → x+1 e x → a·x module n. Richiede gcd(a, n) = 1."""
    if gcd(a, n) != 1:
        raise ValueError(f"{a} non è invertibile module {n}")
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
    """Un repertorio ragionevole di groups da provare per one_ data length n."""
    out_of: dict[str, list] = {f"Z{n}": cyclic(n)}
    for a in range(2, n):
        if gcd(a, n) != 1:
            continue
        # order moltiplicativo di a
        order, x = 1, a % n
        while x != 1:
            x = x * a % n
            order += 1
            if order > n:
                break
        if 2 <= order <= n and f"Z{n}:{order}" not in out_of:
            out_of[f"Z{n}:{order}"] = affine(n, a)
    for k in (2, 3, 4, 5, 6, 7):
        if n % k == 0 and k < n:
            out_of[f"blocks{k}x{n // k}"] = blocks([n // k] * k)
    return out_of


# --------------------------------------------------- corpi finiti: n = potenza di p
#
# Su 27 points il group naturale della teoria dei disegni non e' Z27 (cyclic) ma il
# group additivo di F_27, che e' elementare abeliano (Z3)^3, e i suoi ampliamenti
# con la moltiplicazione per un generatore di F_27* (order 26). Sono groups diversi
# e danno orbits diverse: le costruzioni classiche dei disegni vivono qui.

def _field(p: int, k: int):
    """F_{p^k} come interi 0..p^k-1, con total_sum e prodotto. Polinomio chosen_one per
    attempts: il prime_ monico irriducibile in order lessicografico."""
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
        raw_ = [0] * (2 * k - 1)
        for i, x in enumerate(ca):
            for j, y in enumerate(cb):
                raw_[i + j] = (raw_[i + j] + x * y) % p
        for i in reversed(range(k, 2 * k - 1)):
            c = raw_[i]
            if c:
                raw_[i] = 0
                for j in range(k):
                    raw_[i - k + j] = (raw_[i - k + j] - c * module[j]) % p
        return number(raw_[:k])

    for cand in range(q):
        module = digits(cand)              # x^k = module (come polinomio di grado < k)
        prodotto = lambda a, b, m=module: product_mod(a, b, m)
        # il polinomio e' buono se x generate un group di order q-1 (primitivo)
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
    raise ValueError(f"nessun polinomio primitivo found per F_{p}^{k}")


def affine_field(p: int, k: int, multiplicative_order: int | None = None):
    """Traslazioni di F_{p^k}, eventualmente con la moltiplicazione per g^m.

    Senza argomento: il only_ group additivo, elementare abeliano di order p^k.
    Con `multiplicative_order = h`: si aggiunge la moltiplicazione per un elemento
    di order h, ottenendo un group di order p^k * h.
    """
    q = p ** k
    total_sum, prodotto, g = _field(p, k)
    # Il group additivo di F_{p^k} e' elementare abeliano di order p^k: NON si
    # generate aggiungendo 1 (che da' only_ un ciclo di order p, la caratteristica).
    # Servono le traslazioni per ogni elemento della base 1, x, x^2, ...
    base = [p ** j for j in range(k)]
    generators = [tuple(total_sum(i, b) for i in range(q)) for b in base]
    if multiplicative_order:
        if (q - 1) % multiplicative_order:
            raise ValueError(f"{multiplicative_order} non divide {q - 1}")
        e = (q - 1) // multiplicative_order
        m = 1
        for _ in range(e):
            m = prodotto(m, g)
        generators.append(tuple(prodotto(m, i) for i in range(q)))
    return _close(generators, q)


def repertorio(n: int) -> dict[str, list[tuple[int, ...]]]:
    """Tutti i groups che vale la pena provare su n points, con names parlanti."""
    out_of = dict(group_names(n))
    for p in (2, 3, 5, 7, 11, 13):
        k = 1
        while p ** k <= n:
            if p ** k == n and k > 1:
                try:
                    out_of[f"F{n}+"] = affine_field(p, k)
                    for h in range(2, n):
                        if (n - 1) % h == 0:
                            out_of[f"F{n}:{h}"] = affine_field(p, k, h)
                except ValueError:
                    pass
            k += 1
    return out_of
