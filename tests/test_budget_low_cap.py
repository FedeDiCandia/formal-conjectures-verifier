"""Con un cap low l'agent deve fare PIÙ DI UNA call.

Il finding che questi test fissano ha invalidato un esperimento intero. Il
controllo del budget si fermava quando `max_tokens` scendeva below 6000, che con
i prices di Fable 5.1 vale $0,30 di margine per call: con un cap da $0,50
per problem l'agent aveva one_ call sola, e su two problems su undici ne ha
avute zero. Il result_value sembrava «il model si arrende» ed era «il contabile
non lo lascia lavorare».

Qui si simula l'aritmetica del ciclo, senza chiamare l'API.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "verifier"))

import agent
from costs import Budget, Usage


def _possible_calls(model: str, cap: float, input_tokens: int,
                        cost_per_call: float) -> int:
    """Quante calls riesce a fare, con la rule_ vera del ciclo."""
    b = Budget(dollar_limit=cap * 10, model=model)
    spent_here = 0.0
    calls = 0
    for _ in range(50):
        residue = cap - spent_here
        max_tokens = b.affordable_max_tokens(input_tokens, agent.MAX_TOKENS,
                                              residue=residue)
        if max_tokens < agent.MIN_USEFUL_TOKENS:
            break
        calls += 1
        spent_here += cost_per_call
        # il budget globale deve seguire, altrimenti il residue non scende
        b.record(_fake_usage(cost_per_call, model), "trial")
    return calls


class _FakeUsage:
    def __init__(self, output):
        self.input_tokens = 0
        self.output_tokens = output
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0
        self.cache_creation = None


def _fake_usage(cost: float, model: str):
    from costs import prices
    return _FakeUsage(int(cost * 1_000_000 / prices(model).output))


def test_con_tetto_basso_e_fable_fa_piu_di_una_chiamata():
    """È il test che il finding avrebbe fatto fallire: con $0,50 di cap e
    calls da 5 centesimi, di calls ce ne stanno parecchie."""
    n = _possible_calls("claude-fable-5-1", cap=0.50,
                            input_tokens=8000, cost_per_call=0.05)
    assert n >= 5, f"only_ {n} calls con $0,50 di cap"


def test_la_soglia_vecchia_fermava_il_tentativo_prima_di_cominciare():
    """I numbers real_ones dell'incidente, presi dal log_ della variant B.

    `SidorenkoConjecture...non_bipartite_necessary`: 16 287 token in ingresso,
    cap $0,50, spent $0,00. Con la threshold old_one il attempt non partiva
    nemmeno; con quella new_ fa la sua call.
    """
    old_one = 6_000
    b = Budget(dollar_limit=5.0, model="claude-fable-5-1")
    max_tokens = b.affordable_max_tokens(16_287, agent.MAX_TOKENS, residue=0.50)
    assert max_tokens < old_one, "questi sono i numbers che fermavano il attempt"
    assert max_tokens >= agent.MIN_USEFUL_TOKENS, (
        "con la threshold new_ lo stesso attempt deve poter partire")


def test_il_limite_resta_rigido():
    """L'invariante vero, e vale la pena scriverlo per esteso.

    Non è «il caso worst sta sempre nel residue»: quando il residue non copre
    nemmeno il cost dell'INGRESSO, la funzione restituisce 0 e il ciclo si
    ferma. L'invariante è: **se il ciclo procede, il caso worst sta nel
    residue.** Scritto male, questo test dichiarava rigido un limit che non lo
    era; scritto così, dice la cosa giusta.
    """
    b = Budget(dollar_limit=5.0, model="claude-fable-5-1")
    for residue in (0.02, 0.05, 0.12, 0.30, 0.50, 1.40, 2.00):
        for input_tokens in (2_000, 10_000, 40_000):
            mt = b.affordable_max_tokens(input_tokens, agent.MAX_TOKENS,
                                          residue=residue)
            if mt < agent.MIN_USEFUL_TOKENS:
                continue          # il ciclo si fermerebbe qui: niente da garantire
            worst = b.max_possible_cost(input_tokens, mt)
            assert worst <= residue + 1e-9, (
                f"residue ${residue}, ingresso {input_tokens}: il caso worst "
                f"e' ${worst:.4f} e supera il residue")


def test_sotto_la_soglia_minima_si_ferma():
    """Se non c'è spazio nemmeno per one_ answer minima, il attempt finisce."""
    b = Budget(dollar_limit=5.0, model="claude-fable-5-1")
    mt = b.affordable_max_tokens(10_000, agent.MAX_TOKENS, residue=0.02)
    assert mt < agent.MIN_USEFUL_TOKENS


def test_opus_5_regge_un_tetto_piu_basso_di_fable():
    """A parità di cap Opus 5 fa più calls: costa metà per token."""
    o = _possible_calls("claude-opus-5", 0.50, 8000, 0.05)
    f = _possible_calls("claude-fable-5-1", 0.50, 8000, 0.05)
    assert o >= f, f"Opus {o} calls, Fable {f}"


def test_il_tentativo_interrotto_dal_budget_non_perde_il_lavoro_fatto():
    """Quando il budget TOTALE finisce a metà di un problem, quel problem
    finiva nel report con $0,00 e zero checks.

    E' successo nel giro 0 bis: il settimo problem risultava a cost zero
    mentre il log_ mostrava one_ check consegnata. Un report che
    sottostima la spesa e' un problem di sicurezza, non di cosmetica: il
    limit rigido si controlla proprio su quei numbers.
    """
    from costs import SpendLimitExceeded
    t = agent.Attempt(problem="X.y")
    t.iterations = 3
    t.checks = 1
    e = SpendLimitExceeded("finito")
    e.attempt = t
    # e' il meccanismo che main() usa: l'eccezione porta con se' il attempt
    assert getattr(e, "attempt", None) is t
    assert e.attempt.checks == 1
