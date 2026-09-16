"""
Test del computation dei costi e del limit di spesa.

Non chiamano l'API: usano oggetti `usage` finti. Il punto e' che l'aritmetica
sia giusta e che il limit venga fatto rispettare, non che l'API funzioni.

Il listino e' state verificato il 2026-09-10 sulla tabella ufficiale di
platform.claude.com (documentazione del prompt caching). Due details che era
facile sbagliare e che questi test difendono:

  * la write_op in cache a 1 ORA costa 2 volte l'input, non 1,25;
  * il moltiplicatore della LETTURA da cache non e' uguale per all_items i modelli:
    Fable 5.1 usa 0,025 invece di 0,1.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

from costs import Budget, Usage, SpendLimitExceeded, PRICE_LIST, prices


class _Detail:
    def __init__(self, cinque_min=0, un_ora=0):
        self.ephemeral_5m_input_tokens = cinque_min
        self.ephemeral_1h_input_tokens = un_ora


class _Usage:
    """Imita l'oggetto `usage` dell'SDK."""
    def __init__(self, inp=0, out=0, read_count=0, scritti_5m=0, scritti_1h=0, con_dettaglio=True):
        self.input_tokens = inp
        self.output_tokens = out
        self.cache_read_input_tokens = read_count
        self.cache_creation_input_tokens = scritti_5m + scritti_1h
        self.cache_creation = _Detail(scritti_5m, scritti_1h) if con_dettaglio else None


# --- il listino --------------------------------------------------------------

def test_i_prezzi_di_opus_5_sono_quelli_ufficiali():
    p = prices("claude-opus-5")
    assert (p.input, p.output) == (5.00, 25.00)
    assert p.cache_write_5m == 6.25      # 1,25 x input
    assert p.cache_write_1h == 10.00     # 2 x input, NON 1,25
    assert p.cache_read == 0.50           # 0,1 x input


def test_i_moltiplicatori_della_cache_non_sono_uguali_per_tutti():
    """Fable 5.1 legge dalla cache a 0,025 volte l'input invece di 0,1.
    Se i moltiplicatori fossero computed invece di scritti, questo sbaglio
    passerebbe inosservato."""
    fable = prices("claude-fable-5-1")
    assert fable.cache_read == 0.25
    assert fable.cache_read / fable.input == pytest.approx(0.025)
    opus = prices("claude-opus-5")
    assert opus.cache_read / opus.input == pytest.approx(0.10)


def test_un_modello_senza_prezzi_fa_fallire_subito():
    """Meglio rifiutarsi di partire che far rispettare un limit sbagliato."""
    with pytest.raises(KeyError, match="Unknown prices"):
        Budget(dollar_limit=5, model="claude-inventato").spent


def test_tutti_i_modelli_del_listino_sono_coerenti():
    for name, p in PRICE_LIST.items():
        assert p.cache_write_5m == pytest.approx(p.input * 1.25), name
        assert p.cache_write_1h == pytest.approx(p.input * 2.0), name
        assert p.output > p.input, name


# --- l'aritmetica ------------------------------------------------------------

def test_il_costo_somma_le_cinque_voci():
    c = Usage()
    c.add(_Usage(inp=10_000, out=2_000, read_count=200_000,
                      scritti_5m=50_000, scritti_1h=10_000))
    expected = (10_000 * 5.00 + 2_000 * 25.00 + 50_000 * 6.25
              + 10_000 * 10.00 + 200_000 * 0.50) / 1_000_000
    assert c.cost("claude-opus-5") == pytest.approx(expected)


def test_la_cache_a_un_ora_costa_il_doppio_di_quella_a_cinque_minuti():
    a = Usage(); a.add(_Usage(scritti_5m=100_000))
    b = Usage(); b.add(_Usage(scritti_1h=100_000))
    assert b.cost("claude-opus-5") == pytest.approx(a.cost("claude-opus-5") * 1.6)
    # 10.00 / 6.25 = 1.6


def test_senza_il_dettaglio_la_cache_viene_contata_come_a_cinque_minuti():
    c = Usage()
    c.add(_Usage(scritti_5m=40_000, con_dettaglio=False))
    assert c.cache_write_5m == 40_000
    assert c.cache_write_1h == 0


# --- il limit ---------------------------------------------------------------

def test_il_limite_blocca_quando_e_esaurito():
    b = Budget(dollar_limit=0.10, model="claude-opus-5")
    b.record(_Usage(out=10_000))          # 10k output = $0.25 > $0.10
    assert b.exhausted
    with pytest.raises(SpendLimitExceeded, match="Spending limit reached"):
        b.check_before_calling(1_000, 1_000)


def test_il_costo_massimo_possibile_e_il_caso_peggiore():
    """Ogni token in ingresso contato alla tariffa piu' cara (write_op in
    cache) e l'output contata come se riempisse tutto lo spazio concesso."""
    b = Budget(dollar_limit=100, model="claude-opus-5")
    expected = (20_000 * 6.25 + 32_000 * 25.00) / 1_000_000
    assert b.max_possible_cost(20_000, 32_000) == pytest.approx(expected)


def test_una_chiamata_che_potrebbe_sforare_non_parte():
    """E' il controllo che rende RIGIDO il limit: senza, one singola answer
    lunga sforerebbe before che ce ne accorgiamo."""
    b = Budget(dollar_limit=0.50, model="claude-opus-5")
    assert b.max_possible_cost(20_000, 32_000) > 0.50
    with pytest.raises(SpendLimitExceeded, match="Not starting"):
        b.check_before_calling(20_000, 32_000)


def test_una_chiamata_che_ci_sta_parte():
    b = Budget(dollar_limit=5.00, model="claude-opus-5")
    b.check_before_calling(20_000, 32_000)   # non deve sollevare


def test_max_tokens_sostenibile_si_restringe_col_budget():
    b = Budget(dollar_limit=0.50, model="claude-opus-5")
    affordable = b.affordable_max_tokens(20_000, 32_000)
    assert 0 < affordable < 32_000
    # con quel value la call deve poter partire
    b.check_before_calling(20_000, affordable)


def test_max_tokens_sostenibile_rispetta_anche_il_tetto_per_problema():
    b = Budget(dollar_limit=5.00, model="claude-opus-5")
    wide = b.affordable_max_tokens(20_000, 32_000)
    tight = b.affordable_max_tokens(20_000, 32_000, residue=0.30)
    assert tight < wide


def test_se_il_solo_ingresso_esaurisce_il_budget_non_resta_spazio():
    b = Budget(dollar_limit=0.01, model="claude-opus-5")
    assert b.affordable_max_tokens(1_000_000, 32_000) == 0


def test_il_consumo_viene_tenuto_anche_per_problema():
    b = Budget(dollar_limit=5.00, model="claude-opus-5")
    b.record(_Usage(out=1_000), problem="A")
    b.record(_Usage(out=3_000), problem="B")
    assert b.per_problem["A"].output_tokens == 1_000
    assert b.per_problem["B"].output_tokens == 3_000
    assert b.usage.output_tokens == 4_000


# --- controprova esterna: il conto deve riprodurre one bolletta vera ---------

def test_riproduce_la_spesa_misurata_da_epoch_ai():
    """Un attempt del benchmark OEIS Open, con i token e il cost che Epoch AI
    ha pubblicato: il nostro conto deve dare lo stesso number.

    Provenienza: `external/LeanOpenProblems-results/runs/oeis-full-50usd-ant-.../
    A055487_conjecture/info.json`, model `anthropic/claude-opus-4-8`,
    `total_cost` = 50.00493775. È la trial più forte che abbiamo sulla
    correttezza del computation del budget: viene da outside e da one fattura vera.
    """
    c = Usage(input_tokens=607, output_tokens=684_987,
                cache_write_5m=2_304_613, cache_read=36_946_793)
    # Opus 4.8 e Opus 5 hanno lo stesso listino
    assert abs(c.cost("claude-opus-4-8") - 50.005) < 0.01
    assert abs(c.cost("claude-opus-5") - 50.005) < 0.01


def test_fable_5_1_costa_1_45_volte_opus_5_su_un_profilo_lungo():
    """Non il doppio, come suggerirebbe il prezzo base.

    Fable 5.1 costa il doppio in ingresso e in output, ma la lettura dalla cache
    costa la METÀ in value assoluto ($0,25 against $0,50: 0,025x invece di 0,1x).
    In one sessione lunga la cache è la entry più grossa, quindi il report vero
    è più low. Se questo test si rompe, il confronto fra modelli nel piano di
    spesa va rifatto.
    """
    c = Usage(input_tokens=607, output_tokens=684_987,
                cache_write_5m=2_304_613, cache_read=36_946_793)
    report = c.cost("claude-fable-5-1") / c.cost("claude-opus-5")
    assert 1.40 < report < 1.50, report
