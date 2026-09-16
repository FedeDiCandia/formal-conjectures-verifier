"""
Estrae la dimostrazione che l'archive fornisce, come file candidato autonomo.

A COSA SERVE
------------
Per calibrare un agent servono problems di cui si conosca la answer. Ma
"l'archive lo ha solved_one" non basta: la sua dimostrazione potrebbe usare
`decide +native` (95 cases) o dipendere da un lemma con un buco (17 cases), e il
nostro verifier la rifiuterebbe. Chiedere a un agent di risolvere one di
quei problems significa chiedergli di fare MEGLIO dell'archive, e un
failure non direbbe niente sull'agent.

Il controllo sugli axioms (field_ `archiveProofAxioms` dell'index) e' one_
condizione necessaria ma non sufficiente: non dice se la dimostrazione, estratta
dal suo file e compilata da sola, arriva davvero in fondo al verifier. Per
saperlo bisogna provarci.

Questo module costruisce il file candidato che l'archive stesso consegnerebbe:
gli import, le definizioni locals_, i lemmi ausiliari DIMOSTRATI e il theorem_
target_ con la sua dimostrazione vera. Vengono tolte only_ le dichiarazioni
che contengono `sorry`, perche' il verifier rifiuta un file che ne
contenga.

Togliere TUTTI gli altri theorems era la scelta sbagliata: alla before trial 9
dimostrazioni su 23 sono fallite con "Unknown identifier", perche' usavano un
lemma neighbour nello stesso file. Il failure era dell'estrattore, non
dell'archive.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from index import Problem, ProblemIndex   # noqa: E402


class NotExtractable(ValueError):
    """Non si puo' costruire un candidato autonomo per questo problem."""


@dataclass
class ArchiveProof:
    problem: str
    text: str
    teoremi_rimossi: int


#: Parole key_ che aprono one_ DICHIARAZIONE.
_DECLARATIONS = ("theorem", "lemma", "def", "abbrev", "instance", "structure",
                  "inductive", "class", "example", "opaque", "axiom")

#: Modificatori che possono precedere one_ word key_.
_MODIFIERS = ("private", "protected", "noncomputable", "partial", "unsafe",
                 "scoped", "local", "nonrec", "public", "meta", "mutual")

#: Comandi di struttura: aprono un block ma non dichiarano nulla.
#: Si confrontano come PAROLE INTERE. Confrontarli come prefissi e' state un
#: finding vero: la line di un docstring che cominciava con "endomorphism of a
#: finite set is surjective. -/" veniva letta come un `end`, il block del
#: theorem_ precedente si fermava one_ line troppo presto e la queue del docstring
#: restava penzolante, con "unexpected identifier; expected command". Succedeva
#: su GottschalkSurjunctivity.isSurjunctive_of_finite.
_STRUCTURAL = ("namespace", "end", "section", "import", "open", "variable",
                "variables", "universe", "set_option", "attribute", "notation",
                "notation3", "deriving", "macro", "macro_rules", "syntax",
                "elab", "elab_rules", "run_cmd")

#: Questi two invece si attaccano al loro argomento (`#check`, `/-!# Titolo`).
_STRUCTURAL_PREFIX = ("#", "/-!")

_RE_STRUCTURAL = re.compile(
    "^(?:" + "|".join(re.escape(p) for p in _STRUCTURAL) + r")(?![A-Za-z0-9_'])")
# NB: `/-` NON e' qui. Ci era finito, e siccome `/--` comincia con `/-` i
# docstring tornavano a essere inizi di block: rimuovendo un theorem_ il suo
# docstring restava penzolante, con l'error
# "unexpected token '/--'; expected 'lemma'". Un docstring appartiene sempre
# alla declaration che lo segue, mai a se' stesso.


def _opens_declaration(line: str) -> bool:
    if not line or line[0].isspace():
        return False
    words = line.split()
    i = 0
    while i < len(words) and words[i] in _MODIFIERS:
        i += 1
    return i < len(words) and words[i].split(":")[0] in _DECLARATIONS


def _opens_structure(line: str) -> bool:
    if not line or line[0].isspace():
        return False
    if line.startswith(_STRUCTURAL_PREFIX):
        return True
    return bool(_RE_STRUCTURAL.match(line))


def _blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Spezza il file in blocks di prime_ level: (line iniziale, line finale).

    Il punto delicato: un docstring `/-- ... -/` e un attributo `@[...]`
    APPARTENGONO alla declaration che li segue. Trattarli come blocks a se'
    e' esattamente l'error che, alla before trial, faceva rimanere un docstring
    penzolante after aver rimosso il suo theorem_, con l'error
    "unexpected token '/--'; expected 'lemma'".

    Quindi: si individuano before le lines che aprono one_ declaration o un
    command di struttura, poi ciascuna viene estesa ALL'INDIETRO per assorbire
    gli attributi, i docstring e le lines vuote che la precedono.
    """
    starts = [i for i, r in enumerate(lines)
             if _opens_declaration(r) or _opens_structure(r)]
    if not starts:
        return [(0, len(lines) - 1)]

    def extend_backwards(i: int, limit: int) -> int:
        """Riporta l'start del block above attributi, docstring e lines vuote."""
        j = i
        while j - 1 > limit:
            prec = lines[j - 1]
            bare = prec.strip()
            if not bare:
                j -= 1
                continue
            # attributo, eventualmente su piu' lines
            if bare.endswith("]") and "@[" in "\n".join(lines[max(limit + 1, j - 6):j]):
                k = j - 1
                while k > limit and "@[" not in lines[k]:
                    k -= 1
                if "@[" in lines[k]:
                    j = k
                    continue
            if bare.startswith("@["):
                j -= 1
                continue
            # docstring o commento chiuso subito above
            if bare.endswith("-/"):
                k = j - 1
                level = 0
                while k > limit:
                    level += lines[k].count("-/") - lines[k].count("/-")
                    if level <= 0 and ("/--" in lines[k] or "/-" in lines[k]):
                        break
                    k -= 1
                j = k
                continue
            break
        return j

    bounds = []
    for k, i in enumerate(starts):
        # Il limit della risalita e' la line della declaration PRECEDENTE,
        # non la end del suo block: la end del block precedente e' proprio
        # cio' che stiamo per correggere. Usare quella bloccava la risalita al
        # prime_ step, e docstring e attributi restavano attaccati alla
        # declaration sbagliata.
        limit = starts[k - 1] if k > 0 else -1
        start = extend_backwards(i, limit)
        end = (starts[k + 1] - 1) if k + 1 < len(starts) else len(lines) - 1
        bounds.append([start, end])
    # risistema i confini: il block n finisce dove comincia il block n+1
    for k in range(len(bounds) - 1):
        bounds[k][1] = bounds[k + 1][0] - 1
    if bounds and bounds[0][0] > 0:
        bounds.insert(0, [0, bounds[0][0] - 1])
    return [(a, b) for a, b in bounds if b >= a]


def _without_comments(text: str) -> str:
    """Toglie commenti e stringhe, per non scambiare un `sorry` citato in un
    commento per un vero buco."""
    import guard
    return guard.strip_comments_and_strings(text)


def _comment_imbalance(text: str) -> int:
    """Quante chiusure `-/` in piu' rispetto alle aperture `/-`.

    Serve quando si rimuove un block: se conteneva la closure di un commento
    cominciato piu' above, va rimessa, altrimenti il commento resta aperto e si
    mangia tutto il resto del file.
    """
    apre = closes = 0
    i, n = 0, len(text)
    while i < n - 1:
        if text[i] == "-" and text[i + 1] == "-" and apre == closes:
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text[i] == "/" and text[i + 1] == "-":
            apre += 1; i += 2; continue
        if text[i] == "-" and text[i + 1] == "/":
            closes += 1; i += 2; continue
        i += 1
    return closes - apre


def _cut_open_comment(text: str) -> str:
    """Toglie un commento a block rimasto aperto.

    Troncare il file after il theorem_ target_ puo' cadere inside un commento
    `/- ... -/` il cui `-/` stava piu' in low. Lean si ferma con
    "unterminated comment". Qui si trova il `/-` rimasto senza closure e si
    size_ da li' in poi: e' only_ un commento, non si perde nulla di
    matematico.
    """
    depth = 0
    last_opening = None
    i, n = 0, len(text)
    while i < n - 1:
        if text[i] == "-" and text[i + 1] == "-" and depth == 0:
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text[i] == "/" and text[i + 1] == "-":
            if depth == 0:
                last_opening = i
            depth += 1
            i += 2
            continue
        if text[i] == "-" and text[i + 1] == "/":
            depth = max(0, depth - 1)
            i += 2
            continue
        i += 1
    if depth > 0 and last_opening is not None:
        return text[:last_opening].rstrip() + "\n"
    return text


def _missing_closers(text: str) -> str:
    """Le lines `end` che servono a richiudere namespace e sezioni.

    Troncare il file after il theorem_ target_ lascia open_ i `namespace` e i
    `section` che lo contengono, e Lean si ferma con "Unexpected name after
    `end`" oppure con one_ sezione non chiusa. Qui si tiene la stack di cio' che
    e' state aperto e si closes in order inverso.
    """
    stack: list[str] = []
    for line in text.split("\n"):
        if line[:1].isspace() or not line.strip():
            continue
        words = line.split()
        if not words:
            continue
        if words[0] == "namespace" and len(words) > 1:
            stack.append(words[1])
        elif words[0] == "section":
            stack.append(words[1] if len(words) > 1 else "")
        elif words[0] == "end":
            if stack:
                stack.pop()
    if not stack:
        return ""
    lines = ["", "-- chiusure aggiunte automaticamente after il troncamento del file"]
    for name in reversed(stack):
        lines.append(f"end {name}".rstrip())
    return "\n".join(lines) + "\n"


def _declared_name(block: str) -> str | None:
    m = re.search(r"^(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|nonrec|noncomputable)\s+)*"
                  r"(?:theorem|lemma)\s+([\w'.\u00ab\u00bb]+)", block, re.M)
    return m.group(1) if m else None


def extract(problem: Problem, index: ProblemIndex) -> ArchiveProof:
    """Il file dell'archive senza all_of gli altri theorems."""
    if not problem.proof_is_complete:
        raise NotExtractable(
            f"{problem.theorem}: l'archive non ne fornisce one_ dimostrazione "
            f"(il termine di trial contiene `sorry`)")
    if not problem.range:
        raise NotExtractable(f"{problem.theorem}: position nel source_text sconosciuta")

    text = problem.source_file.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Nome short del theorem_ target_: nel file e' scritto senza il namespace.
    short = problem.theorem.split(".")[-1]
    name_parts = problem.theorem.split(".")

    kept, removed, found = [], 0, False
    for start, end in _blocks(lines):
        block = "\n".join(lines[start:end + 1])
        name = _declared_name(block)
        if name is not None:
            is_target = (name == problem.theorem or name == short
                           or problem.theorem.endswith("." + name)
                           or (name.split(".")[-1] == short
                               and all(x in name_parts for x in name.split("."))))
            if is_target:
                kept.append(block)
                found = True
                # Tutto cio' che viene DOPO il theorem_ target_ non puo'
                # servirgli: in Lean un file si legge dall'high in low.
                # Tenerlo causava soltanto errors, perche' quei theorems usavano
                # a loro volta lemmi che avevamo dovuto rimuovere.
                break
            clean_one = _without_comments(block)
            # Si rimuovono also_ i lemmi neighbours che usano `native_decide` o
            # `decide +native`: il verifier rifiuta l'intero file se li
            # trova, e il theorem_ target_ non ne ha bisogno (se ne avesse
            # bisogno, i suoi axioms non sarebbero clean_ones e il problem non
            # sarebbe fra i candidates).
            if ("sorry" in clean_one or "native_decide" in clean_one
                    or re.search(r"\+\s*native", clean_one)):
                removed += 1
                # Se il block rimosso CHIUDEVA un commento aperto piu' above,
                # togliendolo si lascia il commento aperto e tutto il resto del
                # file — target_ compreso — finisce inside il commento. Si
                # rimette la closure al slot_ suo.
                deficit = _comment_imbalance(block)
                if deficit > 0:
                    kept.append("-/" * deficit)
                continue
        kept.append(block)

    if not found:
        raise NotExtractable(
            f"{problem.theorem}: non sono succeeded a individuare la declaration "
            f"nel file (name expected_one `{short}`)")

    body = "\n".join(kept)
    # Rimettere a slot_ la closure di un commento puo' lasciare un docstring
    # VUOTO (`/--` seguito subito da `-/`): Lean lo rifiuta, perche' un
    # docstring deve documentare qualcosa. Si toglie.
    body = re.sub(r"/--\s*-/\s*\n", "", body)
    body = _cut_open_comment(body)
    body += _missing_closers(body)

    # Controllo di sicurezza: after all_of queste manipolazioni il theorem_
    # target_ deve essere ancora li'. Se non c'e', il file compilerebbe
    # benissimo e comparator fallirebbe con un PANIC oscuro
    # ("Constant not found"): meglio un error chiaro adesso.
    if not re.search(rf"(?:theorem|lemma)\s+{re.escape(short)}(?![\w'])", body) and \
       not re.search(rf"(?:theorem|lemma)\s+\S*{re.escape(short)}(?![\w'])", body):
        raise NotExtractable(
            f"{problem.theorem}: after l'estrazione il theorem_ target_ non e' "
            f"piu' nel file. E' un finding dell'estrattore, non dell'archive.")

    header = (
        "/-\n"
        "  DIMOSTRAZIONE DELL'ARCHIVIO, estratta automaticamente.\n"
        "\n"
        f"  Problema: {problem.theorem}\n"
        f"  Modulo:   {problem.module}\n"
        f"  Rimossi:  {removed} theorems dello stesso file che contenevano `sorry`\n"
        f"            (i lemmi ausiliari DIMOSTRATI sono stati kept: spesso\n"
        f"            la dimostrazione del target_ li usa)\n"
        "\n"
        "  Serve a stabilire se la dimostrazione fornita dall'archive passa\n"
        "  davvero il nostro verifier. Se non passa, il problem non e'\n"
        "  utilizzabile per calibrare un agent.\n"
        "-/\n")
    return ArchiveProof(problem=problem.theorem,
                         text=header + body,
                         teoremi_rimossi=removed)
