#!/usr/bin/env python3
"""
Seleziona i problemi GIA' RISOLTI la cui dimostrazione non e' formalizzata
nell'archivio, e li ordina per difficolta' attesa della formalizzazione.

A COSA SERVE
------------
Formalizzare una dimostrazione nota non e' ricerca: e' un contributo che
l'archivio accetta come pull request (CONTRIBUTING.md: «very short proofs for
solved items or counterexamples»), ed e' il compito su cui l'agente ha gia'
misurato 9 successi su 11 in calibrazione.

CHI ENTRA
---------
  * categoria `research solved` o `textbook`;
  * nessun `formal_proof using formal_conjectures` (quello dichiara la prova
    gia' nell'archivio); `lean4` e `other_system` restano, ma vengono segnati;
  * la dimostrazione d'archivio e' letteralmente `sorry`. Chi ha una
    dimostrazione scritta che dipende da `sorryAx` attraverso un lemma bucato,
    o da `native_decide`, e' ESCLUSO: e' quello che chiede la consegna;
  * l'enunciato non contiene `answer(sorry)`: elaborato diventa `True ↔ P`, e
    per un problema risolto "no" sarebbe un enunciato falso.

COME SI ORDINA, E PERCHE' NON PER LUNGHEZZA DELL'ENUNCIATO
----------------------------------------------------------
La prima versione ordinava per lunghezza dell'enunciato e metteva in cima
Goldbach ternario (Helfgott), Ramanujan-Petersson (Deligne), la trascendenza di
pi + e. E' la lezione di STATO.md in un'altra forma: un enunciato breve non
indica una dimostrazione breve, spesso indica un teorema celebre.

Il segnale vero sta nella FONTE, cioe' nella docstring, che per i problemi
risolti riporta quasi sempre chi l'ha dimostrato e come:
  * a favore: «easy to see», «trivial», «obvious», «Proof: ...», «Indeed»,
    «considerations modulo 8», «Helper lemma», «sanity check» — la fonte stessa
    dice che la dimostrazione e' corta, o la scrive;
  * contro: una citazione a un articolo come fonte della dimostrazione
    («Browkin and Schinzel [BrSc95] proved»), nomi di teoremi profondi;
  * contro, nell'enunciato: insiemi infiniti, densita', irrazionalita',
    trascendenza, limiti, cardinali, somme infinite — formalizzazioni lunghe
    anche quando la matematica e' nota;
  * contro: un calcolo oltre la portata del kernel (limiti come 10^7);
  * minori: lunghezza dell'enunciato, definizioni fuori da Mathlib (stima sui
    nomi), soggetti AMS diversi da 5 e 11, categoria textbook (a favore),
    `formal_proof` gia' esistente altrove (il contributo vale meno).

Uso:
  env FCS_ARCHIVE=... FCS_INDEX=verifier/problem_index_main.json \\
    .venv/bin/python scripts/scegli_formalizzazioni.py [--mostra 30]
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
from nascondi import _posizione_separatore      # noqa: E402

AMMESSI = {"propext", "Classical.choice", "Quot.sound"}
ELEMENTARI = {"5", "11"}

#: la fonte dice che la dimostrazione e' corta, o la scrive
#: «trivial» conta solo come giudizio su una dimostrazione: la prima versione
#: prendeva anche «non-trivial unit» (Kaplansky), «non-trivial invariant subspace»
#: (Read, 1985), «trivial counter examples», «trivial Picard group». «Indeed» e
#: «it is clear» sono stati tolti: compaiono dentro dimostrazioni di ricerca.
_CORTA = re.compile(
    r"easy to (see|show|prove|check)|\bis easy\b|\beasily\b|"
    r"(?<!non-)(?<!non)\btrivial(ly)?\b(?!\s*(counter|units?\b|\(|Picard|way|version|cases|group))|"
    r"\bobvious(ly)?\b|straightforward|\bsimple (proof|argument|construction|observation|computation)|"
    r"elementary proof|helper lemma|sanity check|\bProof:|"
    r"can be (proven|proved|shown|checked) by|follows (immediately|directly)|"
    r"considerations modulo|by (a )?(direct|simple|finite) (computation|calculation|check)|"
    r"check (the conjecture )?directly", re.I)
#: la dimostrazione viene da un articolo o da un teorema profondo
_CITAZIONE = re.compile(r"\[[A-Z][A-Za-z]{1,8}\d{2}[a-z]?\]")
_PROVATO = re.compile(r"\b(proved|proven|showed|shown|established|resolved|answered|"
                      r"disproved|confirmed|settled|solved)\b", re.I)
_PROFONDO = re.compile(
    r"Helfgott|Deligne|Nesterenko|Ap[ée]ry|Keevash|Furstenberg|Heath-Brown|Tao\b|"
    r"Szemer[ée]di|Green[–-]Tao|Maynard|Zhang|Bourgain|Wiles|Perelman|Freedman|Smale|"
    r"Baker|Roth\b|Siegel|Faltings|Mih[ăa]ilescu|Hough|Nesetril|Ne[šs]et[řr]il|R[öo]dl|"
    r"modular|Riemann hypothesis|circle method|sieve|ergodic|conjecture\b.*\bproved", re.I)
#: nell'enunciato: oggetti la cui formalizzazione e' lunga anche per risultati noti
_ENUNCIATO_DURO = re.compile(
    r"\.Infinite|Infinite ↑|HasDensity|HasPosDensity|Density|Irrational|Transcendental|"
    r"Tendsto|atTop|liminf|limsup|dimH|Cardinal|riemannZeta|∑'|Real\.log|Real\.logb|"
    r"MeasureTheory|volume|∫|deriv|Dense|chromaticNumber|Packing|BB \d|=ᶠ")
_POTENZA_GRANDE = re.compile(r"10 \^ ([5-9]|\d\d)|2 \^ ([2-9]\d)|\b\d{6,}\b")

_DICH = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|noncomputable|scoped)\s+)*"
                   r"(?:def|abbrev|structure|inductive|class|opaque)\s+([^\s:({\[]+)", re.M)
_IDENT = re.compile(r"[A-Za-z_][\w'!?]*(?:\.[A-Za-z_][\w'!?]*)*")


def nomi_dichiarati(testo: str) -> set[str]:
    """Nomi corti (ultima componente) delle definizioni dichiarate in un file."""
    return {m.group(1).split(".")[-1] for m in _DICH.finditer(testo)}


def nomi_formal_conjectures_for_mathlib() -> set[str]:
    nomi: set[str] = set()
    for f in (config.ARCHIVE / "FormalConjecturesForMathlib").rglob("*.lean"):
        nomi |= nomi_dichiarati(f.read_text(encoding="utf-8", errors="replace"))
    return nomi


def corpo_dimostrazione(p) -> str | None:
    testo = p.source_text()
    pos = _posizione_separatore(testo)
    return None if pos is None else testo[pos + 2:].strip()


def valuta(p, locali: list[str], di_fcfm: list[str]) -> tuple[float, list[str]]:
    """Punteggio di difficolta' attesa (piu' basso = piu' facile) e i motivi."""
    doc = " ".join((p.docstring or "").split())
    soggetti = set(p.subjects)
    punti, motivi = 0.0, []

    def aggiungi(valore: float, motivo: str) -> None:
        nonlocal punti
        punti += valore
        motivi.append(motivo)

    if _CORTA.search(doc):
        aggiungi(-6, "fonte: prova corta")
    citata = bool(_CITAZIONE.search(doc) and _PROVATO.search(doc))
    if citata:
        aggiungi(+4, "fonte: articolo")
    if _PROFONDO.search(doc):
        aggiungi(+6, "fonte: teorema profondo")
    if _ENUNCIATO_DURO.search(p.statement):
        aggiungi(+5, "enunciato: infinito/analisi")
    if _POTENZA_GRANDE.search(p.statement):
        aggiungi(+4, "calcolo grande")
    if p.category == "textbook":
        aggiungi(-2, "textbook")
    if not (soggetti and soggetti <= ELEMENTARI):
        aggiungi(+1 if soggetti & ELEMENTARI else +3, "fuori da AMS 5/11")
    if locali or di_fcfm:
        aggiungi(0.5 * len(locali) + 1.0 * len(di_fcfm), "definizioni fuori Mathlib")
    if p.formal_proof_kind in ("lean4", "other_system"):
        aggiungi(+1, "prova gia' altrove")
    punti += len(p.statement) / 80
    return round(punti, 2), motivi


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mostra", type=int, default=30)
    ap.add_argument("--uscita", default=str(ROOT / "dati_ricerca" / "formalizzazioni_candidati.json"))
    args = ap.parse_args()

    idx = ProblemIndex.load()
    fcfm = nomi_formal_conjectures_for_mathlib()
    per_file: dict[Path, set[str]] = {}
    esclusi = collections.Counter()
    candidati = []

    for p in idx.problems:
        if p.category not in ("research solved", "textbook"):
            continue
        esclusi["0 solved+textbook in tutto"] += 1
        if p.formal_proof_kind == "formal_conjectures":
            esclusi["1 formal_proof using formal_conjectures"] += 1
            continue
        if "sorryAx" not in p.archive_proof_axioms:
            esclusi["2 dimostrazione gia' completa nell'archivio"] += 1
            continue
        if set(p.archive_proof_axioms) - AMMESSI - {"sorryAx"}:
            esclusi["3 dipende da native_decide o altri assiomi"] += 1
            continue
        try:
            corpo = corpo_dimostrazione(p)
        except Exception:
            esclusi["4 sorgente non leggibile dall'indice"] += 1
            continue
        if corpo is None or not re.fullmatch(r"(by\s+)?sorry", corpo):
            esclusi["5 prova scritta che dipende da un lemma con sorry"] += 1
            continue
        if p.statement_has_sorry or p.answer_placeholder_in_source:
            esclusi["6 enunciato con answer(sorry)"] += 1
            continue

        f = p.source_file
        if f not in per_file:
            per_file[f] = nomi_dichiarati(f.read_text(encoding="utf-8", errors="replace"))
        token = {t.split(".")[-1] for t in _IDENT.findall(p.statement)}
        locali = sorted(token & per_file[f])
        di_fcfm = sorted((token & fcfm) - set(locali))
        punteggio, motivi = valuta(p, locali, di_fcfm)
        candidati.append({
            "problema": p.theorem, "modulo": p.module, "categoria": p.category,
            "ams": sorted(p.subjects, key=lambda s: int(s) if s.isdigit() else 999),
            "lunghezza_enunciato": len(p.statement),
            "definizioni_locali": locali, "definizioni_fcfm": di_fcfm,
            "formal_proof": p.formal_proof_kind, "link": p.formal_proof_link,
            "punteggio": punteggio, "motivi": motivi,
            "enunciato": p.statement, "docstring": (p.docstring or "").strip(),
        })

    candidati.sort(key=lambda c: (c["punteggio"], c["problema"]))
    Path(args.uscita).write_text(json.dumps(candidati, ensure_ascii=False, indent=1),
                                 encoding="utf-8")

    print("FILTRI")
    for k in sorted(esclusi):
        print(f"  {k[2:]:52s} {esclusi[k]:5d}")
    print(f"  {'CANDIDATI':52s} {len(candidati):5d}")
    print("  per categoria:", dict(collections.Counter(c["categoria"] for c in candidati)))
    print("  con formal_proof altrove:", sum(1 for c in candidati if c["formal_proof"]))
    conta = collections.Counter(m for c in candidati for m in c["motivi"])
    print("  segnali:", dict(conta))
    print("  punteggio < 0 (la fonte indica una prova corta e niente di duro):",
          sum(1 for c in candidati if c["punteggio"] < 0))
    print()
    for i, c in enumerate(candidati[:args.mostra], 1):
        s = " ".join(c["enunciato"].split())
        print(f"{i:3d} {c['punteggio']:6.1f} {'tb' if c['categoria'] == 'textbook' else 'rs'} "
              f"AMS {' '.join(c['ams'])}  {c['problema']}")
        print(f"        {'; '.join(c['motivi']) or '-'}")
        print(f"        S: {s[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
