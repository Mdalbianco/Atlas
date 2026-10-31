"""Verifica che nessun calcolo usi dati futuri: troncare la serie non deve
cambiare i valori calcolati fino al punto di troncamento."""

import numpy as np
import pandas as pd
import pytest

from atlas.analysis.indicators import ArrayFrame, add_indicators
from atlas.analysis.snapshot import build_snapshot
from atlas.analysis.structure import analyze_structure, confirmed_pivots

COLS = ["ema20", "ema50", "ema200", "rsi", "macd", "macd_signal", "macd_hist", "atr", "adx", "rel_volume", "volatility", "obv", "bar_range_atr"]


def assert_close(x, y):
    if isinstance(x, dict):
        assert x.keys() == y.keys()
        for k in x:
            assert_close(x[k], y[k])
    elif isinstance(x, list):
        assert len(x) == len(y)
        for a, b in zip(x, y):
            assert_close(a, b)
    elif isinstance(x, float):
        assert x == pytest.approx(y, rel=1e-9, abs=1e-12)
    else:
        assert x == y


def test_indicators_are_causal(market):
    df = market.data["ETH/EUR"].iloc[:1200].reset_index(drop=True)
    full = add_indicators(df)
    for cut in (250, 600, 1100):
        part = add_indicators(df.iloc[:cut])
        pd.testing.assert_frame_equal(part[COLS], full[COLS].iloc[:cut], check_exact=False, rtol=1e-9)


def test_snapshot_identical_on_truncated_data(market):
    df = market.data["BTC/EUR"].iloc[:900].reset_index(drop=True)
    full = ArrayFrame.from_frame(add_indicators(df))
    for i in (300, 512, 899):
        a = build_snapshot("BTC/EUR", "1h", df.iloc[: i + 1])
        view = full.upto(i + 1)
        b = build_snapshot("BTC/EUR", "1h", view, enriched=view)
        assert_close(a.to_dict(), b.to_dict())


def test_future_bars_do_not_change_structure(market):
    df = add_indicators(market.data["SOL/EUR"].iloc[:700].reset_index(drop=True))
    base = analyze_structure(df.iloc[:500])
    # alterare drasticamente il futuro non deve cambiare nulla
    altered = df.copy()
    altered.loc[500:, ["open", "high", "low", "close"]] *= 3
    assert analyze_structure(altered.iloc[:500]).to_dict() == base.to_dict()


def test_pivots_require_confirmation():
    high = np.array([1, 2, 3, 10, 3, 2, 1, 1, 1], dtype=float)
    low = high - 0.5
    hi, _ = confirmed_pivots(high, low, k=3)
    assert hi == [3]
    # con solo 2 candele dopo il massimo il pivot non è ancora confermato
    hi2, _ = confirmed_pivots(high[:6], low[:6], k=3)
    assert hi2 == []


def test_array_frame_cannot_read_beyond_end():
    af = ArrayFrame({"close": np.arange(10.0)}, end=4)
    assert len(af["close"]) == 4 and af["close"][-1] == 3.0


def test_ema200_needs_long_history_to_match_backtest(market):
    """Motivo del default ATLAS_CANDLES_LIMIT=720: con 300 candele l'EMA200 non è convergente."""
    df = market.data["BTC/EUR"].reset_index(drop=True)
    full = add_indicators(df)["ema200"].iloc[-1]
    short = add_indicators(df.tail(300))["ema200"].iloc[-1]
    long = add_indicators(df.tail(720))["ema200"].iloc[-1]
    assert abs(long - full) / full < abs(short - full) / full
    assert abs(long - full) / full < 0.002
