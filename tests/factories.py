from dataclasses import replace

from atlas.analysis.snapshot import MarketContext, Snapshot
from atlas.analysis.structure import StructureResult


def structure(**kw) -> StructureResult:
    base = dict(
        structure="rialzista", swing_highs=[105.0, 110.0], swing_lows=[95.0, 98.0],
        nearest_support=98.0, support_strength=2, nearest_resistance=None, resistance_strength=0,
        dist_support_atr=1.0, dist_resistance_atr=None, breakout=False, breakout_level=101.0,
        consolidation=False, range_atr=6.0, pullback_to_ema=True, candle_patterns=[],
    )
    base.update(kw)
    return StructureResult(**base)


def snap(**kw) -> Snapshot:
    st = kw.pop("structure", None) or structure()
    base = dict(
        symbol="BTC/EUR", timeframe="1h", timestamp=1_700_000_000_000, close=100.0, ema20=99.0, ema50=97.0, ema200=90.0,
        rsi=57.0, macd=0.5, macd_signal=0.3, macd_hist=0.2, macd_hist_prev=0.1, atr=2.0, atr_pct=2.0, atr_pct_median=2.0,
        adx=28.0, rel_volume=1.2, volatility=1.0, change_pct=0.5, change_24_pct=2.0, bar_range_atr=1.0,
        trend="rialzista", trend_strength=56.0, momentum="positivo in accelerazione", volume_state="normale",
        volume_divergence=False, regime="trend_rialzista", anomaly=False, anomaly_reason=None, structure=st,
    )
    base.update(kw)
    return Snapshot(**base)


def ctx(primary=None, higher=None, market=None, spread=0.05) -> MarketContext:
    p = primary or snap()
    h = higher if higher is not None else snap(timeframe="4h")
    return MarketContext(p.symbol, p, h, market=market, spread_pct=spread)
