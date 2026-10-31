"""Strategia: ritorno alla media in mercato laterale (solo con regime compatibile)."""

from __future__ import annotations

from atlas.analysis.snapshot import MarketContext, Snapshot
from atlas.strategy.base import Evaluation, Strategy


class MeanReversion(Strategy):
    name = "mean_reversion"
    version = "1.0.0"
    status = "in_validazione"
    description = (
        "Solo in mercato laterale (ADX basso, timeframe superiore non ribassista): compra un eccesso "
        "sotto la banda di Bollinger inferiore con RSI basso e candela di inversione; target la media mobile centrale."
    )
    regimes = ("laterale",)

    @classmethod
    def param_grid(cls) -> dict:
        return {"rsi_max": [30.0, 35.0]}

    @classmethod
    def default_params(cls) -> dict:
        return {"max_adx": 20.0, "rsi_max": 35.0, "stop_atr": 1.0, "max_stop_atr": 2.5}

    def evaluate(self, ctx: MarketContext) -> Evaluation:
        p, prm = ctx.primary, self.params
        no: list[str] = []
        if p.regime != "laterale" or p.adx >= prm["max_adx"]:
            no.append(f"regime non laterale ({p.regime}, ADX {p.adx:.1f}): la media non è un riferimento affidabile")
        if ctx.higher is not None and ctx.higher.trend == "ribassista":
            no.append("timeframe superiore ribassista: rischio di 'coltello che cade'")
        if not p.low <= p.bb_lower:
            no.append("nessun eccesso sotto la banda di Bollinger inferiore")
        if p.rsi > prm["rsi_max"]:
            no.append(f"RSI {p.rsi:.0f} non in ipervenduto (≤ {prm['rsi_max']:.0f})")
        if not p.close > p.open:
            no.append("nessuna candela di inversione (chiusura non sopra l'apertura)")
        if p.anomaly:
            no.append("movimento anomalo: possibile notizia, non un semplice eccesso")
        if no:
            return Evaluation(None, no)
        stop = max(p.low - prm["stop_atr"] * p.atr, p.close - prm["max_stop_atr"] * p.atr)
        stop = min(stop, p.close - 0.8 * p.atr)
        target = p.bb_mid
        reasons = [
            "mercato laterale con ADX basso",
            f"eccesso sotto la banda inferiore, RSI {p.rsi:.0f}",
            "candela di inversione",
            f"target sulla media centrale {target:.6g}",
        ]
        invalidation = ["passaggio a regime di trend ribassista", f"chiusura sotto lo stop {stop:.6g}"]
        return Evaluation(self._make_signal(ctx, stop, target, reasons, invalidation), reasons)

    def invalidation(self, snap: Snapshot, meta: dict) -> str | None:
        if snap.regime == "trend_ribassista":
            return "il mercato è passato in trend ribassista"
        return None
