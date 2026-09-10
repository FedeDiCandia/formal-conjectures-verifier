"""
Sfide "negate" per i problemi con `answer(sorry)` proposizionale.

IL PROBLEMA
-----------
Come spiegato in docs/01, l'opzione predefinita dell'archivio
(`google.answer = always_true`) trasforma `answer(sorry)` in `True` quando il
tipo atteso e' una proposizione. Quindi una domanda aperta formalizzata cosi':

    /-- Vale P? -/
    theorem congettura : answer(sorry) ↔ P := by sorry

viene elaborata come `True ↔ P`, cioe' come l'affermazione che **la risposta e'
SI'**. Sono 107 problemi ancora aperti dell'archivio.

Conseguenza: se per uno di quei problemi la risposta giusta fosse NO, il
teorema com'e' scritto sarebbe FALSO, e nessuno potrebbe dimostrarlo. Chi
scoprisse la confutazione non avrebbe modo di farla verificare: dovrebbe
cambiare l'enunciato in `answer(False) ↔ P`, e il verificatore lo rifiuterebbe —
giustamente, perche' e' un altro enunciato.

LA SOLUZIONE
------------
Per ognuno di quei problemi si puo' generare la sfida **negata**: lo stesso file
dell'archivio con `answer(sorry)` sostituito da `answer(False)`, cosi' che
l'enunciato diventi `False ↔ P`, che e' logicamente `¬P`.

Il punto essenziale e' CHI genera quel file. Lo generiamo noi, meccanicamente,
dal sorgente dell'archivio: e' un file **fidato**, esattamente come lo e' il
modulo originale. Non lo scrive chi propone la dimostrazione. Se lo scrivesse
lui, potrebbe metterci dentro qualunque cosa.

Cosi' un problema aperto ha due sfide, entrambe fidate ed entrambe verificabili:

    stretta      True  ↔ P     "la risposta e' si'"   (l'enunciato dell'archivio)
    confutazione False ↔ P     "la risposta e' no"

e sono enunciati diversi: una dimostrazione di una delle due viene rifiutata
dall'altra. Il test lo verifica.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from index import Problem   # noqa: E402


#: `answer(sorry)` con spazi qualunque fra i pezzi.
_SEGNAPOSTO = re.compile(r"answer\s*\(\s*sorry\s*\)")


class NonNegabile(ValueError):
    """Il problema non ammette una sfida negata."""


@dataclass
class SfidaNegata:
    problema: str
    #: il testo del file Lean da compilare come Challenge
    testo: str
    #: quante sostituzioni sono state fatte
    sostituzioni: int


def puo_essere_negato(problema: Problem) -> tuple[bool, str]:
    """Dice se ha senso generare la sfida negata, e perche' no in caso contrario."""
    if not problema.answer_placeholder_in_source:
        return False, ("l'enunciato non contiene `answer(sorry)`: non c'e' nessuna "
                       "domanda di cui invertire la risposta. Un enunciato senza "
                       "`answer( )` afferma direttamente una proposizione, e la sua "
                       "negazione non e' un problema dell'archivio")
    if problema.statement_has_sorry:
        return False, ("il buco `answer( )` non e' proposizionale: la risposta e' un "
                       "oggetto (un numero, un insieme), non un si'/no. Non c'e' un "
                       "verso da invertire, c'e' un valore da fornire")
    return True, ""


def genera(problema: Problem) -> SfidaNegata:
    """Costruisce il testo della sfida negata dal sorgente dell'archivio."""
    ok, perche = puo_essere_negato(problema)
    if not ok:
        raise NonNegabile(f"{problema.theorem}: {perche}")

    testo = problema.source_file.read_text(encoding="utf-8")
    r = problema.range
    if not r:
        raise NonNegabile(f"{problema.theorem}: posizione nel sorgente sconosciuta")

    righe = testo.split("\n")
    inizio, fine = r["startLine"] - 1, r["endLine"] - 1

    # La sostituzione va fatta SOLO dentro la dichiarazione del teorema
    # bersaglio: nello stesso file possono esserci altri problemi con il loro
    # `answer(sorry)`, e invertirli tutti darebbe una sfida diversa da quella
    # che si vuole.
    blocco = "\n".join(righe[inizio:fine + 1])
    nuovo, n = _SEGNAPOSTO.subn("answer(False)", blocco)
    if n == 0:
        raise NonNegabile(
            f"{problema.theorem}: `answer(sorry)` non trovato nella dichiarazione. "
            f"L'indice dice che c'e', quindi l'indice e' vecchio: rigeneralo con "
            f"`python verifier/index.py --build`")
    righe[inizio:fine + 1] = nuovo.split("\n")

    intestazione = (
        "/-\n"
        "  SFIDA NEGATA — file generato automaticamente, NON scritto a mano.\n"
        "\n"
        f"  Problema:  {problema.theorem}\n"
        f"  Originale: {problema.module}\n"
        "\n"
        "  E' il file dell'archivio con `answer(sorry)` sostituito da\n"
        "  `answer(False)` nella sola dichiarazione del teorema bersaglio.\n"
        "  L'enunciato passa quindi da `True ↔ P` (la risposta e' si') a\n"
        "  `False ↔ P` (la risposta e' no, cioe' ¬P).\n"
        "\n"
        "  Generato da verifier/negazione.py a partire dal sorgente\n"
        "  dell'archivio: e' un file FIDATO, non fornito da chi propone la\n"
        "  dimostrazione.\n"
        "-/\n")
    return SfidaNegata(problema=problema.theorem,
                       testo=intestazione + "\n".join(righe),
                       sostituzioni=n)
