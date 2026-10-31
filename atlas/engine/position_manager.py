"""Regole di gestione delle posizioni aperte (pure, senza I/O).

Ordine delle verifiche, prudente per costruzione:
1. stop loss (prima del take profit se entrambi toccati nella stessa candela);
2. take profit;
3. alla chiusura di una candela del timeframe operativo: trailing stop,
   invalidazione della strategia, stop temporale.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.analysis.snapshot import Snapshot
from atlas.domain import ExitReason
from atlas.strategy.base import Strategy


@dataclass(frozen=True)
class ManagementParams:
    trailing_activation_r: float = 1.0
    trailing_atr_multiple: float = 2.5
    time_stop_bars: int = 48


@dataclass
class ExitSignal:
    reason: ExitReason
    reference_price: float
    detail: str


def check_stop_target(pos: dict, bar_open: float, bar_high: float, bar_low: float) -> ExitSignal | None:
    stop, target = float(pos["stop_loss"]), float(pos["take_profit"])
    stop_reason = ExitReason.TRAILING_STOP if pos.get("trailing_active") else ExitReason.STOP_LOSS
    if bar_open <= stop:
        return ExitSignal(stop_reason, bar_open, f"apertura in gap sotto lo stop ({bar_open:.6g} ≤ {stop:.6g})")
    if bar_low <= stop:
        return ExitSignal(stop_reason, stop, f"prezzo sceso fino a {bar_low:.6g}, stop a {stop:.6g}")
    if bar_open >= target:
        return ExitSignal(ExitReason.TAKE_PROFIT, bar_open, f"apertura sopra il target {target:.6g}")
    if bar_high >= target:
        return ExitSignal(ExitReason.TAKE_PROFIT, target, f"target {target:.6g} raggiunto")
    return None


def on_bar_close(pos: dict, snap: Snapshot, bar_high: float, strategy: Strategy | None, params: ManagementParams) -> tuple[dict, ExitSignal | None]:
    """Aggiorna la posizione alla chiusura di una candela. Restituisce (aggiornamenti, uscita opzionale)."""
    entry = float(pos["entry_price"])
    initial_risk = entry - float(pos["initial_stop"])
    highest = max(float(pos["highest_price"]), float(bar_high))
    bars_held = int(pos.get("bars_held", 0)) + 1
    updates: dict = {"highest_price": highest, "bars_held": bars_held, "last_bar_ts": snap.timestamp}
    stop = float(pos["stop_loss"])

    if initial_risk > 0 and highest - entry >= params.trailing_activation_r * initial_risk:
        new_stop = max(stop, entry, highest - params.trailing_atr_multiple * snap.atr)
        if new_stop > stop:
            updates["stop_loss"] = new_stop
            updates["trailing_active"] = 1
            stop = new_stop

    if snap.close <= stop:
        reason = ExitReason.TRAILING_STOP if updates.get("trailing_active") or pos.get("trailing_active") else ExitReason.STOP_LOSS
        return updates, ExitSignal(reason, snap.close, "chiusura della candela sotto lo stop")

    if strategy is not None:
        meta = dict(pos.get("meta") or {})
        meta["bars_held"] = bars_held
        why = strategy.invalidation(snap, meta)
        if why:
            return updates, ExitSignal(ExitReason.INVALIDATION, snap.close, why)

    if bars_held >= params.time_stop_bars and initial_risk > 0 and highest - entry < initial_risk:
        return updates, ExitSignal(ExitReason.TIME_STOP, snap.close, f"{bars_held} candele senza raggiungere +1R")

    return updates, None
