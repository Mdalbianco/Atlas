"""Strategia: espansione di volatilità dopo una compressione (momentum + volatilità)."""

from __future__ import annotations

from atlas.analysis.snapshot import MarketContext, Snapshot
from atlas.strategy.base import Evaluation, Strategy


class VolatilitySqueeze(Strategy):
    name = "volatility_squeeze"
    version = "1.0.0"
    status = "in_validazione"
    description = (
        "Dopo una compressione delle bande di Bollinger (larghezza nel 20% più basso delle ultime 120 candele) "
        "entra alla prima chiusura sopra la banda superiore con volume in aumento e trend non ribassista."
    )
    regimes = ("laterale", "trend_rialzista")

    @classmethod
    def param_grid(cls) -> dict:
        return {"target_r": [2.0, 2.5]}

    @classmethod
    def default_params(cls) -> dict:
        return {"max_width_rank": 0.20, "min_rel_volume": 1.2, "stop_atr": 1.5, "target_r": 2.0, "rsi_max": 75.0}

    def evaluate(self, ctx: MarketContext) -> Evaluation:
        p, prm = ctx.primary, self.params
        no: list[str] = []
        if p.bb_width_rank_prev > prm["max_width_rank"]:
            no.append("nessuna compressione di volatilità nella candela precedente")
        if not p.close > p.bb_upper:
            no.append("nessuna chiusura sopra la banda superiore")
        if p.rel_volume < prm["min_rel_volume"]:
            no.append(f"volume insufficiente (x{p.rel_volume:.1f})")
        if p.trend == "ribassista" or (ctx.higher is not None and ctx.higher.trend == "ribassista"):
            no.append("trend ribassista su uno dei timeframe")
        if p.rsi > prm["rsi_max"]:
            no.append(f"RSI {p.rsi:.0f} in ipercomprato")
        if no:
            return Evaluation(None, no)
        stop = min(p.bb_mid, p.close - prm["stop_atr"] * p.atr)
        stop = max(stop, p.close - 3 * p.atr)
        target = self.net_target(ctx, stop, prm["target_r"])
        target, note = self.cap_target_at_resistance(p, target)
        reasons = ["uscita da una compressione di volatilità", "chiusura sopra la banda superiore", f"volume x{p.rel_volume:.1f}"]
        if note:
            reasons.append(note)
        invalidation = ["ritorno sotto la media centrale delle bande", f"chiusura sotto lo stop {stop:.6g}"]
        return Evaluation(self._make_signal(ctx, stop, target, reasons, invalidation), reasons)

    def invalidation(self, snap: Snapshot, meta: dict) -> str | None:
        if int(meta.get("bars_held", 0)) <= 6 and snap.close < snap.bb_mid:
            return "espansione fallita: ritorno sotto la media centrale"
        return None
