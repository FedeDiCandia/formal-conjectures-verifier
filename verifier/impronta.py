"""
Impronta dei file compilati dell'archivio.

PERCHE'
-------
Il README di comparator elenca fra i suoi assunti (il numero 2):

    "You have not previously tried to compile the Solution file or any other
    potentially adversarial files (as that might compromise your Challenge
    file to make it seem like you are looking for a different proof than you
    actually are)"

Detto in italiano: se compilando il file del candidato qualcosa riscrivesse i
file compilati dell'archivio, il "Challenge" che comparator esporta non sarebbe
piu' l'enunciato originale, e la verifica confronterebbe la soluzione con un
problema alterato. Passerebbe tutto, e non vorrebbe dire niente.

Noi facciamo verifiche a ripetizione nella stessa cartella, quindi quell'assunto
non lo possiamo dare per buono: dobbiamo controllarlo. Questo modulo prende
un'impronta dell'archivio prima e dopo ogni verifica.

COME
----
Due livelli, scelti misurando i costi reali:

  * i file dell'archivio (i suoi 786 .olean e i 795 sorgenti, 126 MB in tutto)
    vengono hashati per CONTENUTO, uno per uno. Costa 0,65 secondi e permette
    di dire *quale* file e' cambiato;
  * Mathlib e le altre dipendenze (7877 .olean, 6,8 GB) sarebbero troppo lente
    da hashare per intero, quindi se ne prendono i METADATI (percorso,
    dimensione, data di modifica al nanosecondo). Costa 0,86 secondi e
    intercetta qualunque riscrittura.

In tutto circa un secondo e mezzo, su una verifica che ne dura venticinque.
"""
from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

#: Quanti thread usare per l'hashing. `hashlib` rilascia il GIL mentre lavora,
#: quindi qui i thread aiutano davvero: da 3,2 a meno di un secondo.
N_THREAD = min(8, (os.cpu_count() or 4))


@dataclass
class Impronta:
    #: percorso relativo -> sha256 del contenuto (file dell'archivio)
    contenuto: dict[str, str] = field(default_factory=dict)
    #: un solo digest per i metadati delle dipendenze (Mathlib ecc.)
    metadati_dipendenze: str = ""
    n_file_contenuto: int = 0
    n_file_metadati: int = 0


def _cartelle_archivio(archivio: Path) -> list[Path]:
    """I file che definiscono l'enunciato: i compilati dell'archivio e i sorgenti."""
    return [
        archivio / ".lake" / "build" / "lib" / "lean",
        archivio / "FormalConjectures",
        archivio / "FormalConjecturesForMathlib",
    ]


def _cartelle_dipendenze(archivio: Path) -> list[Path]:
    return [archivio / ".lake" / "packages"]


def _sha256(percorso: Path) -> str:
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        while blocco := f.read(1 << 20):
            h.update(blocco)
    return h.hexdigest()


def calcola(archivio: Path, escludi: str = "_Judge") -> Impronta:
    """Prende l'impronta. `escludi` e' il nome della cartella del modulo
    temporaneo, che per definizione cambia a ogni verifica."""
    imp = Impronta()

    da_hashare: list[Path] = []
    for radice in _cartelle_archivio(archivio):
        if not radice.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(radice):
            dirnames[:] = [d for d in dirnames if d != escludi]
            da_hashare.extend(Path(dirpath) / nome for nome in filenames)

    def uno(p: Path) -> tuple[str, str] | None:
        try:
            return str(p.relative_to(archivio)), _sha256(p)
        except OSError:
            return None

    with ThreadPoolExecutor(max_workers=N_THREAD) as pool:
        for esito in pool.map(uno, da_hashare):
            if esito is not None:
                imp.contenuto[esito[0]] = esito[1]
    imp.n_file_contenuto = len(imp.contenuto)

    voci: list[str] = []
    taglio = len(str(archivio)) + 1
    for radice in _cartelle_dipendenze(archivio):
        if radice.is_dir():
            _metadati_ricorsivo(str(radice), taglio, escludi, voci)
    voci.sort()
    h = hashlib.sha256()
    for v in voci:
        h.update(v.encode())
    imp.metadati_dipendenze = h.hexdigest()
    imp.n_file_metadati = len(voci)
    return imp


#: Cartelle irrilevanti per l'enunciato: `.git` di Mathlib da sola contiene
#: decine di migliaia di file e non viene mai letta da Lean.
_CARTELLE_IGNORATE = {".git", ".github"}


def _metadati_ricorsivo(cartella: str, taglio: int, escludi: str, voci: list[str]) -> None:
    """Raccoglie percorso, dimensione e data di modifica.

    Usa `os.scandir` e stringhe invece di `os.walk` con oggetti `Path`: su
    111 000 file la differenza misurata e' fra 0,3 e 3 secondi, e questa
    funzione gira due volte per ogni verifica.
    """
    try:
        iteratore = os.scandir(cartella)
    except OSError:
        return
    with iteratore:
        for voce in iteratore:
            try:
                if voce.is_dir(follow_symlinks=False):
                    if voce.name != escludi and voce.name not in _CARTELLE_IGNORATE:
                        _metadati_ricorsivo(voce.path, taglio, escludi, voci)
                else:
                    st = voce.stat(follow_symlinks=False)
                    voci.append(f"{voce.path[taglio:]}|{st.st_size}|{st.st_mtime_ns}")
            except OSError:
                continue


def confronta(prima: Impronta, dopo: Impronta, max_elenco: int = 12) -> list[str]:
    """Elenco in italiano delle differenze. Vuoto se l'archivio e' intatto."""
    differenze: list[str] = []

    modificati = [p for p, d in dopo.contenuto.items()
                  if p in prima.contenuto and prima.contenuto[p] != d]
    spariti = [p for p in prima.contenuto if p not in dopo.contenuto]
    comparsi = [p for p in dopo.contenuto if p not in prima.contenuto]

    def elenca(etichetta: str, quali: list[str]) -> None:
        if not quali:
            return
        mostrati = ", ".join(sorted(quali)[:max_elenco])
        resto = f" (e altri {len(quali) - max_elenco})" if len(quali) > max_elenco else ""
        differenze.append(f"{etichetta}: {mostrati}{resto}")

    elenca(f"{len(modificati)} file dell'archivio MODIFICATI", modificati)
    elenca(f"{len(spariti)} file dell'archivio CANCELLATI", spariti)
    elenca(f"{len(comparsi)} file NUOVI dentro l'archivio", comparsi)

    if prima.metadati_dipendenze != dopo.metadati_dipendenze:
        differenze.append(
            f"i file di Mathlib e delle altre dipendenze sono cambiati "
            f"(prima {prima.n_file_metadati} file, dopo {dopo.n_file_metadati})")
    return differenze
