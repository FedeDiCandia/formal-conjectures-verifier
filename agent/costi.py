"""
Calcolo dei costi e limite di spesa.

I prezzi vengono dai campi `usage` che l'API restituisce in OGNI risposta:
non sono stime, sono i token effettivamente fatturati.
"""
from __future__ import annotations

from dataclasses import dataclass, field


#: Prezzi in dollari per MILIONE di token (fonte: documentazione API, giugno 2026).
#: - `input`  : token nuovi, non in cache
#: - `output` : token generati (ragionamento compreso)
#: - la SCRITTURA in cache costa 1,25 volte l'input
#: - la LETTURA da cache costa 0,1 volte l'input (uno sconto del 90%)
PREZZI_PER_MILIONE: dict[str, dict[str, float]] = {
    "claude-opus-5":   {"input": 5.00, "output": 25.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-fable-5-1": {"input": 10.00, "output": 50.00},
}

MOLTIPLICATORE_SCRITTURA_CACHE = 1.25
MOLTIPLICATORE_LETTURA_CACHE = 0.10


def prezzi(modello: str) -> dict[str, float]:
    if modello in PREZZI_PER_MILIONE:
        return PREZZI_PER_MILIONE[modello]
    raise KeyError(
        f"Prezzi sconosciuti per il modello '{modello}'. "
        f"Aggiungili in agent/costi.py prima di usarlo, altrimenti il limite di "
        f"spesa non puo' essere fatto rispettare. Modelli noti: "
        f"{', '.join(PREZZI_PER_MILIONE)}")


@dataclass
class Consumo:
    """I token consumati, sommati su piu' chiamate."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    chiamate: int = 0

    def aggiungi(self, usage) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_creation_input_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read_input_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.chiamate += 1

    def costo(self, modello: str) -> float:
        p = prezzi(modello)
        return (
            self.input_tokens * p["input"]
            + self.cache_creation_input_tokens * p["input"] * MOLTIPLICATORE_SCRITTURA_CACHE
            + self.cache_read_input_tokens * p["input"] * MOLTIPLICATORE_LETTURA_CACHE
            + self.output_tokens * p["output"]
        ) / 1_000_000

    def riassunto(self, modello: str) -> str:
        return (f"{self.chiamate} chiamate | "
                f"input {self.input_tokens:,} | "
                f"cache scritta {self.cache_creation_input_tokens:,} | "
                f"cache letta {self.cache_read_input_tokens:,} | "
                f"output {self.output_tokens:,} | "
                f"costo ${self.costo(modello):.4f}")


class LimiteSpesaSuperato(RuntimeError):
    """Sollevata quando il budget e' esaurito. Ferma tutto."""


@dataclass
class Budget:
    """Il salvadanaio. Tiene il conto e blocca quando e' finito.

    Il controllo avviene DOPO ogni risposta (prima non si puo' sapere quanto
    costera'). Per non sforare, si ferma appena la soglia e' raggiunta: la
    chiamata successiva non parte.
    """
    limite_dollari: float
    modello: str
    consumo: Consumo = field(default_factory=Consumo)
    #: consumo separato per problema, per il resoconto finale
    per_problema: dict[str, Consumo] = field(default_factory=dict)

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

    def controlla(self) -> None:
        """Da chiamare PRIMA di ogni richiesta all'API."""
        if self.esaurito:
            raise LimiteSpesaSuperato(
                f"Limite di spesa raggiunto: ${self.speso:.4f} su ${self.limite_dollari:.2f}. "
                f"Mi fermo qui.")

    def riga_stato(self) -> str:
        pct = 100 * self.speso / self.limite_dollari if self.limite_dollari else 0
        return f"[spesa ${self.speso:.4f} / ${self.limite_dollari:.2f}  ({pct:.0f}%)]"
