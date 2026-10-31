"""Indicatori tecnici vettoriali e causali.

Ogni valore all'indice ``i`` dipende esclusivamente dalle candele ``0..i``:
nessuna funzione usa ``shift(-n)``, finestre centrate o informazioni future.
Questa proprietà è verificata dai test (``tests/test_no_lookahead.py``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).mean()


def _wilder(series: pd.Series, period: int) -> pd.Series:
    """Media mobile di Wilder (RMA): seme = media semplice dei primi ``period`` valori validi.

    Il seme all'indice ``f + period - 1`` usa solo valori fino a quell'indice:
    il calcolo resta causale.
    """
    values = series.to_numpy(dtype="float64", copy=True)
    valid = np.flatnonzero(~np.isnan(values))
    out = np.full(len(values), np.nan)
    if len(valid) < period:
        return pd.Series(out, index=series.index)
    first = valid[0]
    seed_idx = first + period - 1
    seeded = values.copy()
    seeded[:seed_idx] = np.nan
    seeded[seed_idx] = np.nanmean(values[first : seed_idx + 1])
    res = pd.Series(seeded, index=series.index).ewm(alpha=1 / period, adjust=False, ignore_na=True).mean()
    res.iloc[:seed_idx] = np.nan
    return res


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI di Wilder."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = _wilder(gain, period)
    avg_loss = _wilder(loss, period)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    out = out.where(avg_loss != 0, 100.0)
    return out.where(avg_gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    sig = line.ewm(span=signal, adjust=False).mean()
    hist = line - sig
    valid = pd.Series(np.arange(len(close)) >= slow + signal, index=close.index)
    return pd.DataFrame({"macd": line.where(valid), "macd_signal": sig.where(valid), "macd_hist": hist.where(valid)})


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1
    ).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR di Wilder."""
    return _wilder(true_range(df), period)


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index: forza del trend (0-100), indipendente dalla direzione."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    atr_ = _wilder(true_range(df), period)
    plus_di = 100 * _wilder(plus_dm, period) / atr_
    minus_di = 100 * _wilder(minus_dm, period) / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return _wilder(dx, period)


def relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume della candela rispetto alla media delle ``period`` candele PRECEDENTI."""
    baseline = volume.shift(1).rolling(period, min_periods=period).mean()
    return volume / baseline.replace(0, np.nan)


def realized_volatility(close: pd.Series, period: int = 24) -> pd.Series:
    """Deviazione standard dei rendimenti logaritmici (in %, per candela)."""
    return np.log(close).diff().rolling(period, min_periods=period).std() * 100


def bollinger(close: pd.Series, period: int = 20, k: float = 2.0) -> pd.DataFrame:
    """Bande di Bollinger (deviazione standard di popolazione, come da definizione originale)."""
    mid = close.rolling(period, min_periods=period).mean()
    sd = close.rolling(period, min_periods=period).std(ddof=0)
    upper, lower = mid + k * sd, mid - k * sd
    width = (upper - lower) / mid * 100
    pctb = (close - lower) / (upper - lower).replace(0, np.nan)
    return pd.DataFrame({"bb_mid": mid, "bb_upper": upper, "bb_lower": lower, "bb_width": width, "bb_pctb": pctb})


def rolling_rank(series: pd.Series, window: int) -> pd.Series:
    """Percentile (0-1) del valore corrente rispetto alle ultime ``window`` osservazioni, incluso sé stesso."""
    return series.rolling(window, min_periods=window).rank(pct=True)


def donchian_high(high: pd.Series, period: int) -> pd.Series:
    """Massimo delle ``period`` candele PRECEDENTI (esclusa la corrente)."""
    return high.shift(1).rolling(period, min_periods=period).max()


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff().fillna(0))
    return (direction * df["volume"]).cumsum()


def slope_pct(series: pd.Series, lookback: int) -> pd.Series:
    """Variazione percentuale della serie rispetto a ``lookback`` candele prima."""
    return (series / series.shift(lookback) - 1) * 100


class ArrayFrame:
    """Vista in sola lettura delle prime ``end`` righe di un insieme di colonne numpy.

    Evita l'overhead di pandas quando si analizza la stessa serie migliaia di
    volte (backtest). ``frame[col]`` restituisce l'array troncato a ``end``:
    per costruzione è impossibile leggere righe successive.
    """

    __slots__ = ("_cols", "_end")

    def __init__(self, cols: dict[str, np.ndarray], end: int | None = None) -> None:
        self._cols = cols
        n = len(next(iter(cols.values()))) if cols else 0
        self._end = n if end is None else min(end, n)

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> "ArrayFrame":
        return cls({c: df[c].to_numpy(dtype="float64") for c in df.columns})

    def upto(self, end: int) -> "ArrayFrame":
        return ArrayFrame(self._cols, end)

    def __getitem__(self, name: str) -> np.ndarray:
        return self._cols[name][: self._end]

    def __len__(self) -> int:
        return self._end


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Restituisce una copia del DataFrame con tutte le colonne indicatore."""
    out = df.copy()
    close = out["close"]
    out["ema20"] = ema(close, 20)
    out["ema50"] = ema(close, 50)
    out["ema200"] = ema(close, 200)
    out["rsi"] = rsi(close, 14)
    out = out.join(macd(close))
    out["atr"] = atr(out, 14)
    out["atr_pct"] = out["atr"] / close * 100
    out["adx"] = adx(out, 14)
    out["rel_volume"] = relative_volume(out["volume"], 20)
    out["volatility"] = realized_volatility(close, 24)
    out["obv"] = obv(out)
    out["obv_slope"] = out["obv"].diff(10)
    out["ema50_slope"] = slope_pct(out["ema50"], 10)
    out["change_pct"] = close.pct_change() * 100
    out["bar_range_atr"] = (out["high"] - out["low"]) / out["atr"].shift(1)
    out = out.join(bollinger(close))
    out["bb_width_rank"] = rolling_rank(out["bb_width"], 120)
    out["donchian55"] = donchian_high(out["high"], 55)
    out["adx_slope"] = out["adx"].diff(3)
    out["ema20_prev_above_ema50"] = (out["ema20"].shift(1) > out["ema50"].shift(1)).astype(float)
    return out
