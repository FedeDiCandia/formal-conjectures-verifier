"""
Nasconde le dimostrazioni gia' presenti nell'archivio.

Per collaudare onestamente un agent su un problema gia' risolto bisogna
togliergli la risposta. Questo modulo prende il file sorgente di un problema e
sostituisce OGNI dimostrazione con `sorry`, ottenendo esattamente l'aspetto che
il file avrebbe se il problema fosse ancora aperto.

Si sostituiscono tutte le dimostrazioni del file, non solo quella del teorema
bersaglio: i lemmi vicini sono spesso i passaggi intermedi della soluzione e
lasciarli sarebbe come lasciare mezzo compito svolto.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
from index import ProblemIndex, Problem   # noqa: E402


#: Coppie di delimitatori: dentro di esse un `:=` non separa la dimostrazione.
_APERTURE = "([{⟨"
_CHIUSURE = ")]}⟩"


def _posizione_separatore(testo: str) -> int | None:
    """Indice del `:=` che separa l'enunciato dalla dimostrazione.

    Va cercato al livello esterno: in `theorem f (n : ℕ := 3) : P := prova` il
    primo `:=` sta dentro le parentesi e non c'entra.

    E vanno saltati i COMMENTI. Le posizioni che Lean riporta per una
    dichiarazione partono dal docstring, non dalla parola `theorem`, e un
    docstring puo' contenere codice di esempio con dentro un `:=`. Senza questo
    accorgimento il taglio finirebbe dentro la documentazione.
    """
    profondita = 0
    i, n = 0, len(testo)
    while i < n - 1:
        c = testo[i]
        # commento di riga
        if c == "-" and testo[i + 1] == "-":
            while i < n and testo[i] != "\n":
                i += 1
            continue
        # commento a blocco, annidabile; comprende i docstring /-- ... -/
        if c == "/" and testo[i + 1] == "-":
            livello = 0
            while i < n - 1:
                if testo[i] == "/" and testo[i + 1] == "-":
                    livello += 1; i += 2; continue
                if testo[i] == "-" and testo[i + 1] == "/":
                    livello -= 1; i += 2
                    if livello == 0:
                        break
                    continue
                i += 1
            continue
        # stringa
        if c == '"':
            i += 1
            while i < n:
                if testo[i] == "\\":
                    i += 2; continue
                if testo[i] == '"':
                    i += 1; break
                i += 1
            continue
        if c in _APERTURE:
            profondita += 1
        elif c in _CHIUSURE:
            profondita -= 1
        elif c == ":" and testo[i + 1] == "=" and profondita == 0:
            if not _e_legatura(testo, i):
                return i
        i += 1
    return None


#: Parole che introducono una LEGATURA, non la dimostrazione. Un `:=` che le
#: segue appartiene a loro.
_LEGATURE = ("let", "have", "set", "obtain", "suffices", "calc", "fun", "where",
             "if", "then", "else", "with", "do", "match")


def _e_legatura(testo: str, pos: int) -> bool:
    """Dice se il `:=` a `pos` appartiene a un `let`, un `have` e simili.

    Serve perche' un enunciato puo' contenere un `let A : Set α := ...` al
    livello esterno delle parentesi, e prenderlo per l'inizio della
    dimostrazione TRONCA l'enunciato. E' successo davvero, su
    WrittenOnTheWallII.GraphConjecture65.conjecture65, e il controllo di
    onesta' l'ha intercettato.
    """
    inizio_riga = testo.rfind("\n", 0, pos) + 1
    segmento = testo[inizio_riga:pos]
    parole = segmento.replace("(", " ").replace(")", " ").split()
    if not parole:
        # il `:=` sta a inizio riga: si guarda la riga precedente
        prec = testo.rfind("\n", 0, max(0, inizio_riga - 1)) + 1
        parole = testo[prec:inizio_riga].replace("(", " ").replace(")", " ").split()
    # Si guarda a ritroso la prima parola significativa. Un punto e virgola
    # CHIUDE la legatura (`let a := 1; resto`), quindi la scansione si ferma li':
    # senza, il `:=` finale di `theorem t : (let a := 1; a = 1) := by rfl`
    # veniva scambiato per quello del `let`.
    for parola in reversed(parole):
        if ";" in parola:
            return False
        if parola in _LEGATURE:
            return True
        if parola in ("theorem", "lemma", "def", "abbrev", "instance", "example"):
            return False
    return False


def sostituisci_dimostrazione(dichiarazione: str) -> str:
    """`theorem f : P := <prova>`  ->  `theorem f : P := by\\n  sorry`"""
    pos = _posizione_separatore(dichiarazione)
    if pos is None:
        return dichiarazione
    return dichiarazione[:pos].rstrip() + " := by\n  sorry"


def file_senza_dimostrazioni(problema: Problem, indice: ProblemIndex) -> str:
    """Il file del problema con tutte le dimostrazioni sostituite da `sorry`."""
    testo = problema.source_file.read_text(encoding="utf-8")
    righe = testo.split("\n")

    # Tutti i teoremi che stanno in questo file, dal fondo verso l'alto, cosi'
    # le sostituzioni non spostano le posizioni di quelli ancora da trattare.
    nel_file = [p for p in indice.problems if p.module == problema.module and p.range]
    nel_file.sort(key=lambda p: (p.range["startLine"], p.range["startCol"]), reverse=True)

    for p in nel_file:
        r = p.range
        inizio_riga, fine_riga = r["startLine"] - 1, r["endLine"] - 1
        blocco = righe[inizio_riga:fine_riga + 1]
        if not blocco:
            continue
        # ritaglia esattamente la dichiarazione
        coda = blocco[-1][r["endCol"]:]
        blocco[-1] = blocco[-1][:r["endCol"]]
        testa = blocco[0][:r["startCol"]]
        blocco[0] = blocco[0][r["startCol"]:]
        nuovo = sostituisci_dimostrazione("\n".join(blocco))
        nuove_righe = (testa + nuovo + coda).split("\n")
        righe[inizio_riga:fine_riga + 1] = nuove_righe

    return "\n".join(righe)


def controlla_che_sia_nascosta(problema: Problem, testo_nascosto: str) -> None:
    """Verifica che la dimostrazione del teorema BERSAGLIO sia stata sostituita.

    Un collaudo in cui la risposta trapela non misura niente, quindi questo
    controllo deve esserci. Ma va fatto sulla DICHIARAZIONE GIUSTA: la prima
    versione cercava il testo della dimostrazione in tutto il file, e dava
    falso allarme quando un altro teorema dello stesso file aveva la stessa
    dimostrazione di una riga. E' successo con
    DiophantineTuple.fermat_4_tuple, dove tre teoremi condividono
    `by norm_num [IsDiophantineTuple]`: il collaudo si e' interrotto pur
    essendo tutto in ordine.
    """
    corto = problema.theorem.split(".")[-1]
    # la dichiarazione del bersaglio dentro il testo nascosto
    m = re.search(rf"(?:theorem|lemma)\s+[\w'.«»]*{re.escape(corto)}(?![\w']) ?[\s\S]*?"
                  rf"(?=\n(?:@\[|/--|theorem |lemma |def |abbrev |instance |end |namespace |"
                  rf"variable |open |section )|\Z)",
                  testo_nascosto)
    if m is None:
        raise AssertionError(
            f"Nel testo consegnato all'agent non trovo la dichiarazione di "
            f"{problema.theorem}: il problema non sarebbe proponibile.")
    dichiarazione = m.group(0)
    pos = _posizione_separatore(dichiarazione)
    if pos is None:
        raise AssertionError(
            f"Non riesco a individuare la dimostrazione di {problema.theorem} "
            f"nel testo nascosto.")
    # Si togliono i commenti: la dichiarazione estratta puo' portarsi dietro
    # una riga di commento che segue (per esempio "-- Sanity checks"), e
    # confrontarla come se fosse dimostrazione dava un falso allarme.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
    from guard import strip_comments_and_strings
    prova = " ".join(strip_comments_and_strings(dichiarazione[pos + 2:]).split())
    if prova not in ("by sorry", "sorry"):
        raise AssertionError(
            f"La dimostrazione di {problema.theorem} NON e' stata nascosta: al "
            f"suo posto c'e' ancora {prova[:120]!r}. Il collaudo non sarebbe valido.")
