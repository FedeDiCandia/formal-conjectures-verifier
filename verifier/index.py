"""
Indice dei problemi dell'archivio.

Costruirlo richiede di caricare in memoria tutto l'archivio compilato, quindi
si fa UNA VOLTA e si salva in un file JSON. Da li' in poi la lettura e'
istantanea.

Uso da riga di comando:
    python3 verifier/index.py --build      # (ri)costruisce l'indice
    python3 verifier/index.py --stats      # statistiche sui problemi
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
    """Un teorema dell'archivio."""
    theorem: str                    # nome completo, es. "Erdos10.erdos_10"
    module: str                     # es. "FormalConjectures.ErdosProblems.10"
    category: str                   # "research open" | "research solved" | "textbook" | "test" | "API"
    subjects: list[str]             # classificazione AMS
    statement: str                  # enunciato come lo stampa Lean
    docstring: Optional[str]
    formal_proof_kind: Optional[str]
    formal_proof_link: Optional[str]
    proof_is_sorry_free: bool       # nell'archivio la dimostrazione e' gia' completa
    statement_has_sorry: bool       # l'ENUNCIATO ha un buco answer( ) non proposizionale
    range: Optional[dict]           # posizione nel file sorgente

    @property
    def source_file(self) -> Path:
        """Il file .lean che contiene questo teorema."""
        return config.ARCHIVE / (self.module.replace(".", "/") + ".lean")

    @property
    def is_already_solved_here(self) -> bool:
        """True se l'archivio contiene gia' una dimostrazione completa.
        Sono questi i problemi su cui ha senso collaudare il sistema."""
        return self.proof_is_sorry_free

    def source_text(self) -> str:
        """Il testo sorgente esatto della dichiarazione (attributi e docstring
        esclusi: parte dalla parola `theorem`)."""
        if not self.range:
            raise ValueError(f"posizione sorgente sconosciuta per {self.theorem}")
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
            raise KeyError(f"Problema '{theorem}' non trovato nell'indice.{hint}")
        return self._by_name[theorem]

    def find(self, *, category: Optional[str] = None, solved_here: Optional[bool] = None,
             has_answer_hole: Optional[bool] = None) -> list[Problem]:
        out = self.problems
        if category is not None:
            out = [p for p in out if p.category == category]
        if solved_here is not None:
            out = [p for p in out if p.is_already_solved_here == solved_here]
        if has_answer_hole is not None:
            out = [p for p in out if p.statement_has_sorry == has_answer_hole]
        return out

    @staticmethod
    def load(path: Path | None = None) -> "ProblemIndex":
        path = path or config.INDEX_FILE
        if not path.is_file():
            raise FileNotFoundError(
                f"Indice non trovato: {path}\n"
                f"Costruiscilo con: python3 verifier/index.py --build")
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProblemIndex([Problem.from_json(d) for d in data])


def build_index(output: Path | None = None) -> Path:
    """Esegue lo script Lean che estrae i metadati e salva il JSON."""
    output = output or config.INDEX_FILE
    script = Path(__file__).resolve().parent / "lean" / "extract_problems.lean"
    print(f"Estraggo i metadati dall'archivio (richiede qualche minuto)...", file=sys.stderr)
    proc = subprocess.run(
        [str(config.ELAN_BIN / "lake"), "env", "lean", "--run", str(script)],
        cwd=config.ARCHIVE, env=config.lean_env(),
        capture_output=True, text=True, timeout=3600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"estrazione fallita (codice {proc.returncode}):\n{proc.stderr[-4000:]}")
    data = json.loads(proc.stdout)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Indice scritto in {output}: {len(data)} teoremi.", file=sys.stderr)
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
    print(f"\nCon dimostrazione gia' completa nell'archivio: {len(solved)}")
    print(f"Con un buco answer( ) NON proposizionale nell'enunciato: {len(holes)}")
    print("\nEsempi di problemi gia' risolti e senza buchi (buoni per collaudare):")
    good = [p for p in solved if not p.statement_has_sorry
            and p.category in ("research solved", "textbook")]
    for p in good[:10]:
        print(f"  {p.theorem}   [{p.category}]   ({p.module})")
    print(f"  ... {len(good)} in totale")


if __name__ == "__main__":
    if "--build" in sys.argv:
        build_index()
    elif "--stats" in sys.argv:
        _stats()
    else:
        print(__doc__)
