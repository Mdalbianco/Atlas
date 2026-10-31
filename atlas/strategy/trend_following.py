"""Strategia: trend following su incrocio EMA20/EMA50 confermato (cattura i trend lunghi)."""

from __future__ import annotations

from atlas.analysis.snapshot import MarketContext, Snapshot
from atlas.strategy.base import Evaluation, Strategy


class TrendFollowing(Strategy):
    name = "trend_following"
    version = "1.0.0"
    status = "in_validazione"
    description = (
        "Entra quando l'EMA20 incrocia al rialzo l'EMA50 sopra l'EMA200, con ADX in crescita e "
        "timeframe superiore rialzista. Target lontano (4R netti): l'uscita tipica è il trailing stop "
        "o l'incrocio opposto delle medie."
    )
    regimes = ("trend_rialzista",)

    @classmethod
    def param_grid(cls) -> dict:
        return {"target_r": [3.0, 4.0], "stop_atr": [2.0, 2.5]}

    @classmethod
    def default_params(cls) -> dict:
        return {"min_adx": 20.0, "stop_atr": 2.5, "target_r": 4.0, "rsi_max": 72.0}

    def evaluate(self, ctx: MarketContext) -> Evaluation:
        p, prm = ctx.primary, self.params
        no: list[str] = []
        if not p.ema_cross_up:
            no.append("nessun incrocio rialzista EMA20/EMA50 sull'ultima candela")
        if not p.close > p.ema200 or p.ema50 < p.ema200:
            no.append("prezzo o EMA50 sotto l'EMA200: nessun trend di fondo")
        if p.adx < prm["min_adx"] or p.adx_slope <= 0:
            no.append(f"ADX {p.adx:.1f} non sufficiente o non in crescita")
        if ctx.higher is None or ctx.higher.trend != "rialzista":
            no.append("timeframe superiore non rialzista")
        if p.rsi > prm["rsi_max"]:
            no.append(f"RSI {p.rsi:.0f} in ipercomprato")
        if no:
            return Evaluation(None, no)
        stop = p.close - prm["stop_atr"] * p.atr
        target = self.net_target(ctx, stop, prm["target_r"])
        reasons = [
            "incrocio rialzista EMA20/EMA50 sopra l'EMA200",
            f"ADX {p.adx:.0f} in crescita",
            f"timeframe {ctx.higher.timeframe} rialzista",
        ]
        invalidation = ["incrocio ribassista EMA20/EMA50", f"chiusura sotto lo stop {stop:.6g}"]
        return Evaluation(self._make_signal(ctx, stop, target, reasons, invalidation), reasons)

    def invalidation(self, snap: Snapshot, meta: dict) -> str | None:
        if snap.ema20 < snap.ema50:
            return "incrocio ribassista EMA20/EMA50: trend esaurito"
        return None
