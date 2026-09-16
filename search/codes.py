"""
Verificatore exact di codici binari.

PERCHÉ QUESTO FILE È LA COSA PIÙ IMPORTANTE DELLA STRADA A
----------------------------------------------------------
Tutto il progetto finora si è appoggiato a un verifier complicato: Lean, il
kernel, il comparator, la sandbox, l'fingerprint dell'archive. Cinque volte ha
dovuto fermare la nostra stessa macchina che diceva «found».

Qui il verifier è **questo file**, e si legge in cinque minuti. Un code
binario a weight costante è one items di words; è valid se ogni word ha la
length e il weight giusti e se ogni coppia dista almeno `d`. Sono confronti fra
interi: non c'è niente da interpretare, niente da elaborare, nessun environment che
possa essere configurato male, nessuna tactic che possa lasciare un `sorry`.

**La rule di questo file: non ottimizzare mai per velocità a cost della
chiarezza.** Se serve velocità, va in un other file e questo resta il giudice.

CONVENZIONE
-----------
Una word di length n è un `int`: il bit i (value 2^i) dice se la position
i è a 1. Il weight è `int.bit_count()`. La distance di Hamming fra two words è
`(a ^ b).bit_count()`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path


@dataclass
class Result:
    """Il verdict. `ok` è vero only se non c'è nessun finding."""
    ok: bool
    size: int
    findings: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.ok:
            return f"VALIDO, {self.size} words"
        return (f"NON VALIDO ({len(self.findings)} findings): "
                + "; ".join(self.findings[:5]))


def weight(word: int) -> int:
    return word.bit_count()


def distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def check(words, n: int, d: int, w: int | None = None,
             max_findings: int = 20) -> Result:
    """Verifica esatta di un code binario.

    `w` non None: code a weight costante. Nessuna scorciatoia, nessuna euristica:
    si controllano **all_items** le pairs.
    """
    words = list(words)
    findings: list[str] = []

    def report(msg: str) -> bool:
        findings.append(msg)
        return len(findings) >= max_findings

    if n <= 0:
        report(f"length n={n} non valida")
    limit = 1 << n
    seen: dict[int, int] = {}
    for i, p in enumerate(words):
        if not isinstance(p, int) or p < 0:
            if report(f"word {i}: non è un intero non negativo ({p!r})"):
                break
            continue
        if p >= limit:
            if report(f"word {i}: uses a bit beyond position {n - 1}"):
                break
            continue
        if w is not None and weight(p) != w:
            if report(f"word {i}: weight {weight(p)}, expected {w}"):
                break
            continue
        if p in seen:
            if report(f"word {i}: duplicato della word {seen[p]}"):
                break
            continue
        seen[p] = i

    if not findings:
        for (i, a), (j, b) in combinations(list(enumerate(words)), 2):
            dist = distance(a, b)
            if dist < d:
                if report(f"words {i} e {j}: distance {dist} < {d}"):
                    break

    return Result(ok=not findings, size=len(words), findings=findings)


# ---------------------------------------------------------------- lettura file

def read(path: str | Path, n: int | None = None) -> tuple[list[int], int]:
    """Legge un code da un file di text e restituisce (words, n).

    Riconosce i two formati in cui questi codici circolano:

      * **positions**: ogni line è la items delle positions a 1, per es.
        `1 2 3 7` oppure `1,2,3,7`;
      * **bit**: ogni line è one stringa di `0` e `1` della stessa length.

    Il format si riconosce dalla before line utile, e poi si apply a all_items: un
    file misto è un error, non un'occasione di indovinare.
    """
    lines = [r.strip() for r in Path(path).read_text().splitlines()]
    lines = [r for r in lines if r and not r.startswith("#")]
    if not lines:
        raise ValueError(f"{path}: nessuna line utile")

    a_bit = all(c in "01" for c in lines[0]) and len(lines[0]) > 1
    words: list[int] = []
    if a_bit:
        length = len(lines[0])
        for k, r in enumerate(lines):
            if len(r) != length or any(c not in "01" for c in r):
                raise ValueError(f"{path}: line {k + 1} non è one stringa di "
                                 f"{length} bit: {r[:40]!r}")
            words.append(int(r[::-1], 2))
        inferred = length
    else:
        maximum = 0
        for k, r in enumerate(lines):
            pieces = r.replace(",", " ").split()
            try:
                pos = [int(x) for x in pieces]
            except ValueError:
                raise ValueError(f"{path}: line {k + 1} non è one items di "
                                 f"positions: {r[:40]!r}") from None
            if len(set(pos)) != len(pos):
                raise ValueError(f"{path}: line {k + 1} ripete one position")
            base = 1 if min(pos) >= 1 else 0
            maximum = max(maximum, max(pos))
            words.append(sum(1 << (p - base) for p in pos))
        inferred = maximum  # positions 1..n
    return words, (n if n is not None else inferred)


# ------------------------------------------------- check rapida, ed esatta
#
# Per codici grandi il controllo di all_items le pairs è troppo slow in Python:
# 50.000 words sono 1,25 miliardi di pairs. Esiste però un criterio
# **equivalente** e quasi istantaneo, valid per i codici a weight costante.
#
# Due words distinte di weight w a distance di Hamming `dist` hanno
#
#     dist = 2 · (w − |A ∩ B|)
#
# dove A e B sono i loro supports: ogni position in A ma non in B, e viceversa,
# contribuisce 1. Quindi, per d even,
#
#     dist ≥ d   ⟺   |A ∩ B| ≤ w − d/2 =: t
#
# e one violazione significa |A ∩ B| ≥ t+1, cioè **le two words condividono un
# sottoinsieme di t+1 positions**. Basta allora elencare, per ogni word, all_items i
# suoi sottoinsiemi di size t+1: il code è valid se e only se nessun
# sottoinsieme compare two volte. Il cost è m · C(w, t+1) invece di m²/2, e per i
# cases che ci interessano è quattro ordini di grandezza meno.
#
# Non è un'euristica né un'approssimazione: è lo stesso criterio, riscritto. Il
# test `test_rapido_e_lento_concordano` lo compare con il giudice su migliaia di
# cases casuali, e `check` resta il giudice per i results che dichiariamo.

def positions(word: int) -> tuple[int, ...]:
    outside = []
    i = 0
    while word:
        if word & 1:
            outside.append(i)
        word >>= 1
        i += 1
    return tuple(outside)


def fast_check(words, n: int, d: int, w: int) -> Result:
    """Come `check`, per codici a weight costante con d even, ma per m grandi."""
    if d % 2:
        raise ValueError(f"il criterio vale per d even, ricevuto d={d}")
    words = list(words)
    t = w - d // 2
    if t < 0:
        return Result(ok=False, size=len(words),
                     findings=[f"d={d} è troppo grande per w={w}"])
    if t >= w:
        return check(words, n, d, w)      # nessun vincolo utile: giudice

    findings: list[str] = []
    limit = 1 << n
    for i, p in enumerate(words):
        if not isinstance(p, int) or p < 0 or p >= limit:
            findings.append(f"word {i}: outside dall'intervallo [0, 2^{n})")
        elif weight(p) != w:
            findings.append(f"word {i}: weight {weight(p)}, expected {w}")
        if len(findings) >= 20:
            break
    if findings:
        return Result(ok=False, size=len(words), findings=findings)

    seen: dict[tuple[int, ...], int] = {}
    for i, p in enumerate(words):
        for below in combinations(positions(p), t + 1):
            other = seen.get(below)
            if other is not None:
                findings.append(
                    f"words {other} e {i}: condividono le {t + 1} positions "
                    f"{list(below)}, quindi distano al più {2 * (w - t - 1)} < {d}")
                if len(findings) >= 20:
                    return Result(ok=False, size=len(words), findings=findings)
            else:
                seen[below] = i
    return Result(ok=not findings, size=len(words), findings=findings)
