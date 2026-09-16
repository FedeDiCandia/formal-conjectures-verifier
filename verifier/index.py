"""
Index of the archive's problems.

Building it means loading the whole compiled archive into memory, so it is done
ONCE and saved to a JSON file. From then on reading it is instantaneous.

Command line:
    python3 verifier/index.py --build      # (re)build the index
    python3 verifier/index.py --stats      # statistics about the problems
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
    """One theorem of the archive."""
    theorem: str                    # full name, e.g. "Erdos10.erdos_10"
    module: str                     # e.g. "FormalConjectures.ErdosProblems.10"
    category: str                   # "research open" | "research solved" | "textbook" | "test" | "API"
    subjects: list[str]             # AMS classification
    statement: str                  # the statement as Lean prints it
    docstring: Optional[str]
    formal_proof_kind: Optional[str]
    formal_proof_link: Optional[str]
    proof_is_sorry_free: bool       # the archive's proof is already complete
    statement_has_sorry: bool       # the STATEMENT has a non-propositional answer( ) hole
    archive_proof_axioms: list[str]  # axioms the archive's proof depends on
    range: Optional[dict]           # position in the source file

    @property
    def source_file(self) -> Path:
        """The .lean file that contains this theorem.

        The guillemets have to be stripped: a Lean identifier that begins with a
        digit is written between guillemets — the module of the OEIS entries is
        called `FormalConjectures.OEIS.«109074»` — but the file on disk is called
        `109074.lean`. Without this line none of the 209 OEIS problems could be
        read from source: the agent could not receive them, the extractor could
        not extract them, and the negated challenge could not be generated.
        """
        pieces = self.module.replace("«", "").replace("»", "")
        return config.ARCHIVE / (pieces.replace(".", "/") + ".lean")

    #: The only axioms the verifier permits.
    PERMITTED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

    @property
    def proof_is_complete(self) -> bool:
        """True if the archive supplies a proof with no holes.

        It looks at the AXIOMS, not at the `proofIsSorryFree` field Lean reports.
        Two reasons:
          * axioms are TRANSITIVE: a theorem whose proof term contains no `sorry`
            but which uses a lemma that does still comes out depending on
            `sorryAx` (17 cases in the bench-v1 tag);
          * since Lean 4.33 the bodies of imported proofs are not loaded eagerly,
            so `proofIsSorryFree` always comes out false. Trusting that field
            made the count of solved problems ZERO out of 5271.
        """
        return "sorryAx" not in self.archive_proof_axioms

    @property
    def archive_proof_is_clean(self) -> bool:
        """True if the proof the archive supplies would pass our verifier.

        Its existence is not enough: 95 of the archive's proofs use
        `decide +native`, which leaves the axiom `Lean.ofReduceBool`, and that is
        rejected here. They are "solved" problems the verifier does not accept.
        """
        return bool(self.archive_proof_axioms) and \
            set(self.archive_proof_axioms) <= self.PERMITTED_AXIOMS

    @property
    def archive_proof_forbidden_axioms(self) -> list[str]:
        return sorted(set(self.archive_proof_axioms) - self.PERMITTED_AXIOMS)

    @property
    def answer_placeholder_in_source(self) -> bool:
        """True if the theorem's SOURCE contains `answer(sorry)`.

        Note that this differs from `statement_has_sorry`. When the answer is a
        proposition, the default option `google.answer = always_true` turns
        `answer(sorry)` into `True`, so the elaborated statement contains no
        sorry at all and is perfectly verifiable…

        …but it means the formalisation **takes for granted that the answer is
        "yes"**: `answer(sorry) ↔ P` becomes `True ↔ P`, the assertion that P is
        true. If the right answer were "no", the theorem as written would be
        false and nobody could prove it honestly; the solution would require
        changing the statement to `answer(False) ↔ P`, which the verifier rejects
        (rightly: it is a different statement).

        This is not a finding about the verifier: it is a property of the
        benchmark, and it has to be said to whoever reads the result.
        """
        try:
            return "answer(sorry)" in self.source_text().replace(" ", "")
        except Exception:
            return False

    @property
    def is_already_solved_here(self) -> bool:
        """True if the archive already contains a complete proof.
        These are the problems worth exercising the system on."""
        return self.proof_is_complete

    def source_text(self) -> str:
        """The exact source text of the declaration (attributes and docstring
        excluded: it starts at the word `theorem`)."""
        if not self.range:
            raise ValueError(f"source position unknown for {self.theorem}")
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
            hint = f" Did you mean: {', '.join(close)}" if close else ""
            raise KeyError(f"Problem '{theorem}' not found in the index.{hint}")
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
                f"Index not found: {path}\n"
                f"Build it with: python3 verifier/index.py --build")
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProblemIndex([Problem.from_json(d) for d in data])


def build_index(output: Path | None = None) -> Path:
    """Run the Lean script that extracts the metadata, and save the JSON."""
    output = output or config.INDEX_FILE
    # the right script for this archive: the utilities moved between the
    # bench-v1 tag and the main branch
    folder = Path(__file__).resolve().parent / "lean"
    script = (folder / "extract_problems.lean"
              if config.utility_module() == "FormalConjecturesUtil"
              else folder / "extract_problems_bench.lean")
    print("Extracting the metadata from the archive (this takes a few minutes)...", file=sys.stderr)
    proc = subprocess.run(
        [str(config.ELAN_BIN / "lake"), "env", "lean", "--run", str(script)],
        cwd=config.ARCHIVE, env=config.lean_env(),
        capture_output=True, text=True, timeout=3600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"extraction failed (code {proc.returncode}):\n{proc.stderr[-4000:]}")
    # Lean may print linter warnings BEFORE the JSON (on the main branch the
    # module-docstring linter complains about scripts run with `lean --run` too).
    # So we start from the first square bracket.
    stdout_text = proc.stdout
    start = stdout_text.find("[")
    if start < 0:
        raise RuntimeError(
            f"the extractor produced no JSON.\nstdout:\n{stdout_text[:2000]}\n"
            f"stderr:\n{proc.stderr[-2000:]}")
    data = json.loads(stdout_text[start:])
    output.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Index written to {output}: {len(data)} theorems.", file=sys.stderr)
    return output


def _stats() -> None:
    idx = ProblemIndex.load()
    print(f"Theorems carrying a `category` attribute: {len(idx)}\n")
    print("By category:")
    cats: dict[str, int] = {}
    for p in idx.problems:
        cats[p.category] = cats.get(p.category, 0) + 1
    for c, n in sorted(cats.items(), key=lambda kv: -kv[1]):
        print(f"  {n:5d}  {c}")
    solved = idx.find(solved_here=True)
    holes = idx.find(has_answer_hole=True)
    clean_list = idx.find(archive_proof_clean=True)
    print(f"\nWith a complete proof already in the archive: {len(solved)}")
    print(f"  of which acceptable to our verifier: {len(clean_list)}")
    dirty = [p for p in solved if not p.archive_proof_is_clean]
    if dirty:
        from collections import Counter
        reasons = Counter(a for p in dirty for a in p.archive_proof_forbidden_axioms)
        print(f"  the other {len(dirty)} use axioms that are not permitted: "
              + ", ".join(f"{a} ({n})" for a, n in reasons.most_common()))
    print(f"With a NON-propositional answer( ) hole in the statement: {len(holes)}")
    print("\nExamples of problems already solved and hole-free (good for exercising):")
    good = [p for p in clean_list if not p.statement_has_sorry
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
