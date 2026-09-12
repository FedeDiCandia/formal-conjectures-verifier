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
    archive_proof_axioms: list[str]  # assiomi usati dalla dimostrazione dell'archivio
    range: Optional[dict]           # posizione nel file sorgente

    @property
    def source_file(self) -> Path:
        """Il file .lean che contiene questo teorema.

        Le virgolette francesi vanno togliete: un identificatore Lean che comincia
        con una cifra si scrive fra guillemet — il modulo delle voci OEIS si chiama
        `FormalConjectures.OEIS.«109074»` — ma il file sul disco si chiama
        `109074.lean`. Senza questa riga nessuno dei 209 problemi OEIS era
        leggibile dal sorgente: l'agente non poteva riceverli, l'estrattore non
        poteva estrarli e la sfida negata non si poteva generare.
        """
        pezzi = self.module.replace("«", "").replace("»", "")
        return config.ARCHIVE / (pezzi.replace(".", "/") + ".lean")

    #: Gli unici assiomi che il verificatore ammette.
    ASSIOMI_AMMESSI = frozenset({"propext", "Classical.choice", "Quot.sound"})

    @property
    def proof_is_complete(self) -> bool:
        """True se l'archivio fornisce una dimostrazione senza buchi.

        Si guardano gli ASSIOMI, non il campo `proofIsSorryFree` riportato da
        Lean. Due ragioni:
          * gli assiomi sono TRANSITIVI: un teorema il cui termine di prova non
            contiene `sorry` ma che usa un lemma bucato risulta comunque
            dipendente da `sorryAx` (nel tag bench-v1 sono 17 casi);
          * da Lean 4.33 il corpo delle dimostrazioni importate non viene
            caricato subito, quindi `proofIsSorryFree` risulta sempre falso.
            Fidarsi di quel campo faceva contare ZERO problemi risolti su 5271.
        """
        return "sorryAx" not in self.archive_proof_axioms

    @property
    def archive_proof_is_clean(self) -> bool:
        """True se la dimostrazione fornita dall'archivio passerebbe il nostro
        verificatore.

        Non basta che esista: 95 dimostrazioni dell'archivio usano
        `decide +native`, che lascia l'assioma `Lean.ofReduceBool`, e noi lo
        rifiutiamo. Sono problemi "risolti" che il verificatore non accetta.
        """
        return bool(self.archive_proof_axioms) and \
            set(self.archive_proof_axioms) <= self.ASSIOMI_AMMESSI

    @property
    def archive_proof_forbidden_axioms(self) -> list[str]:
        return sorted(set(self.archive_proof_axioms) - self.ASSIOMI_AMMESSI)

    @property
    def answer_placeholder_in_source(self) -> bool:
        """True se il SORGENTE del teorema contiene `answer(sorry)`.

        Attenzione, e' diverso da `statement_has_sorry`. Quando la risposta e'
        una proposizione, l'opzione predefinita `google.answer = always_true`
        trasforma `answer(sorry)` in `True`, quindi l'enunciato elaborato NON
        contiene piu' alcun sorry ed e' perfettamente verificabile...

        ...ma vuol dire che la formalizzazione **da' per scontato che la
        risposta sia "si'"**: `answer(sorry) ↔ P` diventa `True ↔ P`, cioe'
        l'asserzione che P e' vera. Se la risposta corretta fosse "no", il
        teorema cosi' com'e' scritto sarebbe falso e nessuno potrebbe
        dimostrarlo onestamente; la soluzione richiederebbe di cambiare
        l'enunciato in `answer(False) ↔ P`, che il verificatore rifiuta
        (giustamente: e' un altro enunciato).

        Non e' un difetto del verificatore: e' una proprieta' del benchmark, e
        va detta a chi legge il risultato.
        """
        try:
            return "answer(sorry)" in self.source_text().replace(" ", "")
        except Exception:
            return False

    @property
    def is_already_solved_here(self) -> bool:
        """True se l'archivio contiene gia' una dimostrazione completa.
        Sono questi i problemi su cui ha senso collaudare il sistema."""
        return self.proof_is_complete

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
            raise KeyError(f"Problema '{theorem}' non trovato nell'indice.{hint}")
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
                f"Indice non trovato: {path}\n"
                f"Costruiscilo con: python3 verifier/index.py --build")
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProblemIndex([Problem.from_json(d) for d in data])


def build_index(output: Path | None = None) -> Path:
    """Esegue lo script Lean che estrae i metadati e salva il JSON."""
    output = output or config.INDEX_FILE
    # lo script giusto per questo archivio: le utilita' hanno cambiato posto
    # fra il tag bench-v1 e il ramo main
    cartella = Path(__file__).resolve().parent / "lean"
    script = (cartella / "extract_problems.lean"
              if config.modulo_utilita() == "FormalConjecturesUtil"
              else cartella / "extract_problems_bench.lean")
    print(f"Estraggo i metadati dall'archivio (richiede qualche minuto)...", file=sys.stderr)
    proc = subprocess.run(
        [str(config.ELAN_BIN / "lake"), "env", "lean", "--run", str(script)],
        cwd=config.ARCHIVE, env=config.lean_env(),
        capture_output=True, text=True, timeout=3600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"estrazione fallita (codice {proc.returncode}):\n{proc.stderr[-4000:]}")
    # Lean puo' stampare avvisi del linter PRIMA del JSON (nel ramo main il
    # linter dei docstring di modulo si lamenta anche degli script eseguiti con
    # `lean --run`). Si parte dalla prima parentesi quadra.
    uscita = proc.stdout
    inizio = uscita.find("[")
    if inizio < 0:
        raise RuntimeError(
            f"l'estrattore non ha prodotto JSON.\nstdout:\n{uscita[:2000]}\n"
            f"stderr:\n{proc.stderr[-2000:]}")
    data = json.loads(uscita[inizio:])
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
    puliti = idx.find(archive_proof_clean=True)
    print(f"\nCon dimostrazione gia' completa nell'archivio: {len(solved)}")
    print(f"  di cui accettabili dal nostro verificatore: {len(puliti)}")
    sporchi = [p for p in solved if not p.archive_proof_is_clean]
    if sporchi:
        from collections import Counter
        motivi = Counter(a for p in sporchi for a in p.archive_proof_forbidden_axioms)
        print(f"  le altre {len(sporchi)} usano assiomi non ammessi: "
              + ", ".join(f"{a} ({n})" for a, n in motivi.most_common()))
    print(f"Con un buco answer( ) NON proposizionale nell'enunciato: {len(holes)}")
    print("\nEsempi di problemi gia' risolti e senza buchi (buoni per collaudare):")
    good = [p for p in puliti if not p.statement_has_sorry
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
