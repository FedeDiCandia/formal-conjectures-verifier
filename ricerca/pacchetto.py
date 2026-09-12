"""
D(27,5,2): esiste un pacchetto di 32 blocchi? Attacco esatto, con simmetria rotta.

IL PROBLEMA, E PERCHÉ HA UN NOME
--------------------------------
A(27,8,5) della tabella di Brouwer, con t = w − d/2 = 1, è esattamente il **numero di
pacchetto** D(27,5,2): il massimo numero di sottoinsiemi di 5 elementi di un insieme
di 27, a due a due intersecantisi in al massimo un punto (cioè ogni coppia di punti
in al massimo un blocco).

  * limite di Johnson/Schönheim: ⌊27/5 · ⌊26/4⌋⌋ = ⌊27·6/5⌋ = **32**
  * tabella di Brouwer: **31 ≤ D ≤ 32**
  * letteratura dei disegni: per v ≡ 7, 11, 15 (mod 20) si ha P(5,v) = J(5,v), «con
    possibili eccezioni v ∈ {27, 47, 51, 67, 87, 135, 187, 231, 251, 291}» — e
    27 ≡ 7 (mod 20). **v = 27 è elencato per nome come caso non deciso.**

Quindi la domanda «32 o 31?» è una domanda aperta con un nome, e **una risposta
qualunque delle due la chiude.**

LA ROTTURA DI SIMMETRIA, CHE È RIGOROSA E NON UN'APPROSSIMAZIONE
----------------------------------------------------------------
L'ILP diretto ha 80.730 variabili e il gruppo simmetrico S₂₇ agisce su tutte: il
solutore si perde a esplorare copie della stessa soluzione. Si può eliminare quasi
tutta questa simmetria **senza perdere generalità**, con un conto di due righe.

Sia dato un pacchetto di 32 blocchi. I blocchi che passano per un punto x sono a due
a due disgiunti fuori da x, quindi

    deg(x) ≤ ⌊26/4⌋ = 6   per ogni x.

Contando le incidenze, Σ_x deg(x) = 32·5 = **160**, mentre 27 punti di grado 6
darebbero 162. La deficienza totale è 2, quindi **almeno 25 dei 27 punti hanno grado
esattamente 6.**

Allora, a meno di rinominare i punti, possiamo assumere:

  * il punto **0** ha grado 6;
  * i suoi sei blocchi sono `{0,1,2,3,4}`, `{0,5,6,7,8}`, `{0,9,10,11,12}`,
    `{0,13,14,15,16}`, `{0,17,18,19,20}`, `{0,21,22,23,24}` — perché sono disgiunti
    fuori da 0 e coprono 24 dei 26 punti restanti, e la configurazione è unica a
    meno di rinomina;
  * i due punti **25** e **26** non stanno in nessun blocco per 0.

Tutte le coppie interne a quei sei blocchi sono ormai usate. Quindi ogni altro
blocco contiene **al massimo un punto per ciascuno dei sei gruppi** {1,2,3,4},
{5,6,7,8}, …, {21,22,23,24}, e può usare liberamente 25 e 26. I candidati scendono
da 80.730 a **15.104**, e la simmetria residua è solo quella che permuta i gruppi e
i punti dentro un gruppo.

Restano da trovare **26** blocchi. Due esiti, entrambi decisivi:

  * si trovano  → D(27,5,2) = 32, e v = 27 esce dalla lista delle eccezioni;
  * infattibile → nessun pacchetto di 32 ha un punto di grado 6; ma almeno 25 punti
    ce l'hanno, quindi nessun pacchetto di 32 esiste, e **D(27,5,2) = 31**.

In entrambi i casi la cella è chiusa. Un'euristica non può dare il secondo esito.
"""
from __future__ import annotations

from itertools import combinations

import highspy
import numpy as np

GRUPPI = [tuple(range(1 + 4 * i, 5 + 4 * i)) for i in range(6)]   # sei 4-insiemi
LIBERI = (25, 26)
FISSI = [(0,) + g for g in GRUPPI]


def candidati() -> list[tuple[int, ...]]:
    """I blocchi ammissibili dopo la rottura di simmetria: non contengono 0, e
    prendono al massimo un punto per gruppo."""
    fuori = []
    for quanti_liberi in range(3):
        for liberi in combinations(LIBERI, quanti_liberi):
            for quali in combinations(range(6), 5 - quanti_liberi):
                for scelta in _prodotto([GRUPPI[i] for i in quali]):
                    fuori.append(tuple(sorted(liberi + scelta)))
    return fuori


def _prodotto(gruppi):
    if not gruppi:
        yield ()
        return
    for x in gruppi[0]:
        for resto in _prodotto(gruppi[1:]):
            yield (x,) + resto


def coppie_usate() -> set[tuple[int, int]]:
    usate = set()
    for B in FISSI:
        usate |= set(combinations(sorted(B), 2))
    return usate


def risolvi(*, blocchi_da_trovare: int = 26, secondi: float = 3600.0,
            silenzio: bool = False) -> dict:
    cand = candidati()
    usate = coppie_usate()
    # nessun candidato puo' contenere una coppia gia' usata: per costruzione
    for B in cand:
        assert not (set(combinations(B, 2)) & usate), B

    coppia_idx: dict[tuple[int, int], int] = {}
    righe: list[list[int]] = []
    for j, B in enumerate(cand):
        for c in combinations(B, 2):
            i = coppia_idx.get(c)
            if i is None:
                i = len(righe)
                coppia_idx[c] = i
                righe.append([])
            righe[i].append(j)

    h = highspy.Highs()
    if silenzio:
        h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", float(secondi))
    h.setOptionValue("mip_rel_gap", 0.0)
    inf = highspy.kHighsInf
    for _ in cand:
        h.addVar(0.0, 1.0)
    idx = np.arange(len(cand), dtype=np.int32)
    h.changeColsIntegrality(
        len(cand), idx, np.array([highspy.HighsVarType.kInteger] * len(cand)))
    h.changeColsCost(len(cand), idx, np.full(len(cand), -1.0))
    for colonne in righe:
        a = np.array(colonne, dtype=np.int32)
        h.addRow(-inf, 1.0, len(a), a, np.ones(len(a)))
    # grado: ogni punto sta in al massimo 6 blocchi. Per i punti 1..24 uno dei sei
    # blocchi fissi lo usa gia', quindi ne restano 5; per 25 e 26 restano 6.
    for x in range(1, 27):
        colonne = np.array([j for j, B in enumerate(cand) if x in B], dtype=np.int32)
        if len(colonne):
            h.addRow(-inf, 6.0 - (1.0 if x <= 24 else 0.0),
                     len(colonne), colonne, np.ones(len(colonne)))
    # chiediamo esattamente quanti ne mancano: "esiste?" e' molto piu' facile di
    # "qual e' il massimo?"
    h.addRow(float(blocchi_da_trovare), inf, len(idx), idx, np.ones(len(idx)))
    h.run()
    stato = h.modelStatusToString(h.getModelStatus())
    z = np.array(h.getSolution().col_value)
    scelti = [cand[j] for j in range(len(cand)) if z[j] > 0.5]
    return {"candidati": len(cand), "vincoli_coppia": len(righe),
            "stato": stato, "trovati": len(scelti),
            "blocchi": FISSI + scelti if scelti else [],
            "totale": len(FISSI) + len(scelti)}


def verifica_pacchetto(blocchi, n: int = 27, k: int = 5) -> tuple[bool, list[str]]:
    """Controllo indipendente, con aritmetica intera: ogni coppia al massimo una volta."""
    difetti = []
    viste: dict[tuple[int, int], int] = {}
    for i, B in enumerate(blocchi):
        if len(set(B)) != k:
            difetti.append(f"blocco {i} non ha {k} punti distinti: {B}")
            continue
        if not all(0 <= x < n for x in B):
            difetti.append(f"blocco {i} ha punti fuori da 0..{n - 1}: {B}")
            continue
        for c in combinations(sorted(B), 2):
            if c in viste:
                difetti.append(f"la coppia {c} sta nei blocchi {viste[c]} e {i}")
            else:
                viste[c] = i
    return (not difetti), difetti[:10]
