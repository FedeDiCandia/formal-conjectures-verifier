"""Il verificatore dei codici e l'espansione delle orbite.

Il caso di riferimento e' un record pubblicato: A(24,6,12) >= 5558, codice di
Braun, Humpich, Laaksonen & Ostergard, scaricato da aeb.win.tue.nl. Se
l'espansione o il verificatore si rompono, questo test lo dice subito.
"""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "search"))

import pytest   # noqa: E402
from codes import verifica, distanza, peso   # noqa: E402
from orbits import espandi, leggi_permutazione, chiusura, applica   # noqa: E402

# piano di Fano: le sette traslate del blocco {0,1,3} modulo 7. E' il codice
# ottimo A(7,4,3) = 7, ed e' il caso piu' piccolo su cui un errore si vede.
FANO = [sum(1 << ((k + s) % 7) for k in (0, 1, 3)) for s in range(7)]


def test_il_piano_di_fano_e_un_codice_valido():
    # sette blocchi di peso 3 su sette punti, a coppie a distanza 4: A(7,4,3)=7
    e = verifica(FANO, n=7, d=4, w=3)
    assert e.ok, e.difetti
    assert e.dimensione == 7


def test_i_difetti_sono_trovati_tutti_e_tre_i_tipi():
    assert "peso" in verifica([0b1111, 0b0011], n=4, d=2, w=2).difetti[0]
    assert "duplicato" in verifica(FANO + [FANO[0]], n=7, d=4, w=3).difetti[0]
    assert "distanza" in verifica([0b000111, 0b001011], n=6, d=4, w=3).difetti[0]
    assert "oltre la posizione" in verifica([0b111000], n=3, d=2, w=3).difetti[0]


def test_distanza_e_peso():
    assert distanza(0b1100, 0b0011) == 4
    assert peso(0b101101) == 4


def test_permutazione_e_gruppo():
    p = leggi_permutazione("(0,1,2)(3,4)", 5)
    assert p == (1, 2, 0, 4, 3)
    assert len(chiusura([p], 5)) == 6           # Z3 x Z2
    assert applica(p, 0b00001) == 0b00010       # il bit 0 va in posizione 1


CODICE = RADICE / "research_data" / "codici" / "i24.12a"


@pytest.mark.skipif(not CODICE.is_file(), reason="codice pubblicato non scaricato")
def test_riproduce_il_record_pubblicato_A_24_6_12():
    parole, n, info = espandi(CODICE)
    assert n == 24
    assert info["ordine_gruppo"] == 504 and info["semi"] == 19
    assert len(parole) == 5558, "il record pubblicato e' 5558 parole"
    assert verifica(parole, n=24, d=6, w=12).ok


def test_rapido_e_lento_concordano():
    """Il criterio rapido non e' un'euristica: deve dare lo stesso verdetto."""
    import random
    from codes import verifica_veloce
    rng = random.Random(20260911)
    casi = 0
    for _ in range(400):
        n = rng.randint(6, 14)
        w = rng.randint(2, n - 1)
        d = 2 * rng.randint(1, w)
        m = rng.randint(1, 14)
        parole = [sum(1 << i for i in rng.sample(range(n), w)) for _ in range(m)]
        lento = verifica(parole, n, d, w)
        rapido = verifica_veloce(parole, n, d, w)
        assert lento.ok == rapido.ok, (n, d, w, parole, lento.difetti, rapido.difetti)
        casi += 1
    assert casi == 400


def test_rapido_su_un_codice_grande_pubblicato():
    from codes import verifica_veloce
    if not CODICE.is_file():
        pytest.skip("codice pubblicato non scaricato")
    parole, n, _ = espandi(CODICE)
    assert verifica_veloce(parole, n=24, d=6, w=12).ok


def test_le_due_semplificazioni_esatte_non_cambiano_il_risultato():
    """Le scorciatoie del rappresentante devono dare le stesse orbite del calcolo
    ingenuo su tutte le coppie. Se sbagliassero, la ricerca produrrebbe codici
    non validi senza accorgersene."""
    from itertools import combinations
    from search_core import orbite_e_compatibilita
    from groups import ciclico
    for n, d, w in ((9, 4, 3), (10, 4, 4), (11, 6, 4), (12, 6, 5)):
        G = ciclico(n)
        orbite, pesi, vicini = orbite_e_compatibilita(n, d, w, G)
        for o in orbite:      # ogni orbita tenuta e' valida a tutte le coppie
            assert all((a ^ b).bit_count() >= d for a, b in combinations(o, 2))
        for i, o in enumerate(orbite):
            for j in vicini[i]:
                assert all((a ^ b).bit_count() >= d
                           for a in o for b in orbite[j]), (n, d, w, i, j)
        assert pesi == [len(o) for o in orbite]
