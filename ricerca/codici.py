"""
Verificatore esatto di codici binari.

PERCHÉ QUESTO FILE È LA COSA PIÙ IMPORTANTE DELLA STRADA A
----------------------------------------------------------
Tutto il progetto finora si è appoggiato a un verificatore complicato: Lean, il
kernel, il comparator, la sandbox, l'impronta dell'archivio. Cinque volte ha
dovuto fermare la nostra stessa macchina che diceva «trovato».

Qui il verificatore è **questo file**, e si legge in cinque minuti. Un codice
binario a peso costante è una lista di parole; è valido se ogni parola ha la
lunghezza e il peso giusti e se ogni coppia dista almeno `d`. Sono confronti fra
interi: non c'è niente da interpretare, niente da elaborare, nessun ambiente che
possa essere configurato male, nessuna tattica che possa lasciare un `sorry`.

**La regola di questo file: non ottimizzare mai per velocità a costo della
chiarezza.** Se serve velocità, va in un altro file e questo resta il giudice.

CONVENZIONE
-----------
Una parola di lunghezza n è un `int`: il bit i (valore 2^i) dice se la posizione
i è a 1. Il peso è `int.bit_count()`. La distanza di Hamming fra due parole è
`(a ^ b).bit_count()`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path


@dataclass
class Esito:
    """Il verdetto. `ok` è vero solo se non c'è nessun difetto."""
    ok: bool
    dimensione: int
    difetti: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.ok:
            return f"VALIDO, {self.dimensione} parole"
        return (f"NON VALIDO ({len(self.difetti)} difetti): "
                + "; ".join(self.difetti[:5]))


def peso(parola: int) -> int:
    return parola.bit_count()


def distanza(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def verifica(parole, n: int, d: int, w: int | None = None,
             massimo_difetti: int = 20) -> Esito:
    """Verifica esatta di un codice binario.

    `w` non None: codice a peso costante. Nessuna scorciatoia, nessuna euristica:
    si controllano **tutte** le coppie.
    """
    parole = list(parole)
    difetti: list[str] = []

    def segnala(msg: str) -> bool:
        difetti.append(msg)
        return len(difetti) >= massimo_difetti

    if n <= 0:
        segnala(f"lunghezza n={n} non valida")
    limite = 1 << n
    visti: dict[int, int] = {}
    for i, p in enumerate(parole):
        if not isinstance(p, int) or p < 0:
            if segnala(f"parola {i}: non è un intero non negativo ({p!r})"):
                break
            continue
        if p >= limite:
            if segnala(f"parola {i}: usa bit oltre la posizione {n - 1}"):
                break
            continue
        if w is not None and peso(p) != w:
            if segnala(f"parola {i}: peso {peso(p)}, atteso {w}"):
                break
            continue
        if p in visti:
            if segnala(f"parola {i}: duplicato della parola {visti[p]}"):
                break
            continue
        visti[p] = i

    if not difetti:
        for (i, a), (j, b) in combinations(list(enumerate(parole)), 2):
            dist = distanza(a, b)
            if dist < d:
                if segnala(f"parole {i} e {j}: distanza {dist} < {d}"):
                    break

    return Esito(ok=not difetti, dimensione=len(parole), difetti=difetti)


# ---------------------------------------------------------------- lettura file

def leggi(percorso: str | Path, n: int | None = None) -> tuple[list[int], int]:
    """Legge un codice da un file di testo e restituisce (parole, n).

    Riconosce i due formati in cui questi codici circolano:

      * **posizioni**: ogni riga è la lista delle posizioni a 1, per es.
        `1 2 3 7` oppure `1,2,3,7`;
      * **bit**: ogni riga è una stringa di `0` e `1` della stessa lunghezza.

    Il formato si riconosce dalla prima riga utile, e poi si applica a tutte: un
    file misto è un errore, non un'occasione di indovinare.
    """
    righe = [r.strip() for r in Path(percorso).read_text().splitlines()]
    righe = [r for r in righe if r and not r.startswith("#")]
    if not righe:
        raise ValueError(f"{percorso}: nessuna riga utile")

    a_bit = all(c in "01" for c in righe[0]) and len(righe[0]) > 1
    parole: list[int] = []
    if a_bit:
        lung = len(righe[0])
        for k, r in enumerate(righe):
            if len(r) != lung or any(c not in "01" for c in r):
                raise ValueError(f"{percorso}: riga {k + 1} non è una stringa di "
                                 f"{lung} bit: {r[:40]!r}")
            parole.append(int(r[::-1], 2))
        dedotto = lung
    else:
        massimo = 0
        for k, r in enumerate(righe):
            pezzi = r.replace(",", " ").split()
            try:
                pos = [int(x) for x in pezzi]
            except ValueError:
                raise ValueError(f"{percorso}: riga {k + 1} non è una lista di "
                                 f"posizioni: {r[:40]!r}") from None
            if len(set(pos)) != len(pos):
                raise ValueError(f"{percorso}: riga {k + 1} ripete una posizione")
            base = 1 if min(pos) >= 1 else 0
            massimo = max(massimo, max(pos))
            parole.append(sum(1 << (p - base) for p in pos))
        dedotto = massimo  # posizioni 1..n
    return parole, (n if n is not None else dedotto)


# ------------------------------------------------- verifica rapida, ed esatta
#
# Per codici grandi il controllo di tutte le coppie è troppo lento in Python:
# 50.000 parole sono 1,25 miliardi di coppie. Esiste però un criterio
# **equivalente** e quasi istantaneo, valido per i codici a peso costante.
#
# Due parole distinte di peso w a distanza di Hamming `dist` hanno
#
#     dist = 2 · (w − |A ∩ B|)
#
# dove A e B sono i loro supporti: ogni posizione in A ma non in B, e viceversa,
# contribuisce 1. Quindi, per d pari,
#
#     dist ≥ d   ⟺   |A ∩ B| ≤ w − d/2 =: t
#
# e una violazione significa |A ∩ B| ≥ t+1, cioè **le due parole condividono un
# sottoinsieme di t+1 posizioni**. Basta allora elencare, per ogni parola, tutti i
# suoi sottoinsiemi di taglia t+1: il codice è valido se e solo se nessun
# sottoinsieme compare due volte. Il costo è m · C(w, t+1) invece di m²/2, e per i
# casi che ci interessano è quattro ordini di grandezza meno.
#
# Non è un'euristica né un'approssimazione: è lo stesso criterio, riscritto. Il
# test `test_rapido_e_lento_concordano` lo confronta con il giudice su migliaia di
# casi casuali, e `verifica` resta il giudice per i risultati che dichiariamo.

def posizioni(parola: int) -> tuple[int, ...]:
    fuori = []
    i = 0
    while parola:
        if parola & 1:
            fuori.append(i)
        parola >>= 1
        i += 1
    return tuple(fuori)


def verifica_veloce(parole, n: int, d: int, w: int) -> Esito:
    """Come `verifica`, per codici a peso costante con d pari, ma per m grandi."""
    if d % 2:
        raise ValueError(f"il criterio vale per d pari, ricevuto d={d}")
    parole = list(parole)
    t = w - d // 2
    if t < 0:
        return Esito(ok=False, dimensione=len(parole),
                     difetti=[f"d={d} è troppo grande per w={w}"])
    if t >= w:
        return verifica(parole, n, d, w)      # nessun vincolo utile: giudice

    difetti: list[str] = []
    limite = 1 << n
    for i, p in enumerate(parole):
        if not isinstance(p, int) or p < 0 or p >= limite:
            difetti.append(f"parola {i}: fuori dall'intervallo [0, 2^{n})")
        elif peso(p) != w:
            difetti.append(f"parola {i}: peso {peso(p)}, atteso {w}")
        if len(difetti) >= 20:
            break
    if difetti:
        return Esito(ok=False, dimensione=len(parole), difetti=difetti)

    visti: dict[tuple[int, ...], int] = {}
    for i, p in enumerate(parole):
        for sotto in combinations(posizioni(p), t + 1):
            altro = visti.get(sotto)
            if altro is not None:
                difetti.append(
                    f"parole {altro} e {i}: condividono le {t + 1} posizioni "
                    f"{list(sotto)}, quindi distano al più {2 * (w - t - 1)} < {d}")
                if len(difetti) >= 20:
                    return Esito(ok=False, dimensione=len(parole), difetti=difetti)
            else:
                visti[sotto] = i
    return Esito(ok=not difetti, dimensione=len(parole), difetti=difetti)
