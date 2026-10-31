import numpy as np
import pandas as pd
import pytest

from atlas.analysis import indicators as ind
from tests.conftest import make_df


def test_rsi_extremes_and_range():
    up = pd.Series(np.arange(1, 60, dtype=float))
    assert ind.rsi(up).iloc[-1] == pytest.approx(100.0)
    down = pd.Series(np.arange(60, 1, -1, dtype=float))
    assert ind.rsi(down).iloc[-1] == pytest.approx(0.0)
    rnd = pd.Series(100 + np.cumsum(np.random.default_rng(0).normal(0, 1, 500)))
    r = ind.rsi(rnd).dropna()
    assert ((r >= 0) & (r <= 100)).all()
    assert ind.rsi(rnd).iloc[:13].isna().all()


def test_rsi_wilder_reference():
    """Confronto con l'implementazione classica di Wilder scritta a mano."""
    closes = pd.Series(100 + np.cumsum(np.random.default_rng(3).normal(0, 1, 200)))
    d = closes.diff().to_numpy()
    gains, losses = np.clip(d, 0, None), np.clip(-d, 0, None)
    ag, al = gains[1:15].mean(), losses[1:15].mean()
    expected = [100 - 100 / (1 + ag / al)]
    for k in range(15, len(d)):
        ag = (ag * 13 + gains[k]) / 14
        al = (al * 13 + losses[k]) / 14
        expected.append(100 - 100 / (1 + ag / al))
    got = ind.rsi(closes).to_numpy()[14:]
    assert np.allclose(got, expected, atol=1e-9)
    # esempio classico (Wilder 1978): primo RSI ≈ 70,46
    ref = pd.Series([44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28])
    assert ind.rsi(ref).iloc[14] == pytest.approx(70.46, abs=0.05)


def test_ema_sma_atr_macd():
    df = make_df(np.linspace(100, 200, 300))
    assert ind.sma(df.close, 10).iloc[-1] == pytest.approx(df.close.iloc[-10:].mean())
    assert ind.ema(df.close, 20).iloc[-1] < df.close.iloc[-1]  # in salita l'EMA resta sotto
    atr = ind.atr(df).iloc[-1]
    assert atr > 0
    m = ind.macd(df.close)
    assert m["macd"].iloc[-1] > 0 and m["macd"].iloc[:30].isna().all()


def test_adx_strong_trend_vs_noise():
    trend = make_df(np.linspace(100, 300, 300))
    noise = make_df(100 + np.random.default_rng(1).normal(0, 0.5, 300))
    assert ind.adx(trend).iloc[-1] > 40
    assert ind.adx(noise).iloc[-1] < 30


def test_relative_volume_uses_previous_bars_only():
    vol = [100.0] * 30 + [300.0]
    df = make_df(np.linspace(100, 110, 31), volume=vol)
    rv = ind.relative_volume(df.volume, 20)
    assert rv.iloc[-1] == pytest.approx(3.0)


def test_add_indicators_columns():
    df = make_df(np.linspace(100, 150, 250))
    out = ind.add_indicators(df)
    for col in ("ema20", "ema50", "ema200", "rsi", "macd_hist", "atr", "adx", "rel_volume", "volatility"):
        assert col in out
    assert len(out) == len(df)
