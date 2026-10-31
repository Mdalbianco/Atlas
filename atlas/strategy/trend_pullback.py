"""Strategia: ritracciamento in trend rialzista (trend following)."""

from __future__ import annotations

from atlas.analysis.snapshot import MarketContext, Snapshot
from atlas.strategy.base import Evaluation, Strategy


class TrendPullback(Strategy):
    name = "trend_pullback"
    version = "1.0.0"
    status = "in_validazione"
    regimes = ("trend_rialzista", "laterale")
    description = (
        "Acquista in un trend rialzista confermato (EMA20>EMA50>EMA200, ADX sufficiente) "
        "dopo un ritracciamento verso l'EMA20, quando il momentum riprende."
    )

    @classmethod
    def param_grid(cls) -> dict:
        return {"target_r": [2.0, 2.5]}

    @classmethod
    def default_params(cls) -> dict:
        return {
            "min_adx": 18.0,
            "rsi_min": 40.0,
            "rsi_max": 68.0,
            "stop_atr": 1.5,
            "target_r": 2.5,
            "require_higher_trend": True,
        }

    def evaluate(self, ctx: MarketContext) -> Evaluation:
        p = ctx.primary
        prm = self.params
        no: list[str] = []
        if p.trend != "rialzista":
            no.append(f"trend {p.trend} sul {p.timeframe}: la strategia opera solo in trend rialzista")
        if p.adx < prm["min_adx"]:
            no.append(f"forza del trend insufficiente (ADX {p.adx:.1f} < {prm['min_adx']:.1f})")
        if prm["require_higher_trend"] and (ctx.higher is None or ctx.higher.trend == "ribassista"):
            no.append("timeframe superiore non compatibile (ribassista o non disponibile)")
        if not p.structure.pullback_to_ema:
            no.append("nessun ritracciamento recente verso l'EMA20")
        if not (prm["rsi_min"] <= p.rsi <= prm["rsi_max"]):
            no.append(f"RSI {p.rsi:.0f} fuori dall'intervallo {prm['rsi_min']:.0f}-{prm['rsi_max']:.0f}")
        if p.macd_hist <= p.macd_hist_prev:
            no.append("momentum non in ripresa (istogramma MACD non in aumento)")
        if no:
            return Evaluation(None, no)

        recent_low = min(p.structure.swing_lows[-1] if p.structure.swing_lows else p.close, p.close - prm["stop_atr"] * p.atr)
        stop = max(recent_low - 0.2 * p.atr, p.close - 3 * p.atr)  # mai oltre 3 ATR
        stop = min(stop, p.close - 1.0 * p.atr)                       # mai sotto 1 ATR di distanza
        target = self.net_target(ctx, stop, prm["target_r"])  # R netti di costi
        target, note = self.cap_target_at_resistance(p, target)
        reasons = [
            f"trend rialzista sul {p.timeframe} (ADX {p.adx:.0f})",
            "ritracciamento sull'EMA20 con ripresa del momentum",
            f"RSI {p.rsi:.0f} non in ipercomprato",
        ]
        if ctx.higher is not None:
            reasons.append(f"timeframe {ctx.higher.timeframe}: trend {ctx.higher.trend}")
        if note:
            reasons.append(note)
        invalidation = [
            f"chiusura sotto lo stop {stop:.6g}",
            "chiusura sotto l'EMA50 con trend non più rialzista",
            "inversione del timeframe superiore a ribassista",
        ]
        return Evaluation(self._make_signal(ctx, stop, target, reasons, invalidation), reasons)

    def invalidation(self, snap: Snapshot, meta: dict) -> str | None:
        if snap.close < snap.ema50 and snap.trend != "rialzista":
            return "prezzo sotto l'EMA50 e trend non più rialzista"
        return None
