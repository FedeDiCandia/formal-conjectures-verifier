"""The code checker and the expansion of orbits.

The reference case is a published record: A(24,6,12) >= 5558, a code by
Braun, Humpich, Laaksonen & Ostergard, scaricato da aeb.win.tue.nl. Se
the expansion or the checker breaks, this test says so at once.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "search"))

import pytest   # noqa: E402
from codes import check, distance, weight   # noqa: E402
from orbits import expand, read_permutation, closure, apply   # noqa: E402

# the Fano plane: the seven translates of the block {0,1,3} mod 7. It is the
# optimal code A(7,4,3) = 7, and the smallest case in which an error shows.
FANO = [sum(1 << ((k + s) % 7) for k in (0, 1, 3)) for s in range(7)]


def test_the_fano_plane_is_a_valid_code():
    # sette blocks di weight 3 su sette points, a pairs a distance 4: A(7,4,3)=7
    e = check(FANO, n=7, d=4, w=3)
    assert e.ok, e.findings
    assert e.size == 7


def test_all_three_kinds_of_defect_are_found():
    assert "weight" in check([0b1111, 0b0011], n=4, d=2, w=2).findings[0]
    assert "duplicato" in check(FANO + [FANO[0]], n=7, d=4, w=3).findings[0]
    assert "distance" in check([0b000111, 0b001011], n=6, d=4, w=3).findings[0]
    assert "beyond position" in check([0b111000], n=3, d=2, w=3).findings[0]


def test_distance_and_weight():
    assert distance(0b1100, 0b0011) == 4
    assert weight(0b101101) == 4


def test_permutation_and_group():
    p = read_permutation("(0,1,2)(3,4)", 5)
    assert p == (1, 2, 0, 4, 3)
    assert len(closure([p], 5)) == 6           # Z3 x Z2
    assert apply(p, 0b00001) == 0b00010       # bit 0 moves to position 1


CODE = ROOT / "research_data" / "codici" / "i24.12a"


@pytest.mark.skipif(not CODE.is_file(), reason="published code not downloaded")
def test_it_reproduces_the_published_record_A_24_6_12():
    words, n, info = expand(CODE)
    assert n == 24
    assert info["ordine_gruppo"] == 504 and info["seeds"] == 19
    assert len(words) == 5558, "the published record is 5558 words"
    assert check(words, n=24, d=6, w=12).ok


def test_fast_and_slow_agree():
    """The fast criterion is not a heuristic: it has to give the same verdict."""
    import random
    from codes import fast_check
    rng = random.Random(20260911)
    cases = 0
    for _ in range(400):
        n = rng.randint(6, 14)
        w = rng.randint(2, n - 1)
        d = 2 * rng.randint(1, w)
        m = rng.randint(1, 14)
        words = [sum(1 << i for i in rng.sample(range(n), w)) for _ in range(m)]
        slow = check(words, n, d, w)
        fast = fast_check(words, n, d, w)
        assert slow.ok == fast.ok, (n, d, w, words, slow.findings, fast.findings)
        cases += 1
    assert cases == 400


def test_fast_on_a_large_published_code():
    from codes import fast_check
    if not CODE.is_file():
        pytest.skip("published code not downloaded")
    words, n, _ = expand(CODE)
    assert fast_check(words, n=24, d=6, w=12).ok


def test_the_two_exact_shortcuts_do_not_change_the_result():
    """The representative shortcuts have to give the same orbits as the naive
    computation over all pairs. If they were wrong, the search would produce invalid
    codes without noticing."""
    from itertools import combinations
    from search_core import orbits_and_compatibility
    from groups import cyclic
    for n, d, w in ((9, 4, 3), (10, 4, 4), (11, 6, 4), (12, 6, 5)):
        G = cyclic(n)
        orbits, weights, neighbours = orbits_and_compatibility(n, d, w, G)
        for o in orbits:      # every orbit kept is valid on all pairs
            assert all((a ^ b).bit_count() >= d for a, b in combinations(o, 2))
        for i, o in enumerate(orbits):
            for j in neighbours[i]:
                assert all((a ^ b).bit_count() >= d
                           for a in o for b in orbits[j]), (n, d, w, i, j)
        assert weights == [len(o) for o in orbits]
