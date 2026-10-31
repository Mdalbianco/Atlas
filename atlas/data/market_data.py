"""Preparazione e validazione delle candele OHLCV.

Regole anti look-ahead:
- la candela in formazione (non ancora chiusa) viene sempre scartata;
- i timestamp sono quelli di apertura (convenzione CCXT); una candela è
  "nota" solo dopo ``timestamp + durata``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from atlas.data.exchange import MarketDataSource

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

_UNIT_MS = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}


def timeframe_ms(timeframe: str) -> int:
    try:
        return int(timeframe[:-1]) * _UNIT_MS[timeframe[-1]]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Timeframe non supportato: {timeframe}") from exc


class DataQualityError(ValueError):
    """I dati non superano i controlli di qualità."""


@dataclass
class DataQualityReport:
    ok: bool
    rows: int
    issues: list[str] = field(default_factory=list)
    dropped_incomplete: bool = False
    gaps: int = 0


def to_dataframe(rows: list[list]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLUMNS)
    for col in COLUMNS[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce").astype("int64")
    return df


def clean_and_validate(
    df: pd.DataFrame,
    timeframe: str,
    now_ms: int | None = None,
    max_age_minutes: int | None = None,
    min_rows: int = 1,
) -> tuple[pd.DataFrame, DataQualityReport]:
    """Pulisce le candele e verifica la qualità. Solleva DataQualityError se inutilizzabili."""
    issues: list[str] = []
    tf = timeframe_ms(timeframe)
    df = df.copy()

    before = len(df)
    df = df.dropna(subset=COLUMNS)
    if len(df) < before:
        issues.append(f"{before - len(df)} candele con valori mancanti rimosse")

    df = df.drop_duplicates(subset="timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)

    invalid = (
        (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (df["volume"] < 0)
        | (df["high"] < df[["open", "close"]].max(axis=1) - 1e-12)
        | (df["low"] > df[["open", "close"]].min(axis=1) + 1e-12)
    )
    if invalid.any():
        issues.append(f"{int(invalid.sum())} candele incoerenti rimosse")
        df = df[~invalid].reset_index(drop=True)

    dropped_incomplete = False
    if now_ms is not None and len(df):
        if df["timestamp"].iloc[-1] + tf > now_ms:
            df = df.iloc[:-1].reset_index(drop=True)
            dropped_incomplete = True

    gaps = 0
    if len(df) > 1:
        diffs = np.diff(df["timestamp"].to_numpy())
        gaps = int((diffs > tf).sum())
        if gaps:
            issues.append(f"{gaps} buchi temporali nella serie")

    if len(df) < min_rows:
        raise DataQualityError(f"Candele insufficienti: {len(df)} (minimo {min_rows})")

    if now_ms is not None and max_age_minutes is not None and len(df):
        close_ms = int(df["timestamp"].iloc[-1]) + tf
        age_min = (now_ms - close_ms) / 60_000
        if age_min > max_age_minutes:
            raise DataQualityError(f"Dati non aggiornati: ultima candela chiusa {age_min:.0f} minuti fa")

    return df, DataQualityReport(ok=True, rows=len(df), issues=issues, dropped_incomplete=dropped_incomplete, gaps=gaps)


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class MarketDataService:
    """Recupera candele complete e validate da una fonte dati."""

    def __init__(self, source: MarketDataSource, max_age_minutes: int = 180, clock=now_ms) -> None:
        self.source = source
        self.max_age_minutes = max_age_minutes
        self.clock = clock

    def candles(self, symbol: str, timeframe: str, limit: int, min_rows: int = 220) -> tuple[pd.DataFrame, DataQualityReport]:
        rows = self.source.fetch_ohlcv(symbol, timeframe, limit + 1)
        if not rows:
            raise DataQualityError(f"Nessuna candela ricevuta per {symbol}")
        df = to_dataframe(rows)
        # La soglia di freschezza tiene conto della durata del timeframe.
        max_age = self.max_age_minutes + timeframe_ms(timeframe) // 60_000
        return clean_and_validate(df, timeframe, now_ms=self.clock(), max_age_minutes=max_age, min_rows=min_rows)

    def ticker(self, symbol: str) -> dict:
        t = self.source.fetch_ticker(symbol)
        last = t.get("last") or t.get("close")
        if not last or last <= 0:
            raise DataQualityError(f"Ticker non valido per {symbol}")
        bid, ask = t.get("bid"), t.get("ask")
        spread_pct = None
        if bid and ask and ask >= bid > 0:
            spread_pct = (ask - bid) / ((ask + bid) / 2) * 100
        return {
            "symbol": symbol,
            "last": float(last),
            "bid": float(bid) if bid else None,
            "ask": float(ask) if ask else None,
            "spread_pct": spread_pct,
            "change_pct": t.get("percentage"),
            "high": t.get("high"),
            "low": t.get("low"),
            "volume": t.get("quoteVolume") or t.get("baseVolume"),
        }


def download_history(source: MarketDataSource, symbol: str, timeframe: str, since_ms: int, until_ms: int | None = None, page: int = 720) -> pd.DataFrame:
    """Scarica uno storico paginato (Kraken restituisce al massimo ~720 candele)."""
    until_ms = until_ms or now_ms()
    tf = timeframe_ms(timeframe)
    out: list[list] = []
    cursor = since_ms
    while cursor < until_ms:
        rows = source.fetch_ohlcv(symbol, timeframe, page, since=cursor)
        if not rows:
            break
        out.extend(rows)
        last_ts = int(rows[-1][0])
        if last_ts + tf <= cursor:
            break
        cursor = last_ts + tf
        if len(rows) < 2:
            break
    df = to_dataframe(out) if out else pd.DataFrame(columns=COLUMNS)
    df, _ = clean_and_validate(df, timeframe, now_ms=now_ms(), min_rows=0)
    return df[df["timestamp"] < until_ms].reset_index(drop=True)
