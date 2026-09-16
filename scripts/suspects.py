"""
Turn the probe's flags into dossiers to be examined by hand.

**Nothing this script produces is a solution, and no flag is a faulty formalisation
until it has been compared with the original source.** The rule is in
`docs/04-finding-protocol.md`, section "The commonest case".

For each flag the dossier puts side by side:
  * the elaborated Lean statement, as the verifier sees it;
  * the source of the declaration in the archive, line by line;
  * the docstring, which is the text of the source (often an OEIS comment);
  * a checklist of translation defects already seen elsewhere, with the point in the
    source to look at for each.

Then it is a person's turn. The dossier exists to make that work fast, not to do it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verifier"))

import config as verifier_config   # noqa: E402
from index import ProblemIndex          # noqa: E402

#: The known ways a Lean translation says less than it appears to.
#: Each carries: how to recognise it in the source, and why it makes the statement
#: weaker or vacuous. The first two come from Epoch AI's files, the others are
#: classic defects of formalisation in Lean.
KNOWN_SUSPECTS = [
    ("testimone vacuo (`C = 0`, insieme vuoto)",
     r"∃\s*[A-Za-z]",
     "a leading `∃` can be satisfied by zero or by the empty set: check whether the "
     "statement requires the witness to be non-trivial. This is A211420's case in "
     "Epoch's results: \"there exists C such that ... divides C * a(n)\" is true with "
     "C = 0, because everything divides zero."),
    ("caso al bordo (n = 0, n = 1)",
     r"∀\s*\(?[a-z]+\s*:\s*ℕ\)?",
     "a `∀ n : ℕ` includes n = 0 and n = 1, where the definitions often degenerate. "
     "Check whether the source says \"for every n\" or \"for every n ≥ 2\". This is "
     "A262403: injectivity fails because two values are both 0."),
    ("sottrazione troncata di ℕ",
     r"-\s*\d|\w\s*-\s*\w",
     "in ℕ subtraction does not go below zero: `k - 1` with k = 0 gives 0, not -1. "
     "If the source speaks of integers, the translation changes its meaning."),
    ("`sInf`/`sSup` su insieme vuoto",
     r"sInf|sSup|Finset\.sup|Finset\.inf",
     "`sInf ∅ = 0` and `Finset.sup ∅ = 0` in ℕ: a statement saying \"the minimum is "
     "0\" can be true because the set is empty, not because the minimum is 0."),
    ("divisione intera",
     r"/\s*\d|\w\s*/\s*\w",
     "in ℕ and ℤ division truncates: `7 / 2 = 3`. If the source speaks of rationals "
     "l'statement è diverso."),
    ("`answer(sorry)` in the source",
     r"answer\s*\(",
     "with the default option the `answer( )` elaborator makes `answer(sorry)` equal "
     "to `True`: the statement asserts that the answer to the question is \"yes\". If "
     "the source poses an open question, the direction has already been chosen."),
]


def fascicolo(p, entry: dict) -> str:
    r = []
    def s(x=""): r.append(x)
    s(f"# Sospetto: `{p.theorem}`")
    s()
    s("> **This is not a result.** A trivial tactic closed an open statement,")
    s("> and the explanation is nearly always that the Lean statement does not say")
    s("> what the source says. It has to be compared with the source before")
    s("> chiamarlo in qualunque way. Vedi `docs/04-protocollo-ritrovamenti.md`.")
    s()
    s(f"**Categoria nell'archive:** {p.category}  ")
    s(f"**Modulo:** `{p.module}`  ")
    s(f"**What gave way:** {entry.get('ATTENTION', '—')}")
    s()
    s("## The statement, as the verifier sees it")
    s()
    s("```")
    s(p.statement)
    s("```")
    s()
    s("## The text of the source (the archive's docstring)")
    s()
    s((p.docstring or "(no docstring)").strip())
    s()
    s("## The source of the declaration")
    s()
    s("```lean")
    try:
        text = p.source_text()
    except Exception as e:
        text = f"(source not readable: {e})"
    s(text.rstrip())
    s("```")
    s()
    s("## Checklist: the known ways a translation loses the meaning")
    s()
    for name, reason, explanation in KNOWN_SUSPECTS:
        present = bool(re.search(reason, p.statement)) or bool(re.search(reason, text))
        s(f"- [{'x' if present else ' '}] **{name}**"
          f"{' — appears in this statement' if present else ''}  ")
        s(f"      {explanation}")
    s()
    s("## Messaggi di Lean, grezzi")
    s()
    s("```")
    s((entry.get("raw_messages") or "(not kept)")[:3000])
    s("```")
    s()
    s("## What to do, in order")
    s()
    s("1. read the original source (OEIS, paper, website) and write down here the")
    s("   precise point at which the translation departs from it;")
    s("2. if it does depart: prepare a draft report for the archive's authors,")
    s("   **without publishing it**;")
    s("3. if it does NOT: this is a case to understand better, and to be treated with")
    s("   even more suspicion — an open problem that falls to `simp` with a faithful")
    s("   formalisation would be news, and news here is")
    s("   nearly always our own errors.")
    s()
    return "\n".join(r) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=str(ROOT / "runs/hunt/artefacts.json"))
    ap.add_argument("--folder", default=str(ROOT / "runs/sospetti"))
    args = ap.parse_args()

    f = Path(args.probe)
    if not f.is_file():
        print(f"no probe results in {f}")
        return 0
    data = json.loads(f.read_text(encoding="utf-8"))
    notable = [v for v in data if "ATTENZIONE" in v]
    print(f"sondati {len(data)} problems, segnalazioni {len(notable)}")
    if not notable:
        print("\nNo flags. That is the likeliest outcome and should be read for what")
        print("it is: the archive's formalisations hold against the trivial tactics.")
        return 0

    idx = ProblemIndex.load()
    dest = Path(args.folder)
    dest.mkdir(parents=True, exist_ok=True)
    for v in notable:
        try:
            p = idx.get(v["problem"])
        except Exception as e:
            print(f"  {v['problem']}: not found in the index ({e})")
            continue
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", v["problem"])[:80]
        (dest / f"{name}.md").write_text(fascicolo(p, v), encoding="utf-8")
        print(f"  fascicolo: {dest / (name + '.md')}")
    print(f"\n{len(notable)} dossiers. None of them is a solution: they have to be read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
