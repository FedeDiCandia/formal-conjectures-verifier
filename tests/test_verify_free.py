"""verify_libera: la verifica di teoremi che NON stanno nell'archivio.

Il caso d'uso che l'ha fatto nascere e' A105020 ⟺ Goldbach (ricerca/lean/). Qui si
controlla che il nuovo ingresso del verificatore abbia gli stessi denti di `verify`:

  * accetta una dimostrazione giusta di un enunciato della sfida;
  * rifiuta un enunciato DIVERSO dichiarato con lo stesso nome;
  * rifiuta chi si appoggia alla dimostrazione `sorry` di un problema aperto
    dell'archivio importato — e' la ragione per cui importare moduli dell'archivio
    non e' una scappatoia;
  * rifiuta `sorry` nel candidato, assiomi nella sfida, teoremi mancanti nella sfida.
"""
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "verifier"))

import config                                                    # noqa: E402
import guard                                                     # noqa: E402
from verify import ACCEPTED, ERROR, REJECTED, verify_libera      # noqa: E402

MODULO = "FormalConjectures.Wikipedia.PerfectNumbers"

SFIDA_BUONA = f"""import {MODULO}

namespace ProvaLibera

theorem somma (n : ℕ) : n + 0 = n := by
  sorry

end ProvaLibera
"""

SFIDA_APERTA = f"""import {MODULO}

namespace ProvaLibera

theorem dispari_perfetto (n : ℕ) (hn : Nat.Perfect n) : Even n := by
  sorry

end ProvaLibera
"""


def setup_module(module):
    if config.check_installation():
        pytest.skip("ambiente non installato", allow_module_level=True)


def _file(tmp_path, nome, testo):
    f = tmp_path / nome
    f.write_text(testo, encoding="utf-8")
    return f


# --- senza Lean ---------------------------------------------------------------

def test_il_guard_ammette_i_moduli_elencati_e_nessun_altro():
    uno = "import FormalConjectures.Wikipedia.PerfectNumbers\ntheorem t : True := trivial\n"
    due = "import FormalConjectures.Wikipedia.JugglerConjecture\ntheorem t : True := trivial\n"
    tre = "import FormalConjectures.Wikipedia.Lemoine\ntheorem t : True := trivial\n"
    permessi = ("FormalConjectures.Wikipedia.PerfectNumbers",
                "FormalConjectures.Wikipedia.JugglerConjecture")
    assert guard.check_source(uno, modulo_permesso=permessi).ok
    assert guard.check_source(due, modulo_permesso=permessi).ok
    assert not guard.check_source(tre, modulo_permesso=permessi).ok
    # la forma a stringa singola resta valida
    assert guard.check_source(uno, modulo_permesso=permessi[0]).ok
    assert not guard.check_source(due, modulo_permesso=permessi[0]).ok


def test_una_sfida_che_dichiara_un_assioma_e_un_errore(tmp_path):
    cand = _file(tmp_path, "c.lean", "theorem ProvaLibera.somma (n : ℕ) : n + 0 = n := rfl\n")
    sfida = "axiom trucco : False\ntheorem ProvaLibera.somma (n : ℕ) : n + 0 = n := by\n  sorry\n"
    r = verify_libera(sfida, cand, ["ProvaLibera.somma"])
    assert r.status == ERROR and "assioma" in r.message


def test_un_teorema_non_dichiarato_nella_sfida_e_un_errore(tmp_path):
    cand = _file(tmp_path, "c.lean", "theorem ProvaLibera.somma (n : ℕ) : n + 0 = n := rfl\n")
    r = verify_libera(SFIDA_BUONA, cand, ["ProvaLibera.somma", "ProvaLibera.inesistente"])
    assert r.status == ERROR and "inesistente" in r.message


def test_un_candidato_con_sorry_e_rifiutato(tmp_path):
    cand = _file(tmp_path, "c.lean",
                 f"import {MODULO}\nnamespace ProvaLibera\n"
                 "theorem somma (n : ℕ) : n + 0 = n := by\n  sorry\nend ProvaLibera\n")
    r = verify_libera(SFIDA_BUONA, cand, ["ProvaLibera.somma"], moduli_permessi=(MODULO,))
    assert r.status == REJECTED


# --- con Lean e comparator ------------------------------------------------------

def test_una_dimostrazione_giusta_e_accettata(tmp_path):
    cand = _file(tmp_path, "c.lean",
                 f"import {MODULO}\nnamespace ProvaLibera\n"
                 "theorem somma (n : ℕ) : n + 0 = n := rfl\nend ProvaLibera\n")
    r = verify_libera(SFIDA_BUONA, cand, ["ProvaLibera.somma"], moduli_permessi=(MODULO,),
                      timeout=1500)
    assert r.status == ACCEPTED, (r.message, r.errors[-2000:])


def test_stesso_nome_ma_enunciato_diverso_e_rifiutato(tmp_path):
    cand = _file(tmp_path, "c.lean",
                 f"import {MODULO}\nnamespace ProvaLibera\n"
                 "theorem somma (n : ℕ) : 0 + n = n := Nat.zero_add n\nend ProvaLibera\n")
    r = verify_libera(SFIDA_BUONA, cand, ["ProvaLibera.somma"], moduli_permessi=(MODULO,),
                      timeout=1500)
    assert r.status == REJECTED, (r.message, r.errors[-2000:])


def test_appoggiarsi_al_sorry_di_un_problema_aperto_e_rifiutato(tmp_path):
    cand = _file(tmp_path, "c.lean",
                 f"import {MODULO}\nnamespace ProvaLibera\n"
                 "theorem dispari_perfetto (n : ℕ) (hn : Nat.Perfect n) : Even n :=\n"
                 "  PerfectNumbers.odd_perfect_number_conjecture n hn\nend ProvaLibera\n")
    r = verify_libera(SFIDA_APERTA, cand, ["ProvaLibera.dispari_perfetto"],
                      moduli_permessi=(MODULO,), timeout=1500)
    assert r.status == REJECTED, (r.message, r.errors[-2000:])
    testo = r.raw_output + r.errors + r.message
    assert "sorryAx" in testo or "xiom" in testo, testo[-2000:]


def test_un_olean_incompatibile_e_un_errore_di_strumenti_non_un_rifiuto():
    """Il guasto del 12 settembre 2026: RIFIUTATO invece di ERRORE."""
    from verify import _errore_di_strumenti
    uscita = ("uncaught exception: failed to read file '/x/Sfida0.olean', "
              "incompatible header")
    assert _errore_di_strumenti(uscita) is not None
    assert "lean4export-433" in _errore_di_strumenti(uscita)
    assert _errore_di_strumenti("error: unknown identifier 'foo'") is None
