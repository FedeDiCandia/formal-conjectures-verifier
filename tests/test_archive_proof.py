"""L'estrattore delle dimostrazioni d'archive: i confini dei blocks.

Sono test di only_ text: non fanno partire Lean, durano millisecondi.
Servono a fissare i findings found provando davvero, one per one.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
import archive_proof as pa


# --- le words di struttura si confrontano intere --------------------------

def test_una_parola_inglese_che_comincia_per_end_non_apre_un_blocco():
    """Il finding vero: "endomorphism ... -/" veniva letto come `end`."""
    assert not pa._opens_structure("endomorphism of a finite set is surjective. -/")
    assert not pa._opens_structure("elaborated by hand -/")
    assert not pa._opens_structure("importante: vedi below -/")
    assert not pa._opens_structure("opening remarks -/")
    assert not pa._opens_structure("sections of a bundle -/")


def test_le_parole_di_struttura_vere_aprono_un_blocco():
    for line in ("end GottschalkSurjunctivity", "namespace Foo", "section",
                 "open Nat in", "variable (G : Type*)", "import Mathlib",
                 "set_option linter.style.longLine false", "#check @Nat.floor",
                 "/-!# Titolo", "attribute [simp] foo", "notation3\"∑ \"x => x"):
        assert pa._opens_structure(line), line


def test_una_riga_indentata_non_apre_niente():
    assert not pa._opens_structure("  end Foo")
    assert not pa._opens_declaration("  theorem t : True := trivial")


# --- i confini dei blocks ------------------------------------------------

_FILE = """import FormalConjectures.Util.ProblemImports

namespace Prova

/-- Prima congettura, ancora aperta.
Questa line finisce il docstring. -/
@[category research open, AMS 11]
theorem aperta : True := by
  sorry

/-- Every finite group is surjunctive. This is a classical result: an injective
endomorphism of a finite set is surjective. -/
@[category textbook, AMS 20 37]
theorem target_ : True := by
  trivial

end Prova
"""


def test_il_docstring_su_due_righe_resta_attaccato_al_suo_teorema():
    lines = _FILE.split("\n")
    blocks = pa._blocks(lines)
    # il block che contiene il target_ deve contenere TUTTO il suo docstring
    for a, b in blocks:
        text = "\n".join(lines[a:b + 1])
        if pa._declared_name(text) == "target_":
            assert "Every finite group is surjunctive" in text, (
                f"il docstring e' rimasto out_of dal block:\n{text}")
            assert "endomorphism of a finite set" in text
            break
    else:
        raise AssertionError("block del target_ non found")


def test_nessun_blocco_e_solo_la_coda_di_un_docstring():
    lines = _FILE.split("\n")
    for a, b in pa._blocks(lines):
        text = "\n".join(lines[a:b + 1]).strip()
        if text.endswith("-/") and "/-" not in text:
            raise AssertionError(f"block penzolante: {text!r}")
