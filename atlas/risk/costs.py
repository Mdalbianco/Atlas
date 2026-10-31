"""Modello dei costi di esecuzione (commissioni, spread, slippage).

Con capitali piccoli i costi sono decisivi: con commissioni taker dello 0,40%
per lato, un'operazione andata e ritorno costa circa lo 0,8-1,0% del
controvalore. Se lo stop dista l'1,5% dall'ingresso, i soli costi valgono
oltre metà del rischio. Per questo il rapporto rischio/rendimento è sempre
valutato AL NETTO dei costi.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    fee_pct: float = 0.40        # commissione per lato (taker)
    slippage_pct: float = 0.05   # per lato
    spread_pct: float = 0.10     # spread totale bid/ask

    @property
    def per_side_pct(self) -> float:
        """Costo percentuale per lato: commissione + metà spread + slippage."""
        return self.fee_pct + self.spread_pct / 2 + self.slippage_pct

    def entry_price(self, mid: float) -> float:
        return mid * (1 + (self.spread_pct / 2 + self.slippage_pct) / 100)

    def exit_price(self, mid: float) -> float:
        return mid * (1 - (self.spread_pct / 2 + self.slippage_pct) / 100)

    def fee(self, notional: float) -> float:
        return notional * self.fee_pct / 100

    def with_spread(self, spread_pct: float | None) -> "CostModel":
        if spread_pct is None:
            return self
        return CostModel(self.fee_pct, self.slippage_pct, max(spread_pct, 0.0))


def net_reward_risk(entry: float, stop: float, target: float, costs: CostModel) -> tuple[float, float, float]:
    """Rapporto rendimento/rischio netto per unità.

    Restituisce ``(net_rr, net_risk_per_unit, net_reward_per_unit)``: il rischio
    netto include i costi di ingresso e di uscita allo stop; il rendimento
    netto sottrae i costi di ingresso e di uscita al target.
    """
    if not (stop < entry < target):
        return 0.0, 0.0, 0.0
    buy = costs.entry_price(entry)
    buy_cost = buy * (1 + costs.fee_pct / 100)
    sell_stop = costs.exit_price(stop) * (1 - costs.fee_pct / 100)
    sell_target = costs.exit_price(target) * (1 - costs.fee_pct / 100)
    risk = buy_cost - sell_stop
    reward = sell_target - buy_cost
    if risk <= 0:
        return 0.0, risk, reward
    return max(reward, 0.0) / risk, risk, reward
