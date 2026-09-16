"""
Indice dei problems dell'archive.

Costruirlo richiede di caricare in memoria tutto l'archive compilato, quindi
si fa UNA VOLTA e si salva in un file JSON. Da li' in poi la lettura e'
istantanea.

Uso da line di command:
    python3 verifier/index.py --build      # (ri)costruisce l'index
    python3 verifier/index.py --stats      # statistiche sui problems
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config


@dataclass
class Problem:
    """Un theorem_ dell'archive."""
    theorem: str                    # name full_, es. "Erdos10.erdos_10"
    module: str                     # es. "FormalConjectures.ErdosProblems.10"
    category: str                   # "research open" | "research solved" | "textbook" | "test" | "API"
    subjects: list[str]             # classificazione AMS
    statement: str                  # statement come lo show Lean
    docstring: Optional[str]
    formal_proof_kind: Optional[str]
    formal_proof_link: Optional[str]
    proof_is_sorry_free: bool       # nell'archive la dimostrazione e' gia' complete_
    statement_has_sorry: bool       # l'ENUNCIATO ha un buco answer( ) non proposizionale
    archive_proof_axioms: list[str]  # axioms usati dalla dimostrazione dell'archive
    range: Optional[dict]           # position nel file source_text

    @property
    def source_file(self) -> Path:
        """Il file .lean che contiene questo theorem_.

        Le virgolette francesi vanno togliete: un identificatore Lean che comincia
        con one_ cifra si scrive fra guillemet — il module delle entries OEIS si chiama
        `FormalConjectures.OEIS.«109074»` — ma il file sul disco si chiama
        `109074.lean`. Senza questa line nessuno dei 209 problems OEIS era
        leggibile dal source_text: l'agent non poteva riceverli, l'estrattore non
        poteva estrarli e la challenge negata non si poteva generare.
        """
        pieces = self.module.replace("«", "").replace("»", "")
        return config.ARCHIVE / (pieces.replace(".", "/") + ".lean")

    #: Gli unique_ axioms che il verifier ammette.
    PERMITTED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

    @property
    def proof_is_complete(self) -> bool:
        """True se l'archive fornisce one_ dimostrazione senza buchi.

        Si guardano gli ASSIOMI, non il field_ `proofIsSorryFree` riportato da
        Lean. Due ragioni:
          * gli axioms sono TRANSITIVI: un theorem_ il cui termine di trial non
            contiene `sorry` ma che usa un lemma bucato risulta comunque
            dipendente da `sorryAx` (nel tag bench-v1 sono 17 cases);
          * da Lean 4.33 il body delle dimostrazioni importate non viene
            caricato subito, quindi `proofIsSorryFree` risulta sempre falso.
            Fidarsi di quel field_ faceva contare ZERO problems solved_ su 5271.
        """
        return "sorryAx" not in self.archive_proof_axioms

    @property
    def archive_proof_is_clean(self) -> bool:
        """True se la dimostrazione fornita dall'archive passerebbe il nostro
        verifier.

        Non basta che esista: 95 dimostrazioni dell'archive usano
        `decide +native`, che lascia l'assioma `Lean.ofReduceBool`, e noi lo
        rifiutiamo. Sono problems "solved_" che il verifier non accetta.
        """
        return bool(self.archive_proof_axioms) and \
            set(self.archive_proof_axioms) <= self.PERMITTED_AXIOMS

    @property
    def archive_proof_forbidden_axioms(self) -> list[str]:
        return sorted(set(self.archive_proof_axioms) - self.PERMITTED_AXIOMS)

    @property
    def answer_placeholder_in_source(self) -> bool:
        """True se il SORGENTE del theorem_ contiene `answer(sorry)`.

        Attenzione, e' diverso da `statement_has_sorry`. Quando la answer e'
        one_ proposizione, l'opzione predefinita `google.answer = always_true`
        trasforma `answer(sorry)` in `True`, quindi l'statement elaborato NON
        contiene piu' alcun sorry ed e' perfettamente verificabile...

        ...ma vuol dire che la formalizzazione **da' per scontato che la
        answer sia "si'"**: `answer(sorry) ↔ P` diventa `True ↔ P`, cioe'
        l'asserzione che P e' vera. Se la answer corretta fosse "no", il
        theorem_ cosi' com'e' scritto sarebbe falso e nessuno potrebbe
        dimostrarlo onestamente; la solution richiederebbe di cambiare
        l'statement in `answer(False) ↔ P`, che il verifier rifiuta
        (giustamente: e' un other statement).

        Non e' un finding del verifier: e' one_ proprieta' del benchmark, e
        va detta a chi legge il result_value.
        """
        try:
            return "answer(sorry)" in self.source_text().replace(" ", "")
        except Exception:
            return False

    @property
    def is_already_solved_here(self) -> bool:
        """True se l'archive contiene gia' one_ dimostrazione complete_.
        Sono questi i problems su cui ha senso collaudare il system."""
        return self.proof_is_complete

    def source_text(self) -> str:
        """Il text source_text exact della declaration (attributi e docstring
        excluded: parte dalla word `theorem`)."""
        if not self.range:
            raise ValueError(f"position source_text sconosciuta per {self.theorem}")
        lines = self.source_file.read_text(encoding="utf-8").split("\n")
        r = self.range
        chunk = lines[r["startLine"] - 1: r["endLine"]]
        if not chunk:
            return ""
        chunk[-1] = chunk[-1][: r["endCol"]]
        chunk[0] = chunk[0][r["startCol"]:]
        return "\n".join(chunk)

    @staticmethod
    def from_json(d: dict) -> "Problem":
        return Problem(
            theorem=d["theorem"], module=d["module"], category=d["category"],
            subjects=d.get("subjects") or [], statement=d["statement"],
            docstring=d.get("docstring"),
            formal_proof_kind=d.get("formalProofKind"),
            formal_proof_link=d.get("formalProofLink"),
            proof_is_sorry_free=bool(d.get("proofIsSorryFree")),
            statement_has_sorry=bool(d.get("statementHasSorry")),
            archive_proof_axioms=d.get("archiveProofAxioms") or [],
            range=d.get("range"),
        )


class ProblemIndex:
    def __init__(self, problems: list[Problem]):
        self.problems = problems
        self._by_name = {p.theorem: p for p in problems}

    def __len__(self) -> int:
        return len(self.problems)

    def get(self, theorem: str) -> Problem:
        if theorem not in self._by_name:
            close = [n for n in self._by_name if theorem.lower() in n.lower()][:5]
            hint = f" Forse intendevi: {', '.join(close)}" if close else ""
            raise KeyError(f"Problema '{theorem}' non found nell'index.{hint}")
        return self._by_name[theorem]

    def find(self, *, category: Optional[str] = None, solved_here: Optional[bool] = None,
             has_answer_hole: Optional[bool] = None,
             archive_proof_clean: Optional[bool] = None) -> list[Problem]:
        out = self.problems
        if category is not None:
            out = [p for p in out if p.category == category]
        if solved_here is not None:
            out = [p for p in out if p.is_already_solved_here == solved_here]
        if has_answer_hole is not None:
            out = [p for p in out if p.statement_has_sorry == has_answer_hole]
        if archive_proof_clean is not None:
            out = [p for p in out if p.archive_proof_is_clean == archive_proof_clean]
        return out

    @staticmethod
    def load(path: Path | None = None) -> "ProblemIndex":
        path = path or config.INDEX_FILE
        if not path.is_file():
            raise FileNotFoundError(
                f"Indice non found: {path}\n"
                f"Costruiscilo con: python3 verifier/index.py --build")
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProblemIndex([Problem.from_json(d) for d in data])


def build_index(output: Path | None = None) -> Path:
    """Esegue lo script Lean che estrae i metadati e salva il JSON."""
    output = output or config.INDEX_FILE
    # lo script giusto per questo archive: le utility' hanno cambiato slot_
    # fra il tag bench-v1 e il branch main
    folder = Path(__file__).resolve().parent / "lean"
    script = (folder / "extract_problems.lean"
              if config.utility_module() == "FormalConjecturesUtil"
              else folder / "extract_problems_bench.lean")
    print(f"Estraggo i metadati dall'archive (richiede qualche minuto)...", file=sys.stderr)
    proc = subprocess.run(
        [str(config.ELAN_BIN / "lake"), "env", "lean", "--run", str(script)],
        cwd=config.ARCHIVE, env=config.lean_env(),
        capture_output=True, text=True, timeout=3600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"estrazione fallita (code {proc.returncode}):\n{proc.stderr[-4000:]}")
    # Lean puo' stampare avvisi del linter PRIMA del JSON (nel branch main il
    # linter dei docstring di module si lamenta also_ degli script eseguiti con
    # `lean --run`). Si parte dalla before parentesi quadra.
    output = proc.stdout
    start = output.find("[")
    if start < 0:
        raise RuntimeError(
            f"l'estrattore non ha prodotto JSON.\nstdout:\n{output[:2000]}\n"
            f"stderr:\n{proc.stderr[-2000:]}")
    data = json.loads(output[start:])
    output.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Indice scritto in {output}: {len(data)} theorems.", file=sys.stderr)
    return output


def _stats() -> None:
    idx = ProblemIndex.load()
    print(f"Teoremi totali con attributo `category`: {len(idx)}\n")
    print("Per categoria:")
    cats: dict[str, int] = {}
    for p in idx.problems:
        cats[p.category] = cats.get(p.category, 0) + 1
    for c, n in sorted(cats.items(), key=lambda kv: -kv[1]):
        print(f"  {n:5d}  {c}")
    solved = idx.find(solved_here=True)
    holes = idx.find(has_answer_hole=True)
    clean_ones = idx.find(archive_proof_clean=True)
    print(f"\nCon dimostrazione gia' complete_ nell'archive: {len(solved)}")
    print(f"  di cui accettabili dal nostro verifier: {len(clean_ones)}")
    dirty = [p for p in solved if not p.archive_proof_is_clean]
    if dirty:
        from collections import Counter
        reasons = Counter(a for p in dirty for a in p.archive_proof_forbidden_axioms)
        print(f"  le others {len(dirty)} usano axioms non permitted: "
              + ", ".join(f"{a} ({n})" for a, n in reasons.most_common()))
    print(f"Con un buco answer( ) NON proposizionale nell'statement: {len(holes)}")
    print("\nEsempi di problems gia' solved_ e senza buchi (buoni per collaudare):")
    good = [p for p in clean_ones if not p.statement_has_sorry
            and p.category in ("research solved", "textbook")]
    for p in good[:10]:
        print(f"  {p.theorem}   [{p.category}]   ({p.module})")
    print(f"  ... {len(good)} in total")


if __name__ == "__main__":
    if "--build" in sys.argv:
        build_index()
    elif "--stats" in sys.argv:
        _stats()
    else:
        print(__doc__)
