"""The archive-proof extractor: where the blocks begin and end.

These are text-only tests: they do not start Lean and take milliseconds. They pin
down the defects that were found by trying, one at a time.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
import archive_proof as pa


# --- structural words are matched as whole words -------------------------

def test_a_word_beginning_with_end_does_not_open_a_block():
    """The real defect: "endomorphism ... -/" was read as an `end`."""
    assert not pa._opens_structure("endomorphism of a finite set is surjective. -/")
    assert not pa._opens_structure("elaborated by hand -/")
    assert not pa._opens_structure("important: see below -/")
    assert not pa._opens_structure("opening remarks -/")
    assert not pa._opens_structure("sections of a bundle -/")


def test_the_real_structural_words_do_open_a_block():
    for line in ("end GottschalkSurjunctivity", "namespace Foo", "section",
                 "open Nat in", "variable (G : Type*)", "import Mathlib",
                 "set_option linter.style.longLine false", "#check @Nat.floor",
                 "/-!# Title", "attribute [simp] foo", "notation3\"∑ \"x => x"):
        assert pa._opens_structure(line), line


def test_an_indented_line_opens_nothing():
    assert not pa._opens_structure("  end Foo")
    assert not pa._opens_declaration("  theorem t : True := trivial")


# --- the blocks' bounds --------------------------------------------------

_FILE = """import FormalConjectures.Util.ProblemImports

namespace Trial

/-- First conjecture, still open.
This line ends the docstring. -/
@[category research open, AMS 11]
theorem still_open : True := by
  sorry

/-- Every finite group is surjunctive. This is a classical result: an injective
endomorphism of a finite set is surjective. -/
@[category textbook, AMS 20 37]
theorem target : True := by
  trivial

end Trial
"""


def test_a_two_line_docstring_stays_attached_to_its_theorem():
    lines = _FILE.split("\n")
    blocks = pa._blocks(lines)
    # the block holding the target has to hold ALL of its docstring
    for a, b in blocks:
        text = "\n".join(lines[a:b + 1])
        if pa._declared_name(text) == "target":
            assert "Every finite group is surjunctive" in text, (
                f"the docstring was left outside the block:\n{text}")
            assert "endomorphism of a finite set" in text
            break
    else:
        raise AssertionError("the target's block was not found")


def test_no_block_is_only_the_tail_of_a_docstring():
    lines = _FILE.split("\n")
    for a, b in pa._blocks(lines):
        text = "\n".join(lines[a:b + 1]).strip()
        if text.endswith("-/") and "/-" not in text:
            raise AssertionError(f"dangling block: {text!r}")
