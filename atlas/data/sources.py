"""Fonti dati alternative a Kraken live: file CSV storici e dati sintetici.

- ``load_csv``: legge sia il formato ATLAS (con intestazione) sia i file
  OHLCVT ufficiali scaricabili da Kraken (senza intestazione, timestamp in
  secondi: ``time,open,high,low,close,volume,trades``). L'endpoint OHLC di
  Kraken restituisce solo le ultime ~720 candele: per backtest lunghi usare i
  file storici ufficiali.
- ``SyntheticMarket``: generatore deterministico (seed) con regimi di trend,
  laterali e volatilità variabile. Serve SOLO per test e demo: non dimostra
  nulla sulla redditività reale di una strategia.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from atlas.data.market_data import COLUMNS, timeframe_ms, to_dataframe
from atlas.domain import MarketRules


def load_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        first = fh.readline()
    has_header = any(c.isalpha() for c in first)
    if has_header:
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        if "time" in df.columns and "timestamp" not in df.columns:
            df = df.rename(columns={"time": "timestamp"})
    else:
        raw = pd.read_csv(path, header=None)
        df = raw.iloc[:, :6]
        df.columns = COLUMNS
    df = df[COLUMNS]
    ts = pd.to_numeric(df["timestamp"], errors="coerce")
    if ts.max() < 10**11:  # secondi -> millisecondi
        ts = ts * 1000
    df = df.assign(timestamp=ts.astype("int64"))
    return to_dataframe(df.values.tolist())


def resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Aggrega candele in un timeframe superiore (solo gruppi completi)."""
    tf = timeframe_ms(timeframe)
    base_tf = int(np.median(np.diff(df["timestamp"].to_numpy()))) if len(df) > 1 else tf
    per_group = max(1, tf // base_tf)
    bucket = (df["timestamp"] // tf) * tf
    grouped = df.groupby(bucket)
    out = pd.DataFrame(
        {
            "timestamp": grouped["timestamp"].first().index.astype("int64"),
            "open": grouped["open"].first().to_numpy(),
            "high": grouped["high"].max().to_numpy(),
            "low": grouped["low"].min().to_numpy(),
            "close": grouped["close"].last().to_numpy(),
            "volume": grouped["volume"].sum().to_numpy(),
            "_n": grouped.size().to_numpy(),
        }
    )
    out = out[out["_n"] >= per_group].drop(columns="_n").reset_index(drop=True)
    return out


class SyntheticMarket:
    """Mercato sintetico deterministico che implementa ``MarketDataSource``."""

    def __init__(
        self,
        symbols: dict[str, float] | None = None,
        bars: int = 2000,
        timeframe: str = "1h",
        seed: int = 42,
        end_ms: int | None = None,
        spread_pct: float = 0.06,
    ) -> None:
        self.symbols = symbols or {"BTC/EUR": 60000.0, "ETH/EUR": 3000.0, "SOL/EUR": 150.0}
        # Se impostato, il mercato "rivela" solo le candele iniziate prima di now_ms
        # (replay): l'ultima è in formazione, come sull'exchange reale.
        self.now_ms: int | None = None
        self.timeframe = timeframe
        self.spread_pct = spread_pct
        tf = timeframe_ms(timeframe)
        end_ms = end_ms or (pd.Timestamp.now(tz="UTC").floor("h").value // 1_000_000)
        start = end_ms - bars * tf
        rng = np.random.default_rng(seed)
        common = self._regime_returns(rng, bars)
        self.data: dict[str, pd.DataFrame] = {}
        for i, (symbol, price0) in enumerate(self.symbols.items()):
            own = self._regime_returns(np.random.default_rng(seed + 1000 + i), bars)
            beta = 1.0 if i == 0 else 0.7
            rets = beta * common + (0.6 if i else 0.0) * own
            self.data[symbol] = self._build(rng, rets, price0, start, tf)

    @staticmethod
    def _regime_returns(rng: np.random.Generator, n: int) -> np.ndarray:
        out = np.empty(n)
        i = 0
        while i < n:
            length = int(rng.integers(80, 300))
            regime = rng.choice(["up", "down", "range"], p=[0.4, 0.3, 0.3])
            drift = {"up": 0.0012, "down": -0.0010, "range": 0.0}[regime]
            vol = float(rng.uniform(0.004, 0.012))
            seg = rng.normal(drift, vol, size=min(length, n - i))
            if regime == "range":
                seg = seg - seg.mean()
            out[i : i + len(seg)] = seg
            i += len(seg)
        return out

    @staticmethod
    def _build(rng, rets, price0, start, tf) -> pd.DataFrame:
        closes = price0 * np.exp(np.cumsum(rets))
        opens = np.concatenate([[price0], closes[:-1]])
        wick = np.abs(rng.normal(0, 0.003, size=len(rets)))
        highs = np.maximum(opens, closes) * (1 + wick)
        lows = np.minimum(opens, closes) * (1 - np.abs(rng.normal(0, 0.003, size=len(rets))))
        volume = rng.lognormal(mean=3, sigma=0.4, size=len(rets)) * (1 + 40 * np.abs(rets))
        ts = start + np.arange(len(rets), dtype="int64") * tf
        return pd.DataFrame({"timestamp": ts, "open": opens, "high": highs, "low": lows, "close": closes, "volume": volume})

    # --- interfaccia MarketDataSource ------------------------------------
    def _visible(self, symbol: str) -> pd.DataFrame:
        df = self.data[symbol]
        if self.now_ms is not None:
            df = df[df["timestamp"] <= self.now_ms]
            # la candela in formazione è appena iniziata: si conosce solo l'apertura
            forming = df["timestamp"] + timeframe_ms(self.timeframe) > self.now_ms
            if forming.any():
                df = df.copy()
                o = df.loc[forming, "open"]
                df.loc[forming, ["high", "low", "close"]] = np.column_stack([o, o, o])
                df.loc[forming, "volume"] = 0.0
        return df

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int, since: int | None = None) -> list[list]:
        df = self._visible(symbol)
        if timeframe != self.timeframe and timeframe_ms(timeframe) > timeframe_ms(self.timeframe):
            df = resample(df, timeframe)
        if since is not None:
            df = df[df["timestamp"] >= since]
            return df.head(limit).values.tolist()
        return df.tail(limit).values.tolist()

    def fetch_ticker(self, symbol: str) -> dict:
        last = float(self._visible(symbol)["close"].iloc[-1])
        half = last * self.spread_pct / 200
        return {"last": last, "bid": last - half, "ask": last + half, "percentage": 0.0}

    def market_rules(self, symbol: str) -> MarketRules:
        if symbol not in self.data:
            raise ValueError(f"Coppia {symbol} non disponibile")
        return MarketRules(symbol=symbol, amount_step=1e-8, price_step=0.01, min_amount=0.0, min_cost=0.5)

    def ping(self) -> bool:
        return True
