"""
Calcolo dei costi e limite di spesa.

I numeri vengono dai campi `usage` che l'API restituisce in OGNI risposta:
non sono stime, sono i token effettivamente fatturati.

Il limite viene fatto rispettare in DUE momenti:

  * a posteriori, sommando quanto e' stato speso;
  * a priori, PRIMA di ogni chiamata: si conta esattamente quanti token
    entreranno nella richiesta (con l'endpoint di conteggio, che e' gratuito) e
    si calcola il costo MASSIMO possibile di quella chiamata. Se non ci sta nel
    residuo, la chiamata non parte.

Il secondo controllo e' quello che rende il limite davvero rigido: senza, una
singola risposta lunga potrebbe sforare di parecchio prima che ce ne accorgiamo.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Prezzi:
    """Dollari per MILIONE di token."""
    input: float
    output: float
    scrittura_cache_5m: float
    scrittura_cache_1h: float
    lettura_cache: float


#: Listino ufficiale (platform.claude.com/docs — Prompt caching, tabella prezzi;
#: verificato il 2026-09-10).
#:
#: I moltiplicatori NON sono uguali per tutti i modelli, quindi qui sono scritti
#: i prezzi assoluti invece di calcolarli:
#:   - scrittura in cache a 5 minuti: 1,25 volte l'input;
#:   - scrittura in cache a 1 ora:    2 volte l'input  (non 1,25!);
#:   - lettura da cache:              0,1 volte l'input,
#:     TRANNE Fable 5.1 e Mythos 5.1, che usano 0,025 volte.
#: Prezzi in dollari per milione di token, VERIFICATI sulla pagina ufficiale
#: <https://platform.claude.com/docs/en/about-claude/pricing> l'11 settembre 2026.
#: Si tengono in forma assoluta e non come moltiplicatori perche' i moltiplicatori
#: NON sono universali: la lettura dalla cache costa 0,1x il prezzo d'ingresso su
#: tutti i modelli tranne Fable 5.1 e Mythos 5.1, dove costa 0,025x. Con un
#: moltiplicatore unico il budget di Fable 5.1 sarebbe sbagliato di quattro volte
#: sulla voce che in una sessione lunga pesa piu' di tutte.
#:
#: Nota sul confronto fra modelli: Fable 5.1 costa il doppio di Opus 5 in ingresso
#: e in uscita, ma la sua lettura dalla cache costa la META' in valore assoluto
#: ($0,25 contro $0,50). Sul profilo di token di un tentativo lungo — MISURATO da
#: Epoch AI: 36,9 milioni di token letti dalla cache contro 685 mila in uscita —
#: il rapporto reale non e' 2x ma 1,45x.
LISTINO: dict[str, Prezzi] = {
    "claude-opus-5":    Prezzi(input=5.00,  output=25.00, scrittura_cache_5m=6.25,
                               scrittura_cache_1h=10.00, lettura_cache=0.50),
    "claude-opus-4-8":  Prezzi(input=5.00,  output=25.00, scrittura_cache_5m=6.25,
                               scrittura_cache_1h=10.00, lettura_cache=0.50),
    "claude-sonnet-5":  Prezzi(input=2.00,  output=10.00, scrittura_cache_5m=2.50,
                               scrittura_cache_1h=4.00,  lettura_cache=0.20),
    "claude-haiku-4-5": Prezzi(input=1.00,  output=5.00,  scrittura_cache_5m=1.25,
                               scrittura_cache_1h=2.00,  lettura_cache=0.10),
    "claude-fable-5-1": Prezzi(input=10.00, output=50.00, scrittura_cache_5m=12.50,
                               scrittura_cache_1h=20.00, lettura_cache=0.25),
    "claude-fable-5":   Prezzi(input=10.00, output=50.00, scrittura_cache_5m=12.50,
                               scrittura_cache_1h=20.00, lettura_cache=1.00),
}


def prezzi(modello: str) -> Prezzi:
    if modello in LISTINO:
        return LISTINO[modello]
    raise KeyError(
        f"Prezzi sconosciuti per il modello '{modello}'. Aggiungili in agent/costs.py "
        f"prima di usarlo: senza prezzi il limite di spesa non puo' essere fatto "
        f"rispettare, ed e' meglio fermarsi che far finta. "
        f"Modelli noti: {', '.join(LISTINO)}")


@dataclass
class Consumo:
    """Token consumati, sommati su piu' chiamate."""
    input_tokens: int = 0
    output_tokens: int = 0
    scrittura_cache_5m: int = 0
    scrittura_cache_1h: int = 0
    lettura_cache: int = 0
    chiamate: int = 0

    def aggiungi(self, usage) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.lettura_cache += getattr(usage, "cache_read_input_tokens", 0) or 0

        # L'API distingue le scritture in cache a 5 minuti da quelle a 1 ora,
        # che costano il doppio. Se il dettaglio non c'e' (risposte vecchie o
        # altri fornitori), si usa il totale e lo si conta come 5 minuti — e'
        # la tariffa piu' bassa, quindi il campo dettagliato va preferito
        # quando c'e', per non SOTTOstimare.
        dettaglio = getattr(usage, "cache_creation", None)
        if dettaglio is not None:
            self.scrittura_cache_5m += getattr(dettaglio, "ephemeral_5m_input_tokens", 0) or 0
            self.scrittura_cache_1h += getattr(dettaglio, "ephemeral_1h_input_tokens", 0) or 0
        else:
            self.scrittura_cache_5m += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.chiamate += 1

    def costo(self, modello: str) -> float:
        p = prezzi(modello)
        return (self.input_tokens * p.input
                + self.output_tokens * p.output
                + self.scrittura_cache_5m * p.scrittura_cache_5m
                + self.scrittura_cache_1h * p.scrittura_cache_1h
                + self.lettura_cache * p.lettura_cache) / 1_000_000

    def riassunto(self, modello: str) -> str:
        cache = f"cache scritta {self.scrittura_cache_5m:,}"
        if self.scrittura_cache_1h:
            cache += f" (+{self.scrittura_cache_1h:,} a 1h)"
        return (f"{self.chiamate} chiamate | input {self.input_tokens:,} | {cache} | "
                f"cache letta {self.lettura_cache:,} | output {self.output_tokens:,} | "
                f"costo ${self.costo(modello):.4f}")


class LimiteSpesaSuperato(RuntimeError):
    """Sollevata quando il budget non basta piu'. Ferma tutto."""


@dataclass
class Budget:
    limite_dollari: float
    modello: str
    consumo: Consumo = field(default_factory=Consumo)
    per_problema: dict[str, Consumo] = field(default_factory=dict)

    @property
    def prezzi(self) -> Prezzi:
        return prezzi(self.modello)

    @property
    def speso(self) -> float:
        return self.consumo.costo(self.modello)

    @property
    def residuo(self) -> float:
        return max(0.0, self.limite_dollari - self.speso)

    @property
    def esaurito(self) -> bool:
        return self.speso >= self.limite_dollari

    def registra(self, usage, problema: str = "") -> None:
        self.consumo.aggiungi(usage)
        if problema:
            self.per_problema.setdefault(problema, Consumo()).aggiungi(usage)

    # --- il controllo a priori, quello che rende rigido il limite -----------

    def costo_massimo_possibile(self, token_input: int, max_tokens: int) -> float:
        """Il costo peggiore che una chiamata puo' avere.

        Peggiore davvero:
          * ogni token di ingresso viene contato alla tariffa di SCRITTURA in
            cache, che e' la piu' cara delle tre possibilita' (1,25 volte
            l'input). In pratica una parte sara' letta dalla cache e costera'
            dieci volte meno, ma qui non si scommette;
          * l'uscita viene contata come se il modello riempisse tutto lo spazio
            concessogli da `max_tokens`.
        """
        p = self.prezzi
        return (token_input * p.scrittura_cache_5m + max_tokens * p.output) / 1_000_000

    def verifica_prima_di_chiamare(self, token_input: int, max_tokens: int) -> None:
        """Da chiamare PRIMA di ogni richiesta. Solleva se non ci sta."""
        if self.esaurito:
            raise LimiteSpesaSuperato(
                f"Limite di spesa raggiunto: ${self.speso:.4f} su "
                f"${self.limite_dollari:.2f}. Mi fermo.")
        peggiore = self.costo_massimo_possibile(token_input, max_tokens)
        if peggiore > self.residuo:
            raise LimiteSpesaSuperato(
                f"Non parto: questa chiamata puo' costare fino a ${peggiore:.4f} "
                f"({token_input:,} token in ingresso, fino a {max_tokens:,} in uscita) "
                f"ma restano solo ${self.residuo:.4f} "
                f"(spesi ${self.speso:.4f} su ${self.limite_dollari:.2f}).")

    def max_tokens_sostenibile(self, token_input: int, tetto: int,
                               residuo: float | None = None) -> int:
        """Quanti token di uscita ci si possono ancora permettere.

        Serve per ridurre `max_tokens` invece di fermarsi, quando il residuo e'
        poco ma non nullo. `residuo` permette di passare un limite piu' stretto
        di quello globale, per esempio il tetto di spesa di un singolo problema.
        """
        p = self.prezzi
        disponibile = self.residuo if residuo is None else min(self.residuo, residuo)
        costo_ingresso = token_input * p.scrittura_cache_5m / 1_000_000
        avanzo = disponibile - costo_ingresso
        if avanzo <= 0:
            return 0
        return min(tetto, int(avanzo * 1_000_000 / p.output))

    def riga_stato(self) -> str:
        pct = 100 * self.speso / self.limite_dollari if self.limite_dollari else 0
        return f"[spesa ${self.speso:.4f} / ${self.limite_dollari:.2f}  ({pct:.0f}%)]"
