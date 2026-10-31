"""Interfaccia comune delle strategie.

Una strategia:
- è identificata da ``name`` + ``version`` (ogni modifica di logica o parametri
  predefiniti richiede una nuova versione);
- produce al massimo un ``Signal`` long per candela chiusa, oppure ``None``
  con le motivazioni del rifiuto;
- definisce le condizioni che invalidano una posizione aperta.

Le strategie NON dimensionano le posizioni e NON eseguono ordini: questo è
compito del risk manager e del motore di esecuzione.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from atlas.analysis.snapshot import MarketContext, Snapshot
from atlas.domain import Signal
from atlas.risk.costs import CostModel, target_for_net_r


@dataclass
class Evaluation:
    signal: Signal | None
    reasons: list[str] = field(default_factory=list)   # perché sì / perché no


class Strategy(ABC):
    name: str = "base"
    version: str = "0"
    status: str = "sperimentale"   # sperimentale | in_validazione | validata | attiva | ritirata
    description: str = ""
    regimes: tuple[str, ...] = ("trend_rialzista", "laterale")   # regimi in cui la strategia ha senso

    def __init__(self, costs: CostModel | None = None, **params) -> None:
        self.costs = costs or CostModel()
        self.params = {**self.default_params(), **params}

    @classmethod
    def default_params(cls) -> dict:
        return {}

    @classmethod
    def param_grid(cls) -> dict:
        """Griglia PICCOLA e fissata a priori per la validazione walk-forward."""
        return {}

    @property
    def id(self) -> str:
        return f"{self.name}@{self.version}"

    @abstractmethod
    def evaluate(self, ctx: MarketContext) -> Evaluation: ...

    @abstractmethod
    def invalidation(self, snap: Snapshot, meta: dict) -> str | None:
        """Motivo di uscita anticipata, oppure None se la tesi è ancora valida."""

    # ------------------------------------------------------------------
    def _make_signal(self, ctx: MarketContext, stop: float, target: float, reasons: list[str], invalidation: list[str]) -> Signal:
        p = ctx.primary
        return Signal(
            symbol=ctx.symbol,
            strategy=self.name,
            strategy_version=self.version,
            bar_timestamp=p.timestamp,
            entry_price=p.close,
            stop_loss=stop,
            take_profit=target,
            atr=p.atr,
            reasons=reasons,
            invalidation=invalidation,
        )

    def net_target(self, ctx: MarketContext, stop: float, r: float) -> float:
        """Target che rende ``r`` volte il rischio, entrambi AL NETTO dei costi stimati."""
        return target_for_net_r(ctx.primary.close, stop, r, self.costs.with_spread(ctx.spread_pct))

    @staticmethod
    def cap_target_at_resistance(snap: Snapshot, target: float) -> tuple[float, str | None]:
        res = snap.structure.nearest_resistance
        if res is not None and res < target and snap.structure.resistance_strength >= 2:
            capped = res - 0.1 * snap.atr
            return capped, f"take profit ridotto sotto la resistenza a {res:.6g}"
        return target, None
