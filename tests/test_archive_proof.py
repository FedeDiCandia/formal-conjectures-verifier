"""L'estrattore delle dimostrazioni d'archivio: i confini dei blocchi.

Sono test di solo testo: non fanno partire Lean, durano millisecondi.
Servono a fissare i difetti trovati provando davvero, uno per uno.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier"))
import archive_proof as pa


# --- le parole di struttura si confrontano intere --------------------------

def test_una_parola_inglese_che_comincia_per_end_non_apre_un_blocco():
    """Il difetto vero: "endomorphism ... -/" veniva letto come `end`."""
    assert not pa._apre_struttura("endomorphism of a finite set is surjective. -/")
    assert not pa._apre_struttura("elaborated by hand -/")
    assert not pa._apre_struttura("importante: vedi sotto -/")
    assert not pa._apre_struttura("opening remarks -/")
    assert not pa._apre_struttura("sections of a bundle -/")


def test_le_parole_di_struttura_vere_aprono_un_blocco():
    for riga in ("end GottschalkSurjunctivity", "namespace Foo", "section",
                 "open Nat in", "variable (G : Type*)", "import Mathlib",
                 "set_option linter.style.longLine false", "#check @Nat.floor",
                 "/-!# Titolo", "attribute [simp] foo", "notation3\"∑ \"x => x"):
        assert pa._apre_struttura(riga), riga


def test_una_riga_indentata_non_apre_niente():
    assert not pa._apre_struttura("  end Foo")
    assert not pa._apre_dichiarazione("  theorem t : True := trivial")


# --- i confini dei blocchi ------------------------------------------------

_FILE = """import FormalConjectures.Util.ProblemImports

namespace Prova

/-- Prima congettura, ancora aperta.
Questa riga finisce il docstring. -/
@[category research open, AMS 11]
theorem aperta : True := by
  sorry

/-- Every finite group is surjunctive. This is a classical result: an injective
endomorphism of a finite set is surjective. -/
@[category textbook, AMS 20 37]
theorem bersaglio : True := by
  trivial

end Prova
"""


def test_il_docstring_su_due_righe_resta_attaccato_al_suo_teorema():
    righe = _FILE.split("\n")
    blocchi = pa._blocchi(righe)
    # il blocco che contiene il bersaglio deve contenere TUTTO il suo docstring
    for a, b in blocchi:
        testo = "\n".join(righe[a:b + 1])
        if pa._nome_dichiarato(testo) == "bersaglio":
            assert "Every finite group is surjunctive" in testo, (
                f"il docstring e' rimasto fuori dal blocco:\n{testo}")
            assert "endomorphism of a finite set" in testo
            break
    else:
        raise AssertionError("blocco del bersaglio non trovato")


def test_nessun_blocco_e_solo_la_coda_di_un_docstring():
    righe = _FILE.split("\n")
    for a, b in pa._blocchi(righe):
        testo = "\n".join(righe[a:b + 1]).strip()
        if testo.endswith("-/") and "/-" not in testo:
            raise AssertionError(f"blocco penzolante: {testo!r}")
