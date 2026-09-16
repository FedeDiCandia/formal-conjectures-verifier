#!/usr/bin/env python3
"""
Seleziona i problems GIA' RISOLTI la cui dimostrazione non e' formalizzata
nell'archive, e li ordina per difficolta' expected_value della formalizzazione.

A COSA SERVE
------------
Formalizzare one_ dimostrazione note non e' ricerca: e' un contributo che
l'archive accetta come pull request (CONTRIBUTING.md: «very short proofs for
solved items or counterexamples»), ed e' il compito su cui l'agent ha gia'
misurato 9 successi su 11 in calibrazione.

CHI ENTRA
---------
  * categoria `research solved` o `textbook`;
  * nessun `formal_proof using formal_conjectures` (quello dichiara la trial
    gia' nell'archive); `lean4` e `other_system` restano, ma vengono segnati;
  * la dimostrazione d'archive e' letteralmente `sorry`. Chi ha one_
    dimostrazione scritta che dipende da `sorryAx` attraverso un lemma bucato,
    o da `native_decide`, e' ESCLUSO: e' quello che chiede la consegna;
  * l'statement non contiene `answer(sorry)`: elaborato diventa `True ↔ P`, e
    per un problem solved_one "no" sarebbe un statement falso.

COME SI ORDINA, E PERCHE' NON PER LUNGHEZZA DELL'ENUNCIATO
----------------------------------------------------------
La before versione ordinava per length dell'statement e metteva in cima
Goldbach ternario (Helfgott), Ramanujan-Petersson (Deligne), la trascendenza di
pi + e. E' la lezione di STATO.md in un'altra forma: un statement breve non
indica one_ dimostrazione breve, spesso indica un theorem_ celebre.

Il segnale vero sta nella FONTE, cioe' nella docstring, che per i problems
solved_ riporta quasi sempre chi l'ha dimostrato e come:
  * a favore: «easy to see», «trivial», «obvious», «Proof: ...», «Indeed»,
    «considerations module 8», «Helper lemma», «sanity check» — la source_ stessa
    dice che la dimostrazione e' corta, o la scrive;
  * against: one_ citazione a un articolo come source_ della dimostrazione
    («Browkin and Schinzel [BrSc95] proved»), names di theorems profondi;
  * against, nell'statement: insiemi infiniti, densita', irrazionalita',
    trascendenza, bounds, cardinali, somme infinite — formalizzazioni lunghe
    also_ quando la matematica e' note;
  * against: un computation oltre la portata del kernel (bounds come 10^7);
  * minori: length dell'statement, definizioni out_of da Mathlib (estimate sui
    names), subjects AMS diversi da 5 e 11, categoria textbook (a favore),
    `formal_proof` gia' esistente altrove (il contributo vale meno).

Uso:
  env FCS_ARCHIVE=... FCS_INDEX=verifier/problem_index_main.json \\
    .venv/bin/python scripts/select_formalisations.py [--mostra 30]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "agent"))

import config                                   # noqa: E402
from index import ProblemIndex                  # noqa: E402
from hide import _separator_position      # noqa: E402

PERMITTED = {"propext", "Classical.choice", "Quot.sound"}
ELEMENTARY = {"5", "11"}

#: la source_ dice che la dimostrazione e' corta, o la scrive
#: «trivial» count_ only_ come giudizio su one_ dimostrazione: la before versione
#: prendeva also_ «non-trivial unit» (Kaplansky), «non-trivial invariant subspace»
#: (Read, 1985), «trivial counter examples», «trivial Picard group». «Indeed» e
#: «it is clear» sono stati tolti: compaiono inside dimostrazioni di ricerca.
_SHORT = re.compile(
    r"easy to (see|show|trials|check)|\bis easy\b|\beasily\b|"
    r"(?<!non-)(?<!non)\btrivial(ly)?\b(?!\s*(counter|units?\b|\(|Picard|way|version|cases|group))|"
    r"\bobvious(ly)?\b|straightforward|\bsimple (proof|argument|construction|observation|computation)|"
    r"elementary proof|helper lemma|sanity check|\bProof:|"
    r"can be (proven|proved|shown|checked) by|follows (immediately|directly)|"
    r"considerations module|by (a )?(direct|simple|finite) (computation|calculation|check)|"
    r"check (the conjecture )?directly", re.I)
#: la dimostrazione viene da un articolo o da un theorem_ profondo
_CITATION = re.compile(r"\[[A-Z][A-Za-z]{1,8}\d{2}[a-z]?\]")
_PROVED = re.compile(r"\b(proved|proven|showed|shown|established|resolved|answered|"
                      r"disproved|confirmed|settled|solved)\b", re.I)
_DEEP = re.compile(
    r"Helfgott|Deligne|Nesterenko|Ap[ée]ry|Keevash|Furstenberg|Heath-Brown|Tao\b|"
    r"Szemer[ée]di|Green[–-]Tao|Maynard|Zhang|Bourgain|Wiles|Perelman|Freedman|Smale|"
    r"Baker|Roth\b|Siegel|Faltings|Mih[ăa]ilescu|Hough|Nesetril|Ne[šs]et[řr]il|R[öo]dl|"
    r"modular|Riemann hypothesis|circle method|sieve|ergodic|conjecture\b.*\bproved", re.I)
#: nell'statement: oggetti la cui formalizzazione e' lunga also_ per results noti
_HARD_STATEMENT = re.compile(
    r"\.Infinite|Infinite ↑|HasDensity|HasPosDensity|Density|Irrational|Transcendental|"
    r"Tendsto|atTop|liminf|limsup|dimH|Cardinal|riemannZeta|∑'|Real\.log|Real\.logb|"
    r"MeasureTheory|volume|∫|deriv|Dense|chromaticNumber|Packing|BB \d|=ᶠ")
_LARGE_POWER = re.compile(r"10 \^ ([5-9]|\d\d)|2 \^ ([2-9]\d)|\b\d{6,}\b")

_DECL = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|noncomputable|scoped)\s+)*"
                   r"(?:def|abbrev|structure|inductive|class|opaque)\s+([^\s:({\[]+)", re.M)
_IDENT = re.compile(r"[A-Za-z_][\w'!?]*(?:\.[A-Za-z_][\w'!?]*)*")


def declared_names(text: str) -> set[str]:
    """Nomi corti (last_one componente) delle definizioni dichiarate in un file."""
    return {m.group(1).split(".")[-1] for m in _DECL.finditer(text)}


def fcfm_names() -> set[str]:
    names: set[str] = set()
    for f in (config.ARCHIVE / "FormalConjecturesForMathlib").rglob("*.lean"):
        names |= declared_names(f.read_text(encoding="utf-8", errors="replace"))
    return names


def proof_body(p) -> str | None:
    text = p.source_text()
    pos = _separator_position(text)
    return None if pos is None else text[pos + 2:].strip()


def valuta(p, locals_: list[str], di_fcfm: list[str]) -> tuple[float, list[str]]:
    """Punteggio di difficolta' expected_value (piu' low = piu' facile) e i reasons."""
    doc = " ".join((p.docstring or "").split())
    subjects = set(p.subjects)
    points, reasons = 0.0, []

    def add_(value_: float, reason: str) -> None:
        nonlocal points
        points += value_
        reasons.append(reason)

    if _SHORT.search(doc):
        add_(-6, "source_: trial corta")
    citata = bool(_CITATION.search(doc) and _PROVED.search(doc))
    if citata:
        add_(+4, "source_: articolo")
    if _DEEP.search(doc):
        add_(+6, "source_: theorem_ profondo")
    if _HARD_STATEMENT.search(p.statement):
        add_(+5, "statement: infinito/analisi")
    if _LARGE_POWER.search(p.statement):
        add_(+4, "computation grande")
    if p.category == "textbook":
        add_(-2, "textbook")
    if not (subjects and subjects <= ELEMENTARY):
        add_(+1 if subjects & ELEMENTARY else +3, "out_of da AMS 5/11")
    if locals_ or di_fcfm:
        add_(0.5 * len(locals_) + 1.0 * len(di_fcfm), "definizioni out_of Mathlib")
    if p.formal_proof_kind in ("lean4", "other_system"):
        add_(+1, "trial gia' altrove")
    points += len(p.statement) / 80
    return round(points, 2), reasons


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mostra", type=int, default=30)
    ap.add_argument("--output", default=str(ROOT / "research_data" / "formalizzazioni_candidati.json"))
    args = ap.parse_args()

    idx = ProblemIndex.load()
    fcfm = fcfm_names()
    per_file: dict[Path, set[str]] = {}
    excluded = collections.Counter()
    candidates = []

    for p in idx.problems:
        if p.category not in ("research solved", "textbook"):
            continue
        excluded["0 solved+textbook in tutto"] += 1
        if p.formal_proof_kind == "formal_conjectures":
            excluded["1 formal_proof using formal_conjectures"] += 1
            continue
        if "sorryAx" not in p.archive_proof_axioms:
            excluded["2 dimostrazione gia' complete_ nell'archive"] += 1
            continue
        if set(p.archive_proof_axioms) - PERMITTED - {"sorryAx"}:
            excluded["3 dipende da native_decide o altri axioms"] += 1
            continue
        try:
            body = proof_body(p)
        except Exception:
            excluded["4 source_text non leggibile dall'index"] += 1
            continue
        if body is None or not re.fullmatch(r"(by\s+)?sorry", body):
            excluded["5 trial scritta che dipende da un lemma con sorry"] += 1
            continue
        if p.statement_has_sorry or p.answer_placeholder_in_source:
            excluded["6 statement con answer(sorry)"] += 1
            continue

        f = p.source_file
        if f not in per_file:
            per_file[f] = declared_names(f.read_text(encoding="utf-8", errors="replace"))
        token = {t.split(".")[-1] for t in _IDENT.findall(p.statement)}
        locals_ = sorted(token & per_file[f])
        di_fcfm = sorted((token & fcfm) - set(locals_))
        score, reasons = valuta(p, locals_, di_fcfm)
        candidates.append({
            "problem": p.theorem, "module": p.module, "categoria": p.category,
            "ams": sorted(p.subjects, key=lambda s: int(s) if s.isdigit() else 999),
            "lunghezza_enunciato": len(p.statement),
            "definizioni_locali": locals_, "definizioni_fcfm": di_fcfm,
            "formal_proof": p.formal_proof_kind, "link": p.formal_proof_link,
            "score": score, "reasons": reasons,
            "statement": p.statement, "docstring": (p.docstring or "").strip(),
        })

    candidates.sort(key=lambda c: (c["score"], c["problem"]))
    Path(args.output).write_text(json.dumps(candidates, ensure_ascii=False, indent=1),
                                 encoding="utf-8")

    print("FILTRI")
    for k in sorted(excluded):
        print(f"  {k[2:]:52s} {excluded[k]:5d}")
    print(f"  {'CANDIDATES':52s} {len(candidates):5d}")
    print("  per categoria:", dict(collections.Counter(c["categoria"] for c in candidates)))
    print("  con formal_proof altrove:", sum(1 for c in candidates if c["formal_proof"]))
    count_ = collections.Counter(m for c in candidates for m in c["reasons"])
    print("  segnali:", dict(count_))
    print("  score < 0 (la source_ indica one_ trial corta e niente di hard):",
          sum(1 for c in candidates if c["score"] < 0))
    print()
    for i, c in enumerate(candidates[:args.mostra], 1):
        s = " ".join(c["statement"].split())
        print(f"{i:3d} {c['score']:6.1f} {'tb' if c['categoria'] == 'textbook' else 'rs'} "
              f"AMS {' '.join(c['ams'])}  {c['problem']}")
        print(f"        {'; '.join(c['reasons']) or '-'}")
        print(f"        S: {s[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
