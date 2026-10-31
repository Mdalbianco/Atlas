"""Strategia: breakout da consolidamento confermato dai volumi."""

from __future__ import annotations

from atlas.analysis.snapshot import MarketContext, Snapshot
from atlas.strategy.base import Evaluation, Strategy


class VolumeBreakout(Strategy):
    name = "breakout"
    version = "1.0.0"
    status = "in_validazione"
    description = (
        "Acquista la rottura del massimo delle ultime 20 candele dopo un consolidamento, "
        "solo con volume relativo elevato e prezzo sopra l'EMA50."
    )

    @classmethod
    def default_params(cls) -> dict:
        return {
            "min_rel_volume": 1.5,
            "max_range_atr": 8.0,
            "max_bar_range_atr": 2.5,
            "rsi_max": 75.0,
            "stop_atr": 1.5,
            "target_r": 2.0,
        }

    def evaluate(self, ctx: MarketContext) -> Evaluation:
        p = ctx.primary
        s = p.structure
        prm = self.params
        no: list[str] = []
        if not s.breakout:
            no.append("nessun breakout del massimo a 20 candele")
        if p.rel_volume < prm["min_rel_volume"]:
            no.append(f"volume non sufficiente a confermare (x{p.rel_volume:.1f} < x{prm['min_rel_volume']:.1f})")
        if s.range_atr > prm["max_range_atr"]:
            no.append("nessun consolidamento precedente: il prezzo era già in forte movimento")
        if p.close < p.ema50:
            no.append("prezzo sotto l'EMA50")
        if p.trend == "ribassista":
            no.append("trend di fondo ribassista")
        if ctx.higher is not None and ctx.higher.trend == "ribassista":
            no.append(f"timeframe {ctx.higher.timeframe} ribassista")
        if p.rsi > prm["rsi_max"]:
            no.append(f"RSI {p.rsi:.0f} in ipercomprato")
        if p.bar_range_atr > prm["max_bar_range_atr"]:
            no.append("candela di breakout troppo estesa: ingresso tardivo")
        if no:
            return Evaluation(None, no)

        level = s.breakout_level or p.close
        stop = min(level - 0.5 * p.atr, p.close - prm["stop_atr"] * p.atr)
        stop = max(stop, p.close - 3 * p.atr)
        target = self.net_target(ctx, stop, prm["target_r"])  # R netti di costi
        target, note = self.cap_target_at_resistance(p, target)
        reasons = [
            f"breakout sopra {level:.6g} dopo consolidamento ({s.range_atr:.1f} ATR)",
            f"volume x{p.rel_volume:.1f} rispetto alla media",
            "prezzo sopra l'EMA50",
        ]
        if note:
            reasons.append(note)
        invalidation = [
            f"ritorno sotto il livello di breakout {level:.6g} (falso breakout)",
            f"chiusura sotto lo stop {stop:.6g}",
        ]
        sig = self._make_signal(ctx, stop, target, reasons, invalidation)
        sig.meta["breakout_level"] = level
        return Evaluation(sig, reasons)

    def invalidation(self, snap: Snapshot, meta: dict) -> str | None:
        level = meta.get("breakout_level")
        bars = int(meta.get("bars_held", 0))
        if level is not None and bars <= 6 and snap.close < level - 0.5 * snap.atr:
            return "falso breakout: chiusura di nuovo sotto il livello rotto"
        return None
