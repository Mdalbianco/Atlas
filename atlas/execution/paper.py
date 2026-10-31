"""Esecuzione SIMULATA. Nessuna chiamata di rete, nessun ordine reale.

Il modello di riempimento applica a ogni ordine:
- metà spread (dal book reale se disponibile, altrimenti un valore prudente);
- slippage configurabile;
- commissione taker sul controvalore;
- arrotondamento della quantità al passo dell'exchange;
- controllo del saldo disponibile e dei minimi d'ordine.

Gli stop vengono simulati come ordini a mercato che scattano al livello di
stop: se il prezzo "salta" oltre lo stop (gap), il riempimento avviene al
prezzo peggiore effettivamente osservato, non allo stop.
"""

from __future__ import annotations

import hashlib

from atlas.domain import Fill, MarketRules
from atlas.risk.costs import CostModel


class OrderRejected(ValueError):
    pass


def make_client_order_id(*parts: object) -> str:
    """ID deterministico: lo stesso segnale produce sempre lo stesso ID (idempotenza)."""
    raw = "|".join(str(p) for p in parts)
    return "atlas-" + hashlib.sha256(raw.encode()).hexdigest()[:24]


class PaperBroker:
    mode = "paper"

    def __init__(self, costs: CostModel) -> None:
        self.costs = costs

    def buy(self, symbol: str, quantity: float, reference_price: float, cash: float, rules: MarketRules, client_order_id: str, spread_pct: float | None = None) -> Fill:
        costs = self.costs.with_spread(spread_pct)
        qty = rules.round_amount(quantity)
        if qty <= 0 or qty < rules.min_amount:
            raise OrderRejected(f"quantità {qty} sotto il minimo {rules.min_amount}")
        price = costs.entry_price(reference_price)
        notional = qty * price
        if notional < rules.min_cost:
            raise OrderRejected(f"controvalore {notional:.2f} sotto il minimo {rules.min_cost}")
        fee = costs.fee(notional)
        if notional + fee > cash + 1e-9:
            raise OrderRejected(f"saldo insufficiente: servono {notional + fee:.2f}, disponibili {cash:.2f}")
        return Fill(symbol, "buy", qty, price, fee, notional, client_order_id, reference_price=reference_price)

    def sell(self, symbol: str, quantity: float, reference_price: float, client_order_id: str, spread_pct: float | None = None) -> Fill:
        costs = self.costs.with_spread(spread_pct)
        if quantity <= 0:
            raise OrderRejected("quantità di vendita non valida")
        price = costs.exit_price(reference_price)
        notional = quantity * price
        return Fill(symbol, "sell", quantity, price, costs.fee(notional), notional, client_order_id, reference_price=reference_price)
