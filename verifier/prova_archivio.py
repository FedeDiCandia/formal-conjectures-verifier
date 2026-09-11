"""
Estrae la dimostrazione che l'archivio fornisce, come file candidato autonomo.

A COSA SERVE
------------
Per calibrare un agente servono problemi di cui si conosca la risposta. Ma
"l'archivio lo ha risolto" non basta: la sua dimostrazione potrebbe usare
`decide +native` (95 casi) o dipendere da un lemma con un buco (17 casi), e il
nostro verificatore la rifiuterebbe. Chiedere a un agente di risolvere uno di
quei problemi significa chiedergli di fare MEGLIO dell'archivio, e un
fallimento non direbbe niente sull'agente.

Il controllo sugli assiomi (campo `archiveProofAxioms` dell'indice) e' una
condizione necessaria ma non sufficiente: non dice se la dimostrazione, estratta
dal suo file e compilata da sola, arriva davvero in fondo al verificatore. Per
saperlo bisogna provarci.

Questo modulo costruisce il file candidato che l'archivio stesso consegnerebbe:
gli import, le definizioni locali, i lemmi ausiliari DIMOSTRATI e il teorema
bersaglio con la sua dimostrazione vera. Vengono tolte solo le dichiarazioni
che contengono `sorry`, perche' il verificatore rifiuta un file che ne
contenga.

Togliere TUTTI gli altri teoremi era la scelta sbagliata: alla prima prova 9
dimostrazioni su 23 sono fallite con "Unknown identifier", perche' usavano un
lemma vicino nello stesso file. Il fallimento era dell'estrattore, non
dell'archivio.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from index import Problem, ProblemIndex   # noqa: E402


class NonEstraibile(ValueError):
    """Non si puo' costruire un candidato autonomo per questo problema."""


@dataclass
class ProvaArchivio:
    problema: str
    testo: str
    teoremi_rimossi: int


#: Parole chiave che aprono una DICHIARAZIONE.
_DICHIARAZIONI = ("theorem", "lemma", "def", "abbrev", "instance", "structure",
                  "inductive", "class", "example", "opaque", "axiom")

#: Modificatori che possono precedere una parola chiave.
_MODIFICATORI = ("private", "protected", "noncomputable", "partial", "unsafe",
                 "scoped", "local", "nonrec", "public", "meta", "mutual")

#: Comandi di struttura: aprono un blocco ma non dichiarano nulla.
_STRUTTURALI = ("namespace", "end", "section", "import", "open", "variable",
                "universe", "set_option", "attribute", "notation", "deriving",
                "macro", "syntax", "elab", "run_cmd", "#", "/-!")
# NB: `/-` NON e' qui. Ci era finito, e siccome `/--` comincia con `/-` i
# docstring tornavano a essere inizi di blocco: rimuovendo un teorema il suo
# docstring restava penzolante, con l'errore
# "unexpected token '/--'; expected 'lemma'". Un docstring appartiene sempre
# alla dichiarazione che lo segue, mai a se' stesso.


def _apre_dichiarazione(riga: str) -> bool:
    if not riga or riga[0].isspace():
        return False
    parole = riga.split()
    i = 0
    while i < len(parole) and parole[i] in _MODIFICATORI:
        i += 1
    return i < len(parole) and parole[i].split(":")[0] in _DICHIARAZIONI


def _apre_struttura(riga: str) -> bool:
    if not riga or riga[0].isspace():
        return False
    prima = riga.split()[0] if riga.split() else ""
    return prima.startswith(_STRUTTURALI) or riga.startswith("#")


def _blocchi(righe: list[str]) -> list[tuple[int, int]]:
    """Spezza il file in blocchi di primo livello: (riga iniziale, riga finale).

    Il punto delicato: un docstring `/-- ... -/` e un attributo `@[...]`
    APPARTENGONO alla dichiarazione che li segue. Trattarli come blocchi a se'
    e' esattamente l'errore che, alla prima prova, faceva rimanere un docstring
    penzolante dopo aver rimosso il suo teorema, con l'errore
    "unexpected token '/--'; expected 'lemma'".

    Quindi: si individuano prima le righe che aprono una dichiarazione o un
    comando di struttura, poi ciascuna viene estesa ALL'INDIETRO per assorbire
    gli attributi, i docstring e le righe vuote che la precedono.
    """
    avvii = [i for i, r in enumerate(righe)
             if _apre_dichiarazione(r) or _apre_struttura(r)]
    if not avvii:
        return [(0, len(righe) - 1)]

    def estendi_indietro(i: int, limite: int) -> int:
        """Riporta l'inizio del blocco sopra attributi, docstring e righe vuote."""
        j = i
        while j - 1 > limite:
            prec = righe[j - 1]
            spoglia = prec.strip()
            if not spoglia:
                j -= 1
                continue
            # attributo, eventualmente su piu' righe
            if spoglia.endswith("]") and "@[" in "\n".join(righe[max(limite + 1, j - 6):j]):
                k = j - 1
                while k > limite and "@[" not in righe[k]:
                    k -= 1
                if "@[" in righe[k]:
                    j = k
                    continue
            if spoglia.startswith("@["):
                j -= 1
                continue
            # docstring o commento chiuso subito sopra
            if spoglia.endswith("-/"):
                k = j - 1
                livello = 0
                while k > limite:
                    livello += righe[k].count("-/") - righe[k].count("/-")
                    if livello <= 0 and ("/--" in righe[k] or "/-" in righe[k]):
                        break
                    k -= 1
                j = k
                continue
            break
        return j

    limiti = []
    for k, i in enumerate(avvii):
        # Il limite della risalita e' la riga della dichiarazione PRECEDENTE,
        # non la fine del suo blocco: la fine del blocco precedente e' proprio
        # cio' che stiamo per correggere. Usare quella bloccava la risalita al
        # primo passo, e docstring e attributi restavano attaccati alla
        # dichiarazione sbagliata.
        limite = avvii[k - 1] if k > 0 else -1
        inizio = estendi_indietro(i, limite)
        fine = (avvii[k + 1] - 1) if k + 1 < len(avvii) else len(righe) - 1
        limiti.append([inizio, fine])
    # risistema i confini: il blocco n finisce dove comincia il blocco n+1
    for k in range(len(limiti) - 1):
        limiti[k][1] = limiti[k + 1][0] - 1
    if limiti and limiti[0][0] > 0:
        limiti.insert(0, [0, limiti[0][0] - 1])
    return [(a, b) for a, b in limiti if b >= a]


def _senza_commenti(testo: str) -> str:
    """Toglie commenti e stringhe, per non scambiare un `sorry` citato in un
    commento per un vero buco."""
    import guard
    return guard.strip_comments_and_strings(testo)


def _chiusure_mancanti(testo: str) -> str:
    """Le righe `end` che servono a richiudere namespace e sezioni.

    Troncare il file dopo il teorema bersaglio lascia aperti i `namespace` e i
    `section` che lo contengono, e Lean si ferma con "Unexpected name after
    `end`" oppure con una sezione non chiusa. Qui si tiene la pila di cio' che
    e' stato aperto e si chiude in ordine inverso.
    """
    pila: list[str] = []
    for riga in testo.split("\n"):
        if riga[:1].isspace() or not riga.strip():
            continue
        parole = riga.split()
        if not parole:
            continue
        if parole[0] == "namespace" and len(parole) > 1:
            pila.append(parole[1])
        elif parole[0] == "section":
            pila.append(parole[1] if len(parole) > 1 else "")
        elif parole[0] == "end":
            if pila:
                pila.pop()
    if not pila:
        return ""
    righe = ["", "-- chiusure aggiunte automaticamente dopo il troncamento del file"]
    for nome in reversed(pila):
        righe.append(f"end {nome}".rstrip())
    return "\n".join(righe) + "\n"


def _nome_dichiarato(blocco: str) -> str | None:
    m = re.search(r"^(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|nonrec|noncomputable)\s+)*"
                  r"(?:theorem|lemma)\s+([\w'.\u00ab\u00bb]+)", blocco, re.M)
    return m.group(1) if m else None


def estrai(problema: Problem, indice: ProblemIndex) -> ProvaArchivio:
    """Il file dell'archivio senza tutti gli altri teoremi."""
    if not problema.proof_is_sorry_free:
        raise NonEstraibile(
            f"{problema.theorem}: l'archivio non ne fornisce una dimostrazione "
            f"(il termine di prova contiene `sorry`)")
    if not problema.range:
        raise NonEstraibile(f"{problema.theorem}: posizione nel sorgente sconosciuta")

    testo = problema.source_file.read_text(encoding="utf-8")
    righe = testo.split("\n")

    # Nome corto del teorema bersaglio: nel file e' scritto senza il namespace.
    corto = problema.theorem.split(".")[-1]
    pezzi_nome = problema.theorem.split(".")

    tenuti, rimossi, trovato = [], 0, False
    for inizio, fine in _blocchi(righe):
        blocco = "\n".join(righe[inizio:fine + 1])
        nome = _nome_dichiarato(blocco)
        if nome is not None:
            e_bersaglio = (nome == problema.theorem or nome == corto
                           or problema.theorem.endswith("." + nome)
                           or (nome.split(".")[-1] == corto
                               and all(x in pezzi_nome for x in nome.split("."))))
            if e_bersaglio:
                tenuti.append(blocco)
                trovato = True
                # Tutto cio' che viene DOPO il teorema bersaglio non puo'
                # servirgli: in Lean un file si legge dall'alto in basso.
                # Tenerlo causava soltanto errori, perche' quei teoremi usavano
                # a loro volta lemmi che avevamo dovuto rimuovere.
                break
            if "sorry" in _senza_commenti(blocco):
                rimossi += 1
                continue
        tenuti.append(blocco)

    if not trovato:
        raise NonEstraibile(
            f"{problema.theorem}: non sono riuscito a individuare la dichiarazione "
            f"nel file (nome atteso `{corto}`)")

    corpo = "\n".join(tenuti)
    corpo += _chiusure_mancanti(corpo)

    intestazione = (
        "/-\n"
        "  DIMOSTRAZIONE DELL'ARCHIVIO, estratta automaticamente.\n"
        "\n"
        f"  Problema: {problema.theorem}\n"
        f"  Modulo:   {problema.module}\n"
        f"  Rimossi:  {rimossi} teoremi dello stesso file che contenevano `sorry`\n"
        f"            (i lemmi ausiliari DIMOSTRATI sono stati tenuti: spesso\n"
        f"            la dimostrazione del bersaglio li usa)\n"
        "\n"
        "  Serve a stabilire se la dimostrazione fornita dall'archivio passa\n"
        "  davvero il nostro verificatore. Se non passa, il problema non e'\n"
        "  utilizzabile per calibrare un agente.\n"
        "-/\n")
    return ProvaArchivio(problema=problema.theorem,
                         testo=intestazione + corpo,
                         teoremi_rimossi=rimossi)
