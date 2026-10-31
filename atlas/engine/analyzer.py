"""Analisi live di un simbolo: candele validate → snapshot multi-timeframe."""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np
import pandas as pd

from atlas.analysis.indicators import add_indicators
from atlas.analysis.snapshot import MarketContext, Snapshot, build_snapshot
from atlas.data.market_data import DataQualityReport, MarketDataService, timeframe_ms


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
        self._cache: dict[tuple[str, str], tuple] = {}
        self._lock = threading.Lock()
        self.fetches = 0

    def snapshot(self, symbol: str, timeframe: str) -> tuple[Snapshot, pd.DataFrame, DataQualityReport]:
        """Snapshot dell'ultima candela chiusa.

        Le candele vengono riscaricate solo quando è attesa una candela nuova
        (ultima chiusa ``L`` → la successiva chiude a ``L + 2·timeframe``): tra una
        chiusura e l'altra il risultato non può cambiare, quindi la cache è esatta.
        """
        key = (symbol, timeframe)
        tf = timeframe_ms(timeframe)
        now = self.market.clock()
        with self._lock:
            cached = self._cache.get(key)
        if cached is not None and now < cached[0] + 2 * tf:
            return cached[1], cached[2], cached[3]
        df, quality = self.market.candles(symbol, timeframe, self.limit)
        self.fetches += 1
        enriched = add_indicators(df)
        snap = build_snapshot(symbol, timeframe, df, self.max_bar_move_atr, enriched=enriched)
        with self._lock:
            self._cache[key] = (int(df["timestamp"].iloc[-1]), snap, enriched, quality)
        return snap, enriched, quality

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
