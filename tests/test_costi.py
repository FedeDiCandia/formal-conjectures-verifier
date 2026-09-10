"""
Test del calcolo dei costi e del limite di spesa.

Non chiamano l'API: usano oggetti `usage` finti. Il punto e' che l'aritmetica
sia giusta e che il limite venga fatto rispettare, non che l'API funzioni.

Il listino e' stato verificato il 2026-09-10 sulla tabella ufficiale di
platform.claude.com (documentazione del prompt caching). Due dettagli che era
facile sbagliare e che questi test difendono:

  * la scrittura in cache a 1 ORA costa 2 volte l'input, non 1,25;
  * il moltiplicatore della LETTURA da cache non e' uguale per tutti i modelli:
    Fable 5.1 usa 0,025 invece di 0,1.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

from costi import Budget, Consumo, LimiteSpesaSuperato, LISTINO, prezzi


class _Dettaglio:
    def __init__(self, cinque_min=0, un_ora=0):
        self.ephemeral_5m_input_tokens = cinque_min
        self.ephemeral_1h_input_tokens = un_ora


class _Usage:
    """Imita l'oggetto `usage` dell'SDK."""
    def __init__(self, inp=0, out=0, letti=0, scritti_5m=0, scritti_1h=0, con_dettaglio=True):
        self.input_tokens = inp
        self.output_tokens = out
        self.cache_read_input_tokens = letti
        self.cache_creation_input_tokens = scritti_5m + scritti_1h
        self.cache_creation = _Dettaglio(scritti_5m, scritti_1h) if con_dettaglio else None


# --- il listino --------------------------------------------------------------

def test_i_prezzi_di_opus_5_sono_quelli_ufficiali():
    p = prezzi("claude-opus-5")
    assert (p.input, p.output) == (5.00, 25.00)
    assert p.scrittura_cache_5m == 6.25      # 1,25 x input
    assert p.scrittura_cache_1h == 10.00     # 2 x input, NON 1,25
    assert p.lettura_cache == 0.50           # 0,1 x input


def test_i_moltiplicatori_della_cache_non_sono_uguali_per_tutti():
    """Fable 5.1 legge dalla cache a 0,025 volte l'input invece di 0,1.
    Se i moltiplicatori fossero calcolati invece di scritti, questo sbaglio
    passerebbe inosservato."""
    fable = prezzi("claude-fable-5-1")
    assert fable.lettura_cache == 0.25
    assert fable.lettura_cache / fable.input == pytest.approx(0.025)
    opus = prezzi("claude-opus-5")
    assert opus.lettura_cache / opus.input == pytest.approx(0.10)


def test_un_modello_senza_prezzi_fa_fallire_subito():
    """Meglio rifiutarsi di partire che far rispettare un limite sbagliato."""
    with pytest.raises(KeyError, match="Prezzi sconosciuti"):
        Budget(limite_dollari=5, modello="claude-inventato").speso


def test_tutti_i_modelli_del_listino_sono_coerenti():
    for nome, p in LISTINO.items():
        assert p.scrittura_cache_5m == pytest.approx(p.input * 1.25), nome
        assert p.scrittura_cache_1h == pytest.approx(p.input * 2.0), nome
        assert p.output > p.input, nome


# --- l'aritmetica ------------------------------------------------------------

def test_il_costo_somma_le_cinque_voci():
    c = Consumo()
    c.aggiungi(_Usage(inp=10_000, out=2_000, letti=200_000,
                      scritti_5m=50_000, scritti_1h=10_000))
    atteso = (10_000 * 5.00 + 2_000 * 25.00 + 50_000 * 6.25
              + 10_000 * 10.00 + 200_000 * 0.50) / 1_000_000
    assert c.costo("claude-opus-5") == pytest.approx(atteso)


def test_la_cache_a_un_ora_costa_il_doppio_di_quella_a_cinque_minuti():
    a = Consumo(); a.aggiungi(_Usage(scritti_5m=100_000))
    b = Consumo(); b.aggiungi(_Usage(scritti_1h=100_000))
    assert b.costo("claude-opus-5") == pytest.approx(a.costo("claude-opus-5") * 1.6)
    # 10.00 / 6.25 = 1.6


def test_senza_il_dettaglio_la_cache_viene_contata_come_a_cinque_minuti():
    c = Consumo()
    c.aggiungi(_Usage(scritti_5m=40_000, con_dettaglio=False))
    assert c.scrittura_cache_5m == 40_000
    assert c.scrittura_cache_1h == 0


# --- il limite ---------------------------------------------------------------

def test_il_limite_blocca_quando_e_esaurito():
    b = Budget(limite_dollari=0.10, modello="claude-opus-5")
    b.registra(_Usage(out=10_000))          # 10k output = $0.25 > $0.10
    assert b.esaurito
    with pytest.raises(LimiteSpesaSuperato, match="Limite di spesa raggiunto"):
        b.verifica_prima_di_chiamare(1_000, 1_000)


def test_il_costo_massimo_possibile_e_il_caso_peggiore():
    """Ogni token in ingresso contato alla tariffa piu' cara (scrittura in
    cache) e l'uscita contata come se riempisse tutto lo spazio concesso."""
    b = Budget(limite_dollari=100, modello="claude-opus-5")
    atteso = (20_000 * 6.25 + 32_000 * 25.00) / 1_000_000
    assert b.costo_massimo_possibile(20_000, 32_000) == pytest.approx(atteso)


def test_una_chiamata_che_potrebbe_sforare_non_parte():
    """E' il controllo che rende RIGIDO il limite: senza, una singola risposta
    lunga sforerebbe prima che ce ne accorgiamo."""
    b = Budget(limite_dollari=0.50, modello="claude-opus-5")
    assert b.costo_massimo_possibile(20_000, 32_000) > 0.50
    with pytest.raises(LimiteSpesaSuperato, match="Non parto"):
        b.verifica_prima_di_chiamare(20_000, 32_000)


def test_una_chiamata_che_ci_sta_parte():
    b = Budget(limite_dollari=5.00, modello="claude-opus-5")
    b.verifica_prima_di_chiamare(20_000, 32_000)   # non deve sollevare


def test_max_tokens_sostenibile_si_restringe_col_budget():
    b = Budget(limite_dollari=0.50, modello="claude-opus-5")
    sostenibile = b.max_tokens_sostenibile(20_000, 32_000)
    assert 0 < sostenibile < 32_000
    # con quel valore la chiamata deve poter partire
    b.verifica_prima_di_chiamare(20_000, sostenibile)


def test_max_tokens_sostenibile_rispetta_anche_il_tetto_per_problema():
    b = Budget(limite_dollari=5.00, modello="claude-opus-5")
    largo = b.max_tokens_sostenibile(20_000, 32_000)
    stretto = b.max_tokens_sostenibile(20_000, 32_000, residuo=0.30)
    assert stretto < largo


def test_se_il_solo_ingresso_esaurisce_il_budget_non_resta_spazio():
    b = Budget(limite_dollari=0.01, modello="claude-opus-5")
    assert b.max_tokens_sostenibile(1_000_000, 32_000) == 0


def test_il_consumo_viene_tenuto_anche_per_problema():
    b = Budget(limite_dollari=5.00, modello="claude-opus-5")
    b.registra(_Usage(out=1_000), problema="A")
    b.registra(_Usage(out=3_000), problema="B")
    assert b.per_problema["A"].output_tokens == 1_000
    assert b.per_problema["B"].output_tokens == 3_000
    assert b.consumo.output_tokens == 4_000
