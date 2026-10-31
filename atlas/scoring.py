"""Motore di scoring interpretabile (0-100).

Il punteggio è una MEDIA PESATA di componenti, ognuno valutato 0-100 con
regole esplicite e documentate in ``docs/SCORING.md``. Il punteggio misura la
qualità del setup *secondo il modello*: NON è una probabilità di profitto.
Pesi e soglie vanno verificati con il backtest (``atlas backtest --score-buckets``)
che riporta il rendimento medio per fascia di punteggio.
"""

from __future__ import annotations

from atlas.analysis.snapshot import MarketContext
from atlas.domain import ScoreResult, Signal
from atlas.risk.costs import CostModel, net_reward_risk

DEFAULT_WEIGHTS: dict[str, float] = {
    "trend": 0.15,
    "momentum": 0.15,
    "volume": 0.10,
    "price_action": 0.10,
    "volatility": 0.10,
    "reward_risk": 0.15,
    "levels": 0.10,
    "timeframes": 0.10,
    "market": 0.05,
}

# (soglia minima inclusa, etichetta) in ordine decrescente
DEFAULT_CATEGORIES: list[tuple[float, str]] = [
    (75.0, "Opportunità di elevata qualità secondo il modello"),
    (65.0, "Opportunità potenzialmente interessante"),
    (55.0, "Opportunità da monitorare"),
    (40.0, "Opportunità debole"),
    (0.0, "Nessuna opportunità"),
]


def classify(score: float, categories: list[tuple[float, str]] = DEFAULT_CATEGORIES) -> str:
    for threshold, label in categories:
        if score >= threshold:
            return label
    return categories[-1][1]


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


class ScoreEngine:
    def __init__(
        self,
        costs: CostModel,
        min_reward_risk: float = 1.8,
        weights: dict[str, float] | None = None,
        categories: list[tuple[float, str]] | None = None,
    ) -> None:
        self.costs = costs
        self.min_rr = min_reward_risk
        self.weights = weights or dict(DEFAULT_WEIGHTS)
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"La somma dei pesi deve essere 1 (attuale {total:.3f})")
        self.categories = categories or DEFAULT_CATEGORIES

    # --- componenti ----------------------------------------------------
    @staticmethod
    def trend(ctx: MarketContext) -> tuple[float, str]:
        p = ctx.primary
        base = {"rialzista": 60.0, "laterale": 30.0, "ribassista": 0.0}[p.trend]
        bonus = min(p.adx, 40) / 40 * 40 if p.trend == "rialzista" else 0.0
        return _clamp(base + bonus), f"trend {p.trend}, ADX {p.adx:.0f}"

    @staticmethod
    def momentum(ctx: MarketContext) -> tuple[float, str]:
        p = ctx.primary
        r = p.rsi
        if 50 <= r <= 65:
            rsi_s = 100.0
        elif 45 <= r < 50 or 65 < r <= 70:
            rsi_s = 65.0
        elif 40 <= r < 45 or 70 < r <= 75:
            rsi_s = 35.0
        else:
            rsi_s = 10.0
        macd_s = {
            "positivo in accelerazione": 100.0,
            "positivo in indebolimento": 55.0,
            "negativo in indebolimento": 40.0,
            "neutro": 30.0,
            "negativo in accelerazione": 0.0,
        }[p.momentum]
        return 0.5 * rsi_s + 0.5 * macd_s, f"RSI {r:.0f}, MACD {p.momentum}"

    @staticmethod
    def volume(ctx: MarketContext) -> tuple[float, str]:
        p = ctx.primary
        rv = p.rel_volume
        s = 90.0 if rv >= 1.5 else 70.0 if rv >= 1.0 else 45.0 if rv >= 0.6 else 20.0
        if p.volume_divergence:
            s -= 25
        return _clamp(s), f"volume x{rv:.1f}" + (" con divergenza" if p.volume_divergence else "")

    @staticmethod
    def price_action(ctx: MarketContext) -> tuple[float, str]:
        st = ctx.primary.structure
        s = {"rialzista": 80.0, "mista": 50.0, "indefinita": 40.0, "ribassista": 10.0}[st.structure]
        if "engulfing_rialzista" in st.candle_patterns or "hammer" in st.candle_patterns:
            s += 10
        if "engulfing_ribassista" in st.candle_patterns or "shooting_star" in st.candle_patterns:
            s -= 20
        if st.breakout or st.pullback_to_ema:
            s += 10
        return _clamp(s), f"struttura {st.structure}"

    def volatility(self, ctx: MarketContext) -> tuple[float, str]:
        p = ctx.primary
        roundtrip = 2 * self.costs.per_side_pct
        a = p.atr_pct
        if a < roundtrip:
            s = 10.0   # movimento tipico inferiore ai costi: i costi dominano
        elif a <= 3.0:
            s = 100.0
        elif a <= 5.0:
            s = 60.0
        else:
            s = 20.0
        if p.regime == "alta_volatilita":
            s -= 30
        if p.anomaly:
            s = 0.0
        return _clamp(s), f"ATR {a:.2f}%"

    def reward_risk(self, signal: Signal, ctx: MarketContext) -> tuple[float, str]:
        costs = self.costs.with_spread(ctx.spread_pct)
        rr, _, _ = net_reward_risk(signal.entry_price, signal.stop_loss, signal.take_profit, costs)
        if rr < self.min_rr:
            s = 100.0 * rr / self.min_rr * 0.4
        else:
            s = 50.0 + 50.0 * min(1.0, (rr - self.min_rr) / max(3.0 - self.min_rr, 0.1))
        return _clamp(s), f"R/R netto {rr:.2f}"

    @staticmethod
    def levels(ctx: MarketContext) -> tuple[float, str]:
        st = ctx.primary.structure
        d = st.dist_resistance_atr
        if d is None:
            s, txt = 75.0, "nessuna resistenza vicina"
        elif d >= 3:
            s, txt = 100.0, f"resistenza a {d:.1f} ATR"
        elif d >= 1.5:
            s, txt = 60.0, f"resistenza a {d:.1f} ATR"
        else:
            s, txt = 15.0, f"resistenza vicina ({d:.1f} ATR)"
        if st.dist_support_atr is not None and st.dist_support_atr <= 1.5 and st.support_strength >= 2:
            s += 10
            txt += ", supporto solido sotto il prezzo"
        return _clamp(s), txt

    @staticmethod
    def timeframes(ctx: MarketContext) -> tuple[float, str]:
        h = ctx.higher
        if h is None:
            return 30.0, "timeframe superiore non disponibile"
        s = {"rialzista": 100.0, "laterale": 50.0, "ribassista": 0.0}[h.trend]
        return s, f"{h.timeframe} {h.trend}"

    @staticmethod
    def market(ctx: MarketContext) -> tuple[float, str]:
        cond = ctx.market_condition
        return {"favorevole": 100.0, "neutra": 50.0, "sfavorevole": 10.0, "sconosciuta": 40.0}[cond], f"mercato {cond}"

    # ------------------------------------------------------------------
    def score(self, signal: Signal, ctx: MarketContext) -> ScoreResult:
        parts = {
            "trend": self.trend(ctx),
            "momentum": self.momentum(ctx),
            "volume": self.volume(ctx),
            "price_action": self.price_action(ctx),
            "volatility": self.volatility(ctx),
            "reward_risk": self.reward_risk(signal, ctx),
            "levels": self.levels(ctx),
            "timeframes": self.timeframes(ctx),
            "market": self.market(ctx),
        }
        components = {k: round(v[0], 1) for k, v in parts.items()}
        total = sum(components[k] * self.weights[k] for k in components)
        total = round(_clamp(total), 1)
        notes = [f"{k}: {v[1]} → {components[k]:.0f}" for k, v in parts.items()]
        return ScoreResult(score=total, category=classify(total, self.categories), components=components, weights=dict(self.weights), notes=notes)
