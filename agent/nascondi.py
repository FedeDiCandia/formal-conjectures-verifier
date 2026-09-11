"""
Nasconde le dimostrazioni gia' presenti nell'archivio.

Per collaudare onestamente un agente su un problema gia' risolto bisogna
togliergli la risposta. Questo modulo prende il file sorgente di un problema e
sostituisce OGNI dimostrazione con `sorry`, ottenendo esattamente l'aspetto che
il file avrebbe se il problema fosse ancora aperto.

Si sostituiscono tutte le dimostrazioni del file, non solo quella del teorema
bersaglio: i lemmi vicini sono spesso i passaggi intermedi della soluzione e
lasciarli sarebbe come lasciare mezzo compito svolto.
"""
from __future__ import annotations

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
            return i
        i += 1
    return None


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
    """Verifica che la dimostrazione originale non sia rimasta nel testo.

    Un collaudo in cui la risposta trapela non misura niente.
    """
    originale = problema.source_text()
    pos = _posizione_separatore(originale)
    if pos is None:
        return
    prova = originale[pos + 2:].strip()
    # normalizza gli spazi per confrontare in modo robusto
    def compatta(s: str) -> str:
        return " ".join(s.split())
    prova_compatta = compatta(prova)
    if len(prova_compatta) > 30 and prova_compatta in compatta(testo_nascosto):
        raise AssertionError(
            f"La dimostrazione di {problema.theorem} e' ancora presente nel testo "
            f"consegnato all'agente: il collaudo non sarebbe valido.")
