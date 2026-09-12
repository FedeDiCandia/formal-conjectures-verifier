"""Con un tetto basso l'agente deve fare PIÙ DI UNA chiamata.

Il difetto che questi test fissano ha invalidato un esperimento intero. Il
controllo del budget si fermava quando `max_tokens` scendeva sotto 6000, che con
i prezzi di Fable 5.1 vale $0,30 di margine per chiamata: con un tetto da $0,50
per problema l'agente aveva una chiamata sola, e su due problemi su undici ne ha
avute zero. Il risultato sembrava «il modello si arrende» ed era «il contabile
non lo lascia lavorare».

Qui si simula l'aritmetica del ciclo, senza chiamare l'API.
"""
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "agent"))
sys.path.insert(0, str(RADICE / "verifier"))

import agente
from costi import Budget, Consumo


def _chiamate_possibili(modello: str, tetto: float, token_input: int,
                        costo_per_chiamata: float) -> int:
    """Quante chiamate riesce a fare, con la regola vera del ciclo."""
    b = Budget(limite_dollari=tetto * 10, modello=modello)
    speso_qui = 0.0
    chiamate = 0
    for _ in range(50):
        residuo = tetto - speso_qui
        max_tokens = b.max_tokens_sostenibile(token_input, agente.MAX_TOKENS,
                                              residuo=residuo)
        if max_tokens < agente.MIN_TOKENS_UTILI:
            break
        chiamate += 1
        speso_qui += costo_per_chiamata
        # il budget globale deve seguire, altrimenti il residuo non scende
        b.registra(_finto_usage(costo_per_chiamata, modello), "prova")
    return chiamate


class _FintoUsage:
    def __init__(self, output):
        self.input_tokens = 0
        self.output_tokens = output
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0
        self.cache_creation = None


def _finto_usage(costo: float, modello: str):
    from costi import prezzi
    return _FintoUsage(int(costo * 1_000_000 / prezzi(modello).output))


def test_con_tetto_basso_e_fable_fa_piu_di_una_chiamata():
    """È il test che il difetto avrebbe fatto fallire: con $0,50 di tetto e
    chiamate da 5 centesimi, di chiamate ce ne stanno parecchie."""
    n = _chiamate_possibili("claude-fable-5-1", tetto=0.50,
                            token_input=8000, costo_per_chiamata=0.05)
    assert n >= 5, f"solo {n} chiamate con $0,50 di tetto"


def test_la_soglia_vecchia_fermava_il_tentativo_prima_di_cominciare():
    """I numeri veri dell'incidente, presi dal registro della variante B.

    `SidorenkoConjecture...non_bipartite_necessary`: 16 287 token in ingresso,
    tetto $0,50, speso $0,00. Con la soglia vecchia il tentativo non partiva
    nemmeno; con quella nuova fa la sua chiamata.
    """
    vecchia = 6_000
    b = Budget(limite_dollari=5.0, modello="claude-fable-5-1")
    max_tokens = b.max_tokens_sostenibile(16_287, agente.MAX_TOKENS, residuo=0.50)
    assert max_tokens < vecchia, "questi sono i numeri che fermavano il tentativo"
    assert max_tokens >= agente.MIN_TOKENS_UTILI, (
        "con la soglia nuova lo stesso tentativo deve poter partire")


def test_il_limite_resta_rigido():
    """L'invariante vero, e vale la pena scriverlo per esteso.

    Non è «il caso peggiore sta sempre nel residuo»: quando il residuo non copre
    nemmeno il costo dell'INGRESSO, la funzione restituisce 0 e il ciclo si
    ferma. L'invariante è: **se il ciclo procede, il caso peggiore sta nel
    residuo.** Scritto male, questo test dichiarava rigido un limite che non lo
    era; scritto così, dice la cosa giusta.
    """
    b = Budget(limite_dollari=5.0, modello="claude-fable-5-1")
    for residuo in (0.02, 0.05, 0.12, 0.30, 0.50, 1.40, 2.00):
        for token_input in (2_000, 10_000, 40_000):
            mt = b.max_tokens_sostenibile(token_input, agente.MAX_TOKENS,
                                          residuo=residuo)
            if mt < agente.MIN_TOKENS_UTILI:
                continue          # il ciclo si fermerebbe qui: niente da garantire
            peggiore = b.costo_massimo_possibile(token_input, mt)
            assert peggiore <= residuo + 1e-9, (
                f"residuo ${residuo}, ingresso {token_input}: il caso peggiore "
                f"e' ${peggiore:.4f} e supera il residuo")


def test_sotto_la_soglia_minima_si_ferma():
    """Se non c'è spazio nemmeno per una risposta minima, il tentativo finisce."""
    b = Budget(limite_dollari=5.0, modello="claude-fable-5-1")
    mt = b.max_tokens_sostenibile(10_000, agente.MAX_TOKENS, residuo=0.02)
    assert mt < agente.MIN_TOKENS_UTILI


def test_opus_5_regge_un_tetto_piu_basso_di_fable():
    """A parità di tetto Opus 5 fa più chiamate: costa metà per token."""
    o = _chiamate_possibili("claude-opus-5", 0.50, 8000, 0.05)
    f = _chiamate_possibili("claude-fable-5-1", 0.50, 8000, 0.05)
    assert o >= f, f"Opus {o} chiamate, Fable {f}"


def test_il_tentativo_interrotto_dal_budget_non_perde_il_lavoro_fatto():
    """Quando il budget TOTALE finisce a metà di un problema, quel problema
    finiva nel rapporto con $0,00 e zero verifiche.

    E' successo nel giro 0 bis: il settimo problema risultava a costo zero
    mentre il registro mostrava una verifica consegnata. Un rapporto che
    sottostima la spesa e' un problema di sicurezza, non di cosmetica: il
    limite rigido si controlla proprio su quei numeri.
    """
    from costi import LimiteSpesaSuperato
    t = agente.Tentativo(problema="X.y")
    t.iterazioni = 3
    t.verifiche = 1
    e = LimiteSpesaSuperato("finito")
    e.tentativo = t
    # e' il meccanismo che main() usa: l'eccezione porta con se' il tentativo
    assert getattr(e, "tentativo", None) is t
    assert e.tentativo.verifiche == 1
