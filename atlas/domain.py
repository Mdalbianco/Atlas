"""Modello dei dati di dominio condiviso tra i moduli."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Action(str, Enum):
    ENTER = "ENTER"      # aprire una nuova posizione long
    SKIP = "SKIP"        # nessuna operazione
    HOLD = "HOLD"        # mantenere la posizione aperta
    EXIT = "EXIT"        # chiudere la posizione


class ExitReason(str, Enum):
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    TAKE_PROFIT = "take_profit"
    INVALIDATION = "invalidation"
    TIME_STOP = "time_stop"
    MANUAL = "manual"
    END_OF_DATA = "end_of_data"   # solo backtest


EXIT_REASON_IT = {
    ExitReason.STOP_LOSS: "Stop loss",
    ExitReason.TRAILING_STOP: "Trailing stop",
    ExitReason.TAKE_PROFIT: "Take profit",
    ExitReason.INVALIDATION: "Segnale invalidato",
    ExitReason.TIME_STOP: "Tempo massimo superato",
    ExitReason.MANUAL: "Chiusura manuale",
    ExitReason.END_OF_DATA: "Fine dati backtest",
}


@dataclass
class Signal:
    """Segnale di ingresso long prodotto da una strategia (non ancora approvato)."""

    symbol: str
    strategy: str
    strategy_version: str
    bar_timestamp: int            # timestamp (ms) di apertura della candela che genera il segnale
    entry_price: float            # prezzo di riferimento (chiusura candela)
    stop_loss: float
    take_profit: float
    atr: float
    reasons: list[str] = field(default_factory=list)
    invalidation: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)   # dati usati dall'invalidazione della strategia

    @property
    def risk_per_unit(self) -> float:
        return self.entry_price - self.stop_loss

    @property
    def gross_reward_risk(self) -> float:
        risk = self.risk_per_unit
        return (self.take_profit - self.entry_price) / risk if risk > 0 else 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScoreResult:
    score: float
    category: str
    components: dict[str, float]
    weights: dict[str, float]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RiskDecision:
    approved: bool
    quantity: float = 0.0
    cost: float = 0.0
    risk_amount: float = 0.0
    risk_pct: float = 0.0
    net_reward_risk: float = 0.0
    estimated_fees: float = 0.0
    reasons: list[str] = field(default_factory=list)   # motivi di rifiuto o note
    checks: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Decision:
    symbol: str
    action: Action
    summary: str
    reasons: list[str] = field(default_factory=list)
    signal: Signal | None = None
    score: ScoreResult | None = None
    risk: RiskDecision | None = None
    strategy: str | None = None
    bar_timestamp: int | None = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action.value,
            "summary": self.summary,
            "reasons": self.reasons,
            "strategy": self.strategy,
            "bar_timestamp": self.bar_timestamp,
            "signal": self.signal.to_dict() if self.signal else None,
            "score": self.score.to_dict() if self.score else None,
            "risk": self.risk.to_dict() if self.risk else None,
        }


@dataclass
class Fill:
    """Esito di un ordine (simulato)."""

    symbol: str
    side: str           # "buy" | "sell"
    quantity: float
    price: float        # prezzo medio eseguito, slippage incluso
    fee: float          # in valuta quotata
    cost: float         # quantity * price
    client_order_id: str
    timestamp: datetime = field(default_factory=utcnow)
    reference_price: float = 0.0


@dataclass
class MarketRules:
    """Vincoli dell'exchange per una coppia."""

    symbol: str
    amount_step: float = 1e-8       # precisione quantità
    price_step: float = 1e-8
    min_amount: float = 0.0
    min_cost: float = 0.0

    def round_amount(self, amount: float) -> float:
        if self.amount_step <= 0:
            return amount
        steps = int(amount / self.amount_step + 1e-9)
        return round(steps * self.amount_step, 12)
