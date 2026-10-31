"""Price action, supporti/resistenze e pattern di candele.

I pivot (massimi/minimi locali) di ordine ``k`` richiedono ``k`` candele
successive per essere confermati: un pivot all'indice ``j`` viene usato solo
quando l'analisi è all'indice ``>= j + k``. In questo modo non si usa mai il
futuro (il vecchio prototipo usava finestre centrate).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Level:
    price: float
    touches: int
    kind: str  # "support" | "resistance"


@dataclass
class StructureResult:
    structure: str                 # "rialzista" | "ribassista" | "mista" | "indefinita"
    swing_highs: list[float]
    swing_lows: list[float]
    nearest_support: float | None
    support_strength: int
    nearest_resistance: float | None
    resistance_strength: int
    dist_support_atr: float | None
    dist_resistance_atr: float | None
    breakout: bool
    breakout_level: float | None
    consolidation: bool
    range_atr: float
    pullback_to_ema: bool
    candle_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def confirmed_pivots(high: np.ndarray, low: np.ndarray, k: int = 3) -> tuple[list[int], list[int]]:
    """Indici dei pivot alti/bassi confermati entro l'ultima candela disponibile.

    Un pivot all'indice ``j`` è il massimo (minimo) stretto della finestra
    ``[j-k, j+k]``: serve che esistano ``k`` candele successive già chiuse.
    """
    n = len(high)
    if n < 2 * k + 1:
        return [], []
    from numpy.lib.stride_tricks import sliding_window_view

    wh = sliding_window_view(high, 2 * k + 1)
    wl = sliding_window_view(low, 2 * k + 1)
    center_h = high[k : n - k]
    center_l = low[k : n - k]
    is_h = (center_h == wh.max(axis=1)) & ((wh == center_h[:, None]).sum(axis=1) == 1)
    is_l = (center_l == wl.min(axis=1)) & ((wl == center_l[:, None]).sum(axis=1) == 1)
    idx = np.arange(k, n - k)
    return idx[is_h].tolist(), idx[is_l].tolist()


def cluster_levels(prices: list[float], tolerance: float, kind: str) -> list[Level]:
    if not prices:
        return []
    groups: list[list[float]] = []   # [somma, conteggio]
    for p in sorted(prices):
        if groups and abs(p - groups[-1][0] / groups[-1][1]) <= tolerance:
            groups[-1][0] += p
            groups[-1][1] += 1
        else:
            groups.append([p, 1])
    return [Level(price=float(total / n), touches=int(n), kind=kind) for total, n in groups]


def candle_patterns(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> list[str]:
    """Pattern sulle ultime due candele (array numpy open/high/low/close)."""
    if len(c) < 2:
        return []
    po, pc = o[-2], c[-2]
    co, ch, cl, cc = o[-1], h[-1], l[-1], c[-1]
    patterns = []
    body = abs(cc - co)
    rng = max(ch - cl, 1e-12)
    lower_wick = min(co, cc) - cl
    upper_wick = ch - max(co, cc)
    if cc > co and pc < po and cc >= po and co <= pc:
        patterns.append("engulfing_rialzista")
    if cc < co and pc > po and co >= pc and cc <= po:
        patterns.append("engulfing_ribassista")
    if lower_wick >= 2 * body and upper_wick <= body and (cc - cl) / rng >= 0.6:
        patterns.append("hammer")
    if upper_wick >= 2 * body and lower_wick <= body and (ch - cc) / rng >= 0.6:
        patterns.append("shooting_star")
    return patterns


def analyze_structure(df, lookback: int = 150, pivot_order: int = 3, breakout_lookback: int = 20) -> StructureResult:
    """Analizza la struttura di prezzo all'ultima candela di ``df`` (che deve contenere ``atr`` ed ``ema20``)."""
    start = max(0, len(df) - lookback)
    high = np.asarray(df["high"])[start:]
    low = np.asarray(df["low"])[start:]
    opens = np.asarray(df["open"])[start:]
    closes = np.asarray(df["close"])[start:]
    ema20_arr = np.asarray(df["ema20"])[start:]
    close = float(closes[-1])
    atr_last = float(np.asarray(df["atr"])[-1])
    atr_value = atr_last if not np.isnan(atr_last) else close * 0.01
    atr_value = max(atr_value, close * 1e-4)

    hi_idx, lo_idx = confirmed_pivots(high, low, pivot_order)
    swing_highs = [float(high[i]) for i in hi_idx]
    swing_lows = [float(low[i]) for i in lo_idx]

    structure = "indefinita"
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        hh = swing_highs[-1] > swing_highs[-2]
        hl = swing_lows[-1] > swing_lows[-2]
        lh = swing_highs[-1] < swing_highs[-2]
        ll = swing_lows[-1] < swing_lows[-2]
        if hh and hl:
            structure = "rialzista"
        elif lh and ll:
            structure = "ribassista"
        else:
            structure = "mista"

    tolerance = 0.5 * atr_value
    levels = cluster_levels(swing_highs, tolerance, "resistance") + cluster_levels(swing_lows, tolerance, "support")
    above = [lv for lv in levels if lv.price > close]
    below = [lv for lv in levels if lv.price <= close]
    res = min(above, key=lambda lv: lv.price) if above else None
    sup = max(below, key=lambda lv: lv.price) if below else None
    # la forza di un livello conta tutti i pivot (alti e bassi) vicini
    def strength(lv: Level | None) -> int:
        if lv is None:
            return 0
        return sum(1 for p in swing_highs + swing_lows if abs(p - lv.price) <= tolerance)

    if len(high) > breakout_lookback:
        prior_h = high[-breakout_lookback - 1 : -1]
        prior_l = low[-breakout_lookback - 1 : -1]
        breakout_level = float(prior_h.max())
        range_atr = float((prior_h.max() - prior_l.min()) / atr_value)
    else:
        breakout_level, range_atr = None, 0.0
    prev_close = float(closes[-2]) if len(closes) > 1 else close
    breakout = bool(breakout_level is not None and close > breakout_level and prev_close <= breakout_level)
    consolidation = range_atr < 5.0

    pullback = bool(
        not np.isnan(ema20_arr[-1])
        and (low[-3:] <= ema20_arr[-3:] + 0.5 * atr_value).any()
        and close > float(ema20_arr[-1])
    )

    return StructureResult(
        structure=structure,
        swing_highs=swing_highs[-5:],
        swing_lows=swing_lows[-5:],
        nearest_support=sup.price if sup else None,
        support_strength=strength(sup),
        nearest_resistance=res.price if res else None,
        resistance_strength=strength(res),
        dist_support_atr=(close - sup.price) / atr_value if sup else None,
        dist_resistance_atr=(res.price - close) / atr_value if res else None,
        breakout=breakout,
        breakout_level=breakout_level,
        consolidation=consolidation,
        range_atr=range_atr,
        pullback_to_ema=pullback,
        candle_patterns=candle_patterns(opens, high, low, closes),
    )
