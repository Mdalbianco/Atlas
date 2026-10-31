"""Analisi live di un simbolo: candele validate → snapshot multi-timeframe."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from atlas.analysis.indicators import add_indicators
from atlas.analysis.snapshot import MarketContext, Snapshot, build_snapshot
from atlas.data.market_data import DataQualityReport, MarketDataService


@dataclass
class SymbolAnalysis:
    ctx: MarketContext
    primary_df: pd.DataFrame        # candele chiuse con indicatori
    ticker: dict
    quality: DataQualityReport


class Analyzer:
    def __init__(self, market: MarketDataService, timeframe: str, higher_timeframe: str, limit: int, max_bar_move_atr: float) -> None:
        self.market = market
        self.tf = timeframe
        self.htf = higher_timeframe
        self.limit = limit
        self.max_bar_move_atr = max_bar_move_atr

    def snapshot(self, symbol: str, timeframe: str) -> tuple[Snapshot, pd.DataFrame, DataQualityReport]:
        df, quality = self.market.candles(symbol, timeframe, self.limit)
        enriched = add_indicators(df)
        return build_snapshot(symbol, timeframe, df, self.max_bar_move_atr, enriched=enriched), enriched, quality

    def analyze(self, symbol: str, market_snapshot: Snapshot | None = None) -> SymbolAnalysis:
        primary, enriched, quality = self.snapshot(symbol, self.tf)
        higher, _, _ = self.snapshot(symbol, self.htf)
        ticker = self.market.ticker(symbol)
        ctx = MarketContext(symbol, primary, higher, market=market_snapshot, spread_pct=ticker.get("spread_pct"))
        return SymbolAnalysis(ctx, enriched, ticker, quality)


def correlations(target: pd.DataFrame, others: dict[str, pd.DataFrame], window: int = 168) -> dict[str, float]:
    """Correlazione dei rendimenti (ultime ``window`` candele) tra ``target`` e ogni altra serie."""
    out = {}
    a = target.set_index("timestamp")["close"].pct_change().tail(window)
    for sym, df in others.items():
        b = df.set_index("timestamp")["close"].pct_change().tail(window)
        joined = pd.concat([a, b], axis=1, join="inner").dropna()
        if len(joined) > 20:
            c = float(np.corrcoef(joined.iloc[:, 0], joined.iloc[:, 1])[0, 1])
            out[sym] = c
    return out
