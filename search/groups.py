"""
I gruppi sotto cui cercare.

PERCHÉ IL GRUPPO È TUTTO
------------------------
Dalla lettura dei codici pubblicati (vedi `orbits.py`) viene la lezione centrale
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


# --------------------------------------------------- corpi finiti: n = potenza di p
#
# Su 27 punti il gruppo naturale della teoria dei disegni non e' Z27 (ciclico) ma il
# gruppo additivo di F_27, che e' elementare abeliano (Z3)^3, e i suoi ampliamenti
# con la moltiplicazione per un generatore di F_27* (ordine 26). Sono gruppi diversi
# e danno orbite diverse: le costruzioni classiche dei disegni vivono qui.

def _campo(p: int, k: int):
    """F_{p^k} come interi 0..p^k-1, con somma e prodotto. Polinomio scelto per
    tentativi: il primo monico irriducibile in ordine lessicografico."""
    q = p ** k

    def cifre(x):
        c = []
        for _ in range(k):
            c.append(x % p)
            x //= p
        return c

    def numero(c):
        x = 0
        for i in reversed(range(k)):
            x = x * p + c[i]
        return x

    def somma(a, b):
        return numero([(x + y) % p for x, y in zip(cifre(a), cifre(b))])

    def prodotto_mod(a, b, modulo):
        ca, cb = cifre(a), cifre(b)
        grezzo = [0] * (2 * k - 1)
        for i, x in enumerate(ca):
            for j, y in enumerate(cb):
                grezzo[i + j] = (grezzo[i + j] + x * y) % p
        for i in reversed(range(k, 2 * k - 1)):
            c = grezzo[i]
            if c:
                grezzo[i] = 0
                for j in range(k):
                    grezzo[i - k + j] = (grezzo[i - k + j] - c * modulo[j]) % p
        return numero(grezzo[:k])

    for cand in range(q):
        modulo = cifre(cand)              # x^k = modulo (come polinomio di grado < k)
        prodotto = lambda a, b, m=modulo: prodotto_mod(a, b, m)
        # il polinomio e' buono se x genera un gruppo di ordine q-1 (primitivo)
        x = p
        visti, y, ordine = set(), x, 0
        while True:
            y = prodotto(y, 1) if ordine == 0 else prodotto(y, x)
            ordine += 1
            if y in visti or y == 0:
                break
            visti.add(y)
            if y == 1:
                break
        if y == 1 and ordine == q - 1:
            return somma, prodotto, x
    raise ValueError(f"nessun polinomio primitivo trovato per F_{p}^{k}")


def affine_campo(p: int, k: int, ordine_moltiplicativo: int | None = None):
    """Traslazioni di F_{p^k}, eventualmente con la moltiplicazione per g^m.

    Senza argomento: il solo gruppo additivo, elementare abeliano di ordine p^k.
    Con `ordine_moltiplicativo = h`: si aggiunge la moltiplicazione per un elemento
    di ordine h, ottenendo un gruppo di ordine p^k * h.
    """
    q = p ** k
    somma, prodotto, g = _campo(p, k)
    # Il gruppo additivo di F_{p^k} e' elementare abeliano di ordine p^k: NON si
    # genera aggiungendo 1 (che da' solo un ciclo di ordine p, la caratteristica).
    # Servono le traslazioni per ogni elemento della base 1, x, x^2, ...
    base = [p ** j for j in range(k)]
    generatori = [tuple(somma(i, b) for i in range(q)) for b in base]
    if ordine_moltiplicativo:
        if (q - 1) % ordine_moltiplicativo:
            raise ValueError(f"{ordine_moltiplicativo} non divide {q - 1}")
        e = (q - 1) // ordine_moltiplicativo
        m = 1
        for _ in range(e):
            m = prodotto(m, g)
        generatori.append(tuple(prodotto(m, i) for i in range(q)))
    return _chiudi(generatori, q)


def repertorio(n: int) -> dict[str, list[tuple[int, ...]]]:
    """Tutti i gruppi che vale la pena provare su n punti, con nomi parlanti."""
    fuori = dict(nome_gruppi(n))
    for p in (2, 3, 5, 7, 11, 13):
        k = 1
        while p ** k <= n:
            if p ** k == n and k > 1:
                try:
                    fuori[f"F{n}+"] = affine_campo(p, k)
                    for h in range(2, n):
                        if (n - 1) % h == 0:
                            fuori[f"F{n}:{h}"] = affine_campo(p, k, h)
                except ValueError:
                    pass
            k += 1
    return fuori
