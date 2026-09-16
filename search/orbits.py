"""
Espansione dei codici pubblicati dal formato `$EXEC orbit`.

PERCHÉ SERVE, E COSA CI INSEGNA
-------------------------------
I codici record delle tabelle di Brouwer non sono pubblicati come elenchi di
parole: sono pubblicati come **generatori di un gruppo di permutazioni più alcune
parole seme**, e il codice è l'unione delle orbite dei semi sotto il gruppo. Un
codice di 5558 parole sta in venticinque righe.

Questo non è solo un formato: è il **metodo** con cui quasi tutti questi record
sono stati trovati. Non si cercano 5558 parole una per una — si cerca un gruppo
adatto e poche parole seme, e il gruppo fa il resto. È l'informazione più utile
che abbiamo raccolto sulla strada A, e viene gratis dal leggere la fonte.

FORMATO
-------
    $EXEC orbit
    (23,2,8)(22,1,7)...        <- un generatore per riga, in notazione ciclica
    ...
    ..                         <- separatore
    000111111111111000000000   <- parole seme, una per riga
    ...
"""
from __future__ import annotations

import re
from pathlib import Path

_CICLO = re.compile(r"\(([^)]*)\)")


def leggi_permutazione(riga: str, n: int) -> tuple[int, ...]:
    """Da notazione ciclica a una tupla `p` con `p[i]` = immagine di `i`."""
    p = list(range(n))
    for corpo in _CICLO.findall(riga):
        punti = [int(x) for x in corpo.replace(",", " ").split()]
        for a, b in zip(punti, punti[1:] + punti[:1]):
            if not (0 <= a < n and 0 <= b < n):
                raise ValueError(f"punto fuori intervallo in {riga!r} (n={n})")
            p[a] = b
    return tuple(p)


def chiusura(generatori: list[tuple[int, ...]], n: int,
             massimo: int = 2_000_000) -> list[tuple[int, ...]]:
    """Il gruppo generato, per visita in ampiezza. Include l'identità."""
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
                    if len(visti) > massimo:
                        raise ValueError(f"gruppo troppo grande (> {massimo})")
        frontiera = nuova
    return sorted(visti)


def applica(p: tuple[int, ...], parola: int) -> int:
    """Permuta le posizioni di una parola: il bit in `i` finisce in `p[i]`.

    La posizione 0 e' il carattere **piu' a destra** della stringa di bit: e' la
    lettura binaria normale, ed e' la convenzione dei file di Brouwer. Provate
    tutte e quattro le combinazioni (stringa diritta o rovesciata, permutazione o
    inversa), solo questa riproduce il record pubblicato A(24,6,12) >= 5558; le
    altre danno 8750 parole con coppie a distanza 4. La convenzione non e'
    documentata sul sito: e' stata dedotta verificando.
    """
    fuori = 0
    for i in range(len(p)):
        if parola >> i & 1:
            fuori |= 1 << p[i]
    return fuori


def blocchi(n: int, dichiarati: list[int]) -> list[int]:
    """Le taglie dei blocchi, completate fino a coprire `n`.

    L'intestazione `$EXEC cycle k1 k2 ...` elenca le taglie dei blocchi
    consecutivi, e la loro somma deve fare n. Quando ne e' elencata una sola (o
    poche) e la somma e' minore di n, l'ultima si ripete fino a riempire: e' il
    caso di `$EXEC cycle 16` con n=32, che vuol dire 16+16. Un resto piu' piccolo
    dell'ultima taglia diventa un blocco a se'. Senza argomenti: un solo blocco
    lungo n, cioe' la rotazione ciclica di tutta la parola.
    """
    if not dichiarati:
        return [n]
    taglie = list(dichiarati)
    if sum(taglie) > n:
        raise ValueError(f"blocchi {taglie} piu' lunghi di n={n}")
    ultima = taglie[-1]
    while n - sum(taglie) >= ultima:
        taglie.append(ultima)
    # il resto, piu' corto dell'ultima taglia, e' fatto di posizioni ferme: e'
    # cosi' che tornano A(22,10,7) e A(23,10,9), che con un blocco corto finale
    # davano orbite troppo grandi e non valide.
    taglie.extend([1] * (n - sum(taglie)))
    return taglie


def rotazione(n: int, taglie: list[int]) -> tuple[int, ...]:
    """Ruota di uno, contemporaneamente, ogni blocco. I blocchi di 1 sono fermi.

    I blocchi si contano da **sinistra nella stringa di bit**, cioe' dalle
    posizioni alte: `cycle 1 24` su n=25 vuol dire che il primo carattere scritto
    e' fisso e i 24 seguenti ruotano. Contandoli dall'altra parte i conteggi
    tornano ma i codici risultano non validi — e' cosi' che l'errore e' venuto
    fuori.
    """
    p = list(range(n))
    alto = n
    for k in taglie:
        base = alto - k
        for i in range(k):
            p[base + i] = base + (i + 1) % k
        alto = base
    return tuple(p)


def espandi_ciclico(percorso: str | Path) -> tuple[list[int], int, dict]:
    """Il formato `$EXEC cycle k1 k2 ...`: orbita sotto la rotazione a blocchi.

    Le parole sono scritte a gruppi separati da spazi (`11100 10010 ... 00`), che
    sono proprio i blocchi: gli spazi vanno tolti, non ignorati per caso.
    """
    righe = [r.rstrip() for r in Path(percorso).read_text().splitlines()]
    righe = [r for r in righe if r.strip()]
    dichiarati = [int(x) for x in righe[0].split()[2:]]
    semi_testo = ["".join(r.split()) for r in righe[1:]
                  if r.strip() and r.strip() != ".."]
    semi_testo = [r for r in semi_testo if r and all(c in "01" for c in r)]
    if not semi_testo:
        raise ValueError(f"{percorso}: nessun seme leggibile")
    n = max(len(r) for r in semi_testo)
    scartate = [r for r in semi_testo if len(r) != n]
    semi_testo = [r for r in semi_testo if len(r) == n]
    taglie = blocchi(n, dichiarati)
    gruppo = chiusura([rotazione(n, taglie)], n)
    parole = set()
    for s in (int(r, 2) for r in semi_testo):
        for p in gruppo:
            parole.add(applica(p, s))
    info = {"n": n, "generatori": 1, "ordine_gruppo": len(gruppo),
            "semi": len(semi_testo), "parole": len(parole), "blocchi": taglie,
            "righe_scartate": len(scartate)}
    return sorted(parole), n, info


def espandi(percorso: str | Path) -> tuple[list[int], int, dict]:
    """Legge un file `$EXEC orbit` e restituisce (parole, n, informazioni)."""
    righe = [r.rstrip() for r in Path(percorso).read_text().splitlines()]
    righe = [r for r in righe if r.strip()]
    if not righe or not righe[0].lower().startswith("$exec"):
        raise ValueError(f"{percorso}: non è un file $EXEC")
    try:
        sep = next(i for i, r in enumerate(righe) if r.strip() == "..")
    except StopIteration:
        raise ValueError(f"{percorso}: manca il separatore '..'") from None

    # un secondo `..` in fondo e' solo un terminatore: si ignora
    semi_testo = [r.strip() for r in righe[sep + 1:] if r.strip() and r.strip() != ".."]
    if not semi_testo or any(c not in "01" for c in semi_testo[0]):
        raise ValueError(f"{percorso}: i semi non sono stringhe di bit")
    n = len(semi_testo[0])
    semi = []
    for r in semi_testo:
        if len(r) != n or any(c not in "01" for c in r):
            raise ValueError(f"{percorso}: seme di lunghezza diversa: {r[:40]!r}")
        semi.append(int(r, 2))

    gen = [leggi_permutazione(r, n) for r in righe[1:sep] if "(" in r]
    gruppo = chiusura(gen, n) if gen else [tuple(range(n))]

    parole = set()
    for s in semi:
        for p in gruppo:
            parole.add(applica(p, s))
    info = {"n": n, "generatori": len(gen), "ordine_gruppo": len(gruppo),
            "semi": len(semi), "parole": len(parole)}
    return sorted(parole), n, info
