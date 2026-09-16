"""
Calcolo dei costi e limit di spesa.

I numbers vengono dai fields `usage` che l'API restituisce in OGNI answer:
non sono stime, sono i token effettivamente fatturati.

Il limit viene fatto rispettare in DUE momenti:

  * a posteriori, sommando quanto e' state spent;
  * a priori, PRIMA di ogni call: si count esattamente how_many token
    entreranno nella richiesta (con l'endpoint di count, che e' gratuito) e
    si compute il cost MASSIMO possibile di quella call. Se non ci sta nel
    residue, la call non parte.

Il second controllo e' quello che rende il limit davvero rigido: senza, one
singola answer lunga potrebbe sforare di parecchio before che ce ne accorgiamo.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Prices:
    """Dollari per MILIONE di token."""
    input: float
    output: float
    cache_write_5m: float
    cache_write_1h: float
    cache_read: float


#: Listino ufficiale (platform.claude.com/docs — Prompt caching, tabella prices;
#: verificato il 2026-09-10).
#:
#: I moltiplicatori NON sono uguali per all_items i modelli, quindi qui sono scritti
#: i prices assoluti invece di calcolarli:
#:   - write_op in cache a 5 minuti: 1,25 volte l'input;
#:   - write_op in cache a 1 now:    2 volte l'input  (non 1,25!);
#:   - lettura da cache:              0,1 volte l'input,
#:     TRANNE Fable 5.1 e Mythos 5.1, che usano 0,025 volte.
#: Prices in dollari per milione di token, VERIFICATI sulla pagina ufficiale
#: <https://platform.claude.com/docs/en/about-claude/pricing> l'11 settembre 2026.
#: Si tengono in forma assoluta e non come moltiplicatori perche' i moltiplicatori
#: NON sono universali: la lettura dalla cache costa 0,1x il prezzo d'ingresso su
#: all_items i modelli tranne Fable 5.1 e Mythos 5.1, dove costa 0,025x. Con un
#: moltiplicatore unico il budget di Fable 5.1 sarebbe sbagliato di quattro volte
#: sulla entry che in one sessione lunga pesa piu' di all_items.
#:
#: Nota sul confronto fra modelli: Fable 5.1 costa il doppio di Opus 5 in ingresso
#: e in output, ma la sua lettura dalla cache costa la META' in value assoluto
#: ($0,25 against $0,50). Sul profile di token di un attempt lungo — MISURATO da
#: Epoch AI: 36,9 milioni di token read_count dalla cache against 685 mila in output —
#: il report reale non e' 2x ma 1,45x.
PRICE_LIST: dict[str, Prices] = {
    "claude-opus-5":    Prices(input=5.00,  output=25.00, cache_write_5m=6.25,
                               cache_write_1h=10.00, cache_read=0.50),
    "claude-opus-4-8":  Prices(input=5.00,  output=25.00, cache_write_5m=6.25,
                               cache_write_1h=10.00, cache_read=0.50),
    "claude-sonnet-5":  Prices(input=2.00,  output=10.00, cache_write_5m=2.50,
                               cache_write_1h=4.00,  cache_read=0.20),
    "claude-haiku-4-5": Prices(input=1.00,  output=5.00,  cache_write_5m=1.25,
                               cache_write_1h=2.00,  cache_read=0.10),
    "claude-fable-5-1": Prices(input=10.00, output=50.00, cache_write_5m=12.50,
                               cache_write_1h=20.00, cache_read=0.25),
    "claude-fable-5":   Prices(input=10.00, output=50.00, cache_write_5m=12.50,
                               cache_write_1h=20.00, cache_read=1.00),
}


def prices(model: str) -> Prices:
    if model in PRICE_LIST:
        return PRICE_LIST[model]
    raise KeyError(
        f"Prices sconosciuti per il model '{model}'. Aggiungili in agent/costs.py "
        f"before di usarlo: senza prices il limit di spesa non puo' essere fatto "
        f"rispettare, ed e' meglio fermarsi che far finta. "
        f"Modelli noti: {', '.join(PRICE_LIST)}")


@dataclass
class Usage:
    """Token consumati, sommati su piu' calls."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    calls: int = 0

    def add(self, usage) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0

        # L'API distingue le scritture in cache a 5 minuti da quelle a 1 now,
        # che costano il doppio. Se il detail non c'e' (risposte vecchie o
        # altri fornitori), si usa il total e lo si count come 5 minuti — e'
        # la tariffa piu' bassa, quindi il field dettagliato va preferito
        # quando c'e', per non SOTTOstimare.
        detail = getattr(usage, "cache_creation", None)
        if detail is not None:
            self.cache_write_5m += getattr(detail, "ephemeral_5m_input_tokens", 0) or 0
            self.cache_write_1h += getattr(detail, "ephemeral_1h_input_tokens", 0) or 0
        else:
            self.cache_write_5m += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.calls += 1

    def cost(self, model: str) -> float:
        p = prices(model)
        return (self.input_tokens * p.input
                + self.output_tokens * p.output
                + self.cache_write_5m * p.cache_write_5m
                + self.cache_write_1h * p.cache_write_1h
                + self.cache_read * p.cache_read) / 1_000_000

    def riassunto(self, model: str) -> str:
        cache = f"cache scritta {self.cache_write_5m:,}"
        if self.cache_write_1h:
            cache += f" (+{self.cache_write_1h:,} a 1h)"
        return (f"{self.calls} calls | input {self.input_tokens:,} | {cache} | "
                f"cache letta {self.cache_read:,} | output {self.output_tokens:,} | "
                f"cost ${self.cost(model):.4f}")


class SpendLimitExceeded(RuntimeError):
    """Sollevata quando il budget non basta piu'. Ferma tutto."""


@dataclass
class Budget:
    dollar_limit: float
    model: str
    usage: Usage = field(default_factory=Usage)
    per_problem: dict[str, Usage] = field(default_factory=dict)

    @property
    def prices(self) -> Prices:
        return prices(self.model)

    @property
    def spent(self) -> float:
        return self.usage.cost(self.model)

    @property
    def residue(self) -> float:
        return max(0.0, self.dollar_limit - self.spent)

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.dollar_limit

    def record(self, usage, problem: str = "") -> None:
        self.usage.add(usage)
        if problem:
            self.per_problem.setdefault(problem, Usage()).add(usage)

    # --- il controllo a priori, quello che rende rigido il limit -----------

    def max_possible_cost(self, input_tokens: int, max_tokens: int) -> float:
        """Il cost worst che one call puo' avere.

        Peggiore davvero:
          * ogni token di ingresso viene contato alla tariffa di SCRITTURA in
            cache, che e' la piu' cara delle three possibilita' (1,25 volte
            l'input). In pratica one parte sara' letta dalla cache e costera'
            dieci volte meno, ma qui non si scommette;
          * l'output viene contata come se il model riempisse tutto lo spazio
            concessogli da `max_tokens`.
        """
        p = self.prices
        return (input_tokens * p.cache_write_5m + max_tokens * p.output) / 1_000_000

    def check_before_calling(self, input_tokens: int, max_tokens: int) -> None:
        """Da chiamare PRIMA di ogni richiesta. Solleva se non ci sta."""
        if self.exhausted:
            raise SpendLimitExceeded(
                f"Limite di spesa reached: ${self.spent:.4f} su "
                f"${self.dollar_limit:.2f}. Mi fermo.")
        worst = self.max_possible_cost(input_tokens, max_tokens)
        if worst > self.residue:
            raise SpendLimitExceeded(
                f"Non parto: questa call puo' costare fino a ${worst:.4f} "
                f"({input_tokens:,} token in ingresso, fino a {max_tokens:,} in output) "
                f"ma restano only ${self.residue:.4f} "
                f"(spesi ${self.spent:.4f} su ${self.dollar_limit:.2f}).")

    def affordable_max_tokens(self, input_tokens: int, cap: int,
                               residue: float | None = None) -> int:
        """Quanti token di output ci si possono ancora permettere.

        Serve per ridurre `max_tokens` invece di fermarsi, quando il residue e'
        poco ma non nullo. `residue` permette di passare un limit piu' tight
        di quello globale, per example il cap di spesa di un singolo problem.
        """
        p = self.prices
        available = self.residue if residue is None else min(self.residue, residue)
        input_cost = input_tokens * p.cache_write_5m / 1_000_000
        leftover = available - input_cost
        if leftover <= 0:
            return 0
        return min(cap, int(leftover * 1_000_000 / p.output))

    def riga_stato(self) -> str:
        pct = 100 * self.spent / self.dollar_limit if self.dollar_limit else 0
        return f"[spesa ${self.spent:.4f} / ${self.dollar_limit:.2f}  ({pct:.0f}%)]"
