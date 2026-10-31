"""Fotografia interpretata del mercato su un timeframe, più combinazione multi-timeframe."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from atlas.analysis.indicators import ArrayFrame, add_indicators
from atlas.analysis.structure import StructureResult, analyze_structure

MIN_BARS = 210  # EMA200 + margine


@dataclass
class Snapshot:
    symbol: str
    timeframe: str
    timestamp: int
    close: float
    ema20: float
    ema50: float
    ema200: float
    rsi: float
    macd: float
    macd_signal: float
    macd_hist: float
    macd_hist_prev: float
    atr: float
    atr_pct: float
    atr_pct_median: float
    adx: float
    rel_volume: float
    volatility: float
    change_pct: float
    change_24_pct: float
    bar_range_atr: float
    trend: str                # rialzista | ribassista | laterale
    trend_strength: float     # 0-100 (ADX normalizzato)
    momentum: str
    volume_state: str
    volume_divergence: bool
    regime: str               # trend_rialzista | trend_ribassista | laterale | alta_volatilita
    anomaly: bool
    anomaly_reason: str | None
    structure: StructureResult
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["structure"] = self.structure.to_dict()
        return d


def _f(value, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return default if np.isnan(v) else v


def classify_trend(close: float, ema20: float, ema50: float, ema200: float, slope: float) -> str:
    if close > ema50 > ema200 and ema20 > ema50 and slope > 0:
        return "rialzista"
    if close < ema50 < ema200 and ema20 < ema50 and slope < 0:
        return "ribassista"
    return "laterale"


def build_snapshot(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame | ArrayFrame,
    max_bar_move_atr: float = 4.0,
    enriched: pd.DataFrame | ArrayFrame | None = None,
) -> Snapshot:
    """Analizza ``df`` (candele chiuse) all'ultima candela.

    ``enriched`` permette di passare un DataFrame con indicatori già calcolati
    (usato dal backtest per efficienza); deve corrispondere a ``df``.
    """
    if len(df) < MIN_BARS:
        raise ValueError(f"Servono almeno {MIN_BARS} candele chiuse per l'analisi ({len(df)} disponibili)")
    data = enriched if enriched is not None else add_indicators(df)
    if isinstance(data, pd.DataFrame):
        data = ArrayFrame.from_frame(data)

    def col(name: str) -> np.ndarray:
        return data[name]

    def last(name: str, default: float = 0.0, offset: int = 1) -> float:
        return _f(data[name][-offset], default)

    close = last("close")
    ema20, ema50, ema200 = last("ema20"), last("ema50"), last("ema200")
    slope = last("ema50_slope")
    trend = classify_trend(close, ema20, ema50, ema200, slope)
    adx_v = last("adx")
    hist, hist_prev = last("macd_hist"), last("macd_hist", offset=2)

    if hist > 0:
        momentum = "positivo in accelerazione" if hist > hist_prev else "positivo in indebolimento"
    elif hist < 0:
        momentum = "negativo in accelerazione" if hist < hist_prev else "negativo in indebolimento"
    else:
        momentum = "neutro"

    rel_vol = last("rel_volume", 1.0)
    volume_state = "alto" if rel_vol >= 1.5 else "basso" if rel_vol <= 0.6 else "normale"
    closes = col("close")
    price_up = closes[-1] > closes[max(0, len(closes) - 11)]
    obv_slope = last("obv_slope")
    volume_divergence = bool((price_up and obv_slope < 0) or (not price_up and obv_slope > 0))

    atr_pct = last("atr_pct")
    atr_med = _f(np.nanmedian(col("atr_pct")[-100:]), atr_pct)
    prev_atr_pct = last("atr_pct", atr_pct, offset=2)
    change = last("change_pct")
    anomaly_reason = None
    if prev_atr_pct > 0 and abs(change) > max_bar_move_atr * prev_atr_pct:
        anomaly_reason = f"movimento anomalo dell'ultima candela ({change:+.2f}%, oltre {max_bar_move_atr:.0f}x ATR)"
    elif last("volume") <= 0:
        anomaly_reason = "volume nullo sull'ultima candela"
    elif atr_med > 0 and atr_pct > 3 * atr_med:
        anomaly_reason = f"volatilità estrema (ATR {atr_pct:.2f}% contro mediana {atr_med:.2f}%)"

    if atr_med > 0 and atr_pct > 2 * atr_med:
        regime = "alta_volatilita"
    elif adx_v >= 20 and trend == "rialzista":
        regime = "trend_rialzista"
    elif adx_v >= 20 and trend == "ribassista":
        regime = "trend_ribassista"
    else:
        regime = "laterale"

    lookback_24 = closes[-25] if len(closes) > 25 else closes[0]
    structure = analyze_structure(data)

    return Snapshot(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=int(data["timestamp"][-1]),
        close=close,
        ema20=ema20,
        ema50=ema50,
        ema200=ema200,
        rsi=last("rsi", 50.0),
        macd=last("macd"),
        macd_signal=last("macd_signal"),
        macd_hist=hist,
        macd_hist_prev=hist_prev,
        atr=last("atr"),
        atr_pct=atr_pct,
        atr_pct_median=atr_med,
        adx=adx_v,
        rel_volume=rel_vol,
        volatility=last("volatility"),
        change_pct=change,
        change_24_pct=(close / float(lookback_24) - 1) * 100,
        bar_range_atr=last("bar_range_atr"),
        trend=trend,
        trend_strength=min(100.0, adx_v * 2),
        momentum=momentum,
        volume_state=volume_state,
        volume_divergence=volume_divergence,
        regime=regime,
        anomaly=anomaly_reason is not None,
        anomaly_reason=anomaly_reason,
        structure=structure,
    )


@dataclass
class MarketContext:
    """Tutto ciò che una strategia può vedere per un simbolo in un istante."""

    symbol: str
    primary: Snapshot
    higher: Snapshot | None
    market: Snapshot | None = None    # riferimento generale (es. BTC sul timeframe superiore)
    spread_pct: float | None = None

    @property
    def timeframes_aligned(self) -> bool:
        return self.higher is not None and self.higher.trend == "rialzista" and self.primary.trend == "rialzista"

    @property
    def market_condition(self) -> str:
        ref = self.market or self.higher
        if ref is None:
            return "sconosciuta"
        if ref.trend == "rialzista":
            return "favorevole"
        if ref.trend == "ribassista":
            return "sfavorevole"
        return "neutra"
