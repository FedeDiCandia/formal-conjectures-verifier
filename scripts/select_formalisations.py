#!/usr/bin/env python3
"""
Select the problems that are ALREADY SOLVED but whose proof is not formalised in the
archive, and order them by the expected difficulty of formalising them.

WHAT IT IS FOR
--------------
Formalising a known proof is not research: it is a contribution the archive accepts
as a pull request (CONTRIBUTING.md: "very short proofs for solved items or
counterexamples"), and it is the task the agent has already been measured on.

A problem is a candidate if:
  * it carries no `formal_proof using formal_conjectures` (that declares the proof is
    already in the archive); `lean4` and `other_system` stay, but are flagged;
  * the archive's proof is literally `sorry`. Anything with a written proof that
    depends on `sorryAx` through a holed lemma, or on `native_decide`, is EXCLUDED:
    that is what the contribution asks for;
  * the statement contains no `answer(sorry)`: elaborated, it becomes `True ↔ P`, and
    for a problem solved "no" that would be a false statement.

HOW THEY ARE ORDERED, AND WHY NOT BY LENGTH OF STATEMENT
--------------------------------------------------------
The first version ordered by length of statement and put ternary Goldbach
(Helfgott), Ramanujan-Petersson (Deligne) and the transcendence of pi + e at the top.
A short statement does not indicate a short proof; often it indicates a famous
theorem.

The real signal is in the SOURCE, that is in the docstring, which for solved problems
nearly always says who proved it and how:

  * in favour: "easy to see", "trivial", "Proof: ...", "considerations mod 8",
    "Helper lemma", "sanity check" — the source itself says the proof is short, or
    writes it out;
  * against: a citation to a paper as the source of the proof;
  * against: a deep theorem named in the docstring, which makes formalisation long
    even when the mathematics is known;
  * against: a computation beyond the kernel's reach (bounds like 10^7);
  * minor: length of the statement, definitions outside Mathlib (an estimate of the
    work of copying them), and a `formal_proof` that already exists elsewhere (the
    contribution is worth less).
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

#: the source says the proof is short, or writes it out
#: "trivial" counts only as a judgement about a proof: the first version also
#: caught "non-trivial unit" (Kaplansky), "non-trivial invariant subspace"
#: (Read, 1985), «trivial counter examples», «trivial Picard group». «Indeed» e
#: and "it is clear", which were removed: they appear inside research proofs.
_SHORT = re.compile(
    r"easy to (see|show|trials|check)|\bis easy\b|\beasily\b|"
    r"(?<!non-)(?<!non)\btrivial(ly)?\b(?!\s*(counter|units?\b|\(|Picard|way|version|cases|group))|"
    r"\bobvious(ly)?\b|straightforward|\bsimple (proof|argument|construction|observation|computation)|"
    r"elementary proof|helper lemma|sanity check|\bProof:|"
    r"can be (proven|proved|shown|checked) by|follows (immediately|directly)|"
    r"considerations module|by (a )?(direct|simple|finite) (computation|calculation|check)|"
    r"check (the conjecture )?directly", re.I)
#: the proof comes from a paper or from a deep theorem
_CITATION = re.compile(r"\[[A-Z][A-Za-z]{1,8}\d{2}[a-z]?\]")
_PROVED = re.compile(r"\b(proved|proven|showed|shown|established|resolved|answered|"
                      r"disproved|confirmed|settled|solved)\b", re.I)
_DEEP = re.compile(
    r"Helfgott|Deligne|Nesterenko|Ap[ée]ry|Keevash|Furstenberg|Heath-Brown|Tao\b|"
    r"Szemer[ée]di|Green[–-]Tao|Maynard|Zhang|Bourgain|Wiles|Perelman|Freedman|Smale|"
    r"Baker|Roth\b|Siegel|Faltings|Mih[ăa]ilescu|Hough|Nesetril|Ne[šs]et[řr]il|R[öo]dl|"
    r"modular|Riemann hypothesis|circle method|sieve|ergodic|conjecture\b.*\bproved", re.I)
#: in the statement: objects whose formalisation is long even for known results
_HARD_STATEMENT = re.compile(
    r"\.Infinite|Infinite ↑|HasDensity|HasPosDensity|Density|Irrational|Transcendental|"
    r"Tendsto|atTop|liminf|limsup|dimH|Cardinal|riemannZeta|∑'|Real\.log|Real\.logb|"
    r"MeasureTheory|volume|∫|deriv|Dense|chromaticNumber|Packing|BB \d|=ᶠ")
_LARGE_POWER = re.compile(r"10 \^ ([5-9]|\d\d)|2 \^ ([2-9]\d)|\b\d{6,}\b")

_DECL = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|noncomputable|scoped)\s+)*"
                   r"(?:def|abbrev|structure|inductive|class|opaque)\s+([^\s:({\[]+)", re.M)
_IDENT = re.compile(r"[A-Za-z_][\w'!?]*(?:\.[A-Za-z_][\w'!?]*)*")


def declared_names(text: str) -> set[str]:
    """Short names (last component) of the definitions declared in a file."""
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


def valuta(p, local_names: list[str], di_fcfm: list[str]) -> tuple[float, list[str]]:
    """Expected difficulty score (lower = easier) and the reasons for it."""
    doc = " ".join((p.docstring or "").split())
    subjects = set(p.subjects)
    points, reasons = 0.0, []

    def add(value: float, reason: str) -> None:
        nonlocal points
        points += value
        reasons.append(reason)

    if _SHORT.search(doc):
        add(-6, "source: trial corta")
    citata = bool(_CITATION.search(doc) and _PROVED.search(doc))
    if citata:
        add(+4, "source: articolo")
    if _DEEP.search(doc):
        add(+6, "source: theorem profondo")
    if _HARD_STATEMENT.search(p.statement):
        add(+5, "statement: infinito/analisi")
    if _LARGE_POWER.search(p.statement):
        add(+4, "computation grande")
    if p.category == "textbook":
        add(-2, "textbook")
    if not (subjects and subjects <= ELEMENTARY):
        add(+1 if subjects & ELEMENTARY else +3, "outside da AMS 5/11")
    if local_names or di_fcfm:
        add(0.5 * len(local_names) + 1.0 * len(di_fcfm), "definizioni outside Mathlib")
    if p.formal_proof_kind in ("lean4", "other_system"):
        add(+1, "proof already elsewhere")
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
        excluded["0 solved+textbook in all"] += 1
        if p.formal_proof_kind == "formal_conjectures":
            excluded["1 formal_proof using formal_conjectures"] += 1
            continue
        if "sorryAx" not in p.archive_proof_axioms:
            excluded["2 proof already complete in the archive"] += 1
            continue
        if set(p.archive_proof_axioms) - PERMITTED - {"sorryAx"}:
            excluded["3 dipende da native_decide o altri axioms"] += 1
            continue
        try:
            body = proof_body(p)
        except Exception:
            excluded["4 source not readable from the index"] += 1
            continue
        if body is None or not re.fullmatch(r"(by\s+)?sorry", body):
            excluded["5 written proof that depends on a lemma with sorry"] += 1
            continue
        if p.statement_has_sorry or p.answer_placeholder_in_source:
            excluded["6 statement with answer(sorry)"] += 1
            continue

        f = p.source_file
        if f not in per_file:
            per_file[f] = declared_names(f.read_text(encoding="utf-8", errors="replace"))
        token = {t.split(".")[-1] for t in _IDENT.findall(p.statement)}
        local_names = sorted(token & per_file[f])
        di_fcfm = sorted((token & fcfm) - set(local_names))
        score, reasons = valuta(p, local_names, di_fcfm)
        candidates.append({
            "problem": p.theorem, "module": p.module, "category": p.category,
            "ams": sorted(p.subjects, key=lambda s: int(s) if s.isdigit() else 999),
            "lunghezza_enunciato": len(p.statement),
            "definizioni_locali": local_names, "definizioni_fcfm": di_fcfm,
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
    print("  by category:", dict(collections.Counter(c["category"] for c in candidates)))
    print("  with formal_proof elsewhere:", sum(1 for c in candidates if c["formal_proof"]))
    count = collections.Counter(m for c in candidates for m in c["reasons"])
    print("  segnali:", dict(count))
    print("  score < 0 (the source indicates a short proof and nothing hard):",
          sum(1 for c in candidates if c["score"] < 0))
    print()
    for i, c in enumerate(candidates[:args.mostra], 1):
        s = " ".join(c["statement"].split())
        print(f"{i:3d} {c['score']:6.1f} {'tb' if c['category'] == 'textbook' else 'rs'} "
              f"AMS {' '.join(c['ams'])}  {c['problem']}")
        print(f"        {'; '.join(c['reasons']) or '-'}")
        print(f"        S: {s[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
