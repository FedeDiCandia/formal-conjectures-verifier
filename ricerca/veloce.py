"""
Ricerca locale con il grafo dei conflitti precalcolato.

PERCHÉ, MISURATO
----------------
Il primo motore locale (`tabu.py`) ricalcola a ogni mossa le distanze fra la parola
che entra e tutte le candidate: N·m conteggi di bit per iterazione. Su A(17,6,6)
sono un milione di operazioni per mossa, cioè circa 2500 mosse in venti secondi. Con
così poche mosse la ricerca non riesce nemmeno ad **aggiungere una parola** a un
codice valido di 85: il salto da 85 a 86 richiede di scambiarne diverse, e 2500
mosse non bastano.

Qui il lavoro si fa una volta sola. Si precalcola la matrice dei **conflitti** — bit
`j` della riga `i` acceso se le parole `i` e `j` distano meno di `d` — e si tiene un
contatore `conta[v]` = quante parole scelte sono in conflitto con `v`. Aggiungere o
togliere una parola costa una somma di N interi, cioè millesimi di quello che
costava prima. Si passa da migliaia di mosse a milioni.

La matrice occupa N²/8 byte: 19 MB per N = 12.376, 700 MB per N = 74.613. Sopra il
tetto si torna al motore lento, che è più povero ma non esplode in memoria.

IL CRITERIO È SEMPRE LO STESSO
------------------------------
`conta` conta le violazioni, e un codice è valido quando la somma dei conflitti
delle parole scelte è zero. Il verdetto finale resta di `codici.verifica`.
"""
from __future__ import annotations

import numpy as np

from codici import verifica_veloce
from tabu import _tutte_le_parole

TETTO_MEMORIA_BYTE = 700_000_000


def matrice_conflitti(tutte: np.ndarray, d: int) -> np.ndarray:
    """Bit `j` della riga `i` acceso se `dist(i, j) < d` e `i != j`."""
    N = len(tutte)
    byte = (N + 7) // 8
    if N * byte > TETTO_MEMORIA_BYTE:
        raise MemoryError(f"la matrice richiederebbe {N * byte / 1e6:.0f} MB")
    M = np.zeros((N, byte), dtype=np.uint8)
    blocco = max(1, 8_000_000 // max(N, 1))
    for i in range(0, N, blocco):
        fetta = tutte[i:i + blocco]
        vicino = np.bitwise_count(np.bitwise_xor(fetta[:, None], tutte[None, :])) < d
        for k in range(len(fetta)):
            vicino[k, i + k] = False          # niente conflitto con se stessa
        M[i:i + blocco] = np.packbits(vicino, axis=1)
    return M


class Stato:
    """Un insieme di parole scelte, con il conteggio dei conflitti aggiornato."""

    def __init__(self, M: np.ndarray, N: int) -> None:
        self.M = M
        self.N = N
        self.conta = np.zeros(N, dtype=np.int32)
        self.dentro = np.zeros(N, dtype=bool)
        self.righe: dict[int, np.ndarray] = {}

    def riga(self, i: int) -> np.ndarray:
        r = self.righe.get(i)
        if r is None:
            r = np.unpackbits(self.M[i], count=self.N).astype(np.int32)
            if len(self.righe) > 4096:
                self.righe.clear()
            self.righe[i] = r
        return r

    def aggiungi(self, i: int) -> None:
        self.conta += self.riga(i)
        self.dentro[i] = True

    def togli(self, i: int) -> None:
        self.conta -= self.riga(i)
        self.dentro[i] = False

    @property
    def scelte(self) -> np.ndarray:
        return np.flatnonzero(self.dentro)

    @property
    def violazioni(self) -> int:
        return int(self.conta[self.dentro].sum()) // 2


def cerca_dimensione(n: int, d: int, w: int, m: int, *, mosse: int = 200_000,
                     seme: int = 0, tutte: np.ndarray | None = None,
                     M: np.ndarray | None = None,
                     inizio: list[int] | None = None,
                     passeggiata: float = 0.3) -> tuple[list[int], int]:
    """Cerca un codice di `m` parole. Restituisce (parole, violazioni minime viste)."""
    tutte = _tutte_le_parole(n, w) if tutte is None else tutte
    N = len(tutte)
    if m > N:
        return [], m * m
    M = matrice_conflitti(tutte, d) if M is None else M
    rng = np.random.default_rng(seme)
    s = Stato(M, N)

    partenza = (list(inizio) if inizio is not None
                else [int(x) for x in rng.choice(N, size=m, replace=False)])
    for i in partenza[:m]:
        s.aggiungi(int(i))
    while int(s.dentro.sum()) < m:            # completa scegliendo il meno in conflitto
        costo = np.where(s.dentro, 1 << 30, s.conta)
        s.aggiungi(int(rng.choice(np.flatnonzero(costo == costo.min()))))

    migliore = s.violazioni
    migliori = s.scelte.copy()
    tabu = np.zeros(N, dtype=np.int64)
    for passo in range(mosse):
        if s.violazioni == 0:
            break
        scelte = s.scelte
        conf = s.conta[scelte]
        if conf.max() == 0:
            break
        if rng.random() < passeggiata:
            colpevoli = scelte[conf > 0]
            esce = int(rng.choice(colpevoli))
        else:
            esce = int(rng.choice(scelte[conf == conf.max()]))
        s.togli(esce)
        tabu[esce] = passo + 4 + int(rng.integers(0, max(2, m // 3)))
        costo = np.where(s.dentro, 1 << 30, s.conta).astype(np.int64)
        costo += np.where(tabu > passo, 1 << 10, 0)
        entra = int(rng.choice(np.flatnonzero(costo == costo.min())))
        s.aggiungi(entra)
        if s.violazioni < migliore:
            migliore = s.violazioni
            migliori = s.scelte.copy()
    return [int(tutte[i]) for i in migliori], migliore


def sali(n: int, d: int, w: int, da: list[int], fino_a: int, *,
         mosse_per_gradino: int = 100_000, seme: int = 0,
         tentativi: int = 4) -> dict:
    """Da un codice valido, una parola alla volta fino a `fino_a` (o finché riesce)."""
    tutte = _tutte_le_parole(n, w)
    M = matrice_conflitti(tutte, d)
    posizione = {int(p): k for k, p in enumerate(tutte)}
    parole = sorted(da)
    rng = np.random.default_rng(seme)
    gradini: dict[int, str] = {}
    while len(parole) < fino_a:
        traguardo = len(parole) + 1
        base = [posizione[p] for p in parole]
        vinto = None
        for t in range(tentativi):
            libere = np.flatnonzero(~np.isin(np.arange(len(tutte)), base))
            nuove, viol = cerca_dimensione(
                n, d, w, traguardo, mosse=mosse_per_gradino,
                seme=seme * 1000 + traguardo * 7 + t, tutte=tutte, M=M,
                inizio=base + [int(rng.choice(libere))])
            if viol == 0:
                vinto = nuove
                break
        gradini[traguardo] = "riuscito" if vinto else "fallito"
        if vinto is None:
            break
        parole = sorted(vinto)
    v = verifica_veloce(parole, n, d, w)
    return {"dimensione": len(parole), "valido": v.ok, "gradini": gradini,
            "parole": parole if v.ok else [], "obiettivo": fino_a}
