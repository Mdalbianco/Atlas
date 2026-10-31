import numpy as np
import pandas as pd
import pytest

from atlas.data.market_data import DataQualityError, MarketDataService, clean_and_validate, timeframe_ms, to_dataframe
from atlas.data.sources import SyntheticMarket, load_csv, resample
from tests.conftest import make_df

H = 3_600_000


def test_incomplete_last_candle_is_dropped():
    df = make_df(np.linspace(100, 110, 50))
    last_open = int(df.timestamp.iloc[-1])
    out, rep = clean_and_validate(df, "1h", now_ms=last_open + 10 * 60_000)
    assert len(out) == 49 and rep.dropped_incomplete
    out2, rep2 = clean_and_validate(df, "1h", now_ms=last_open + H)
    assert len(out2) == 50 and not rep2.dropped_incomplete


def test_invalid_and_duplicate_rows_removed():
    df = make_df(np.linspace(100, 110, 30))
    df.loc[5, "high"] = df.loc[5, "low"] - 1     # incoerente
    df.loc[6, "close"] = np.nan                   # mancante
    df = pd.concat([df, df.iloc[[10]]])           # duplicato
    out, rep = clean_and_validate(df, "1h")
    assert len(out) == 28
    assert out.timestamp.is_monotonic_increasing and out.timestamp.is_unique
    assert any("incoerenti" in i for i in rep.issues)


def test_stale_data_rejected():
    df = make_df(np.linspace(100, 110, 30))
    now = int(df.timestamp.iloc[-1]) + H + 5 * H
    with pytest.raises(DataQualityError, match="non aggiornati"):
        clean_and_validate(df, "1h", now_ms=now, max_age_minutes=60)


def test_gaps_detected_and_min_rows():
    df = make_df(np.linspace(100, 110, 30)).drop(index=[10, 11]).reset_index(drop=True)
    _, rep = clean_and_validate(df, "1h")
    assert rep.gaps == 1
    with pytest.raises(DataQualityError):
        clean_and_validate(df, "1h", min_rows=100)


def test_timeframe_ms():
    assert timeframe_ms("1h") == H and timeframe_ms("4h") == 4 * H and timeframe_ms("15m") == 900_000
    with pytest.raises(ValueError):
        timeframe_ms("1x")


def test_resample_keeps_only_complete_groups():
    df = make_df(np.arange(1, 11, dtype=float), start_ms=0)  # 10 candele orarie
    r = resample(df, "4h")
    assert len(r) == 2
    assert r.high.iloc[0] == df.high.iloc[:4].max() and r.close.iloc[0] == df.close.iloc[3]
    assert r.volume.iloc[1] == df.volume.iloc[4:8].sum()


def test_csv_formats(tmp_path):
    df = make_df(np.linspace(100, 110, 20))
    p1 = tmp_path / "BTC_EUR_1h.csv"
    df.to_csv(p1, index=False)
    assert len(load_csv(p1)) == 20
    # formato Kraken OHLCVT: senza intestazione, timestamp in secondi, colonna trades
    p2 = tmp_path / "XBTEUR_60.csv"
    k = df.copy()
    k["timestamp"] = k.timestamp // 1000
    k["trades"] = 5
    k.to_csv(p2, index=False, header=False)
    loaded = load_csv(p2)
    assert loaded.timestamp.iloc[0] == df.timestamp.iloc[0]
    assert loaded.close.iloc[-1] == pytest.approx(df.close.iloc[-1])


def test_market_data_service_with_replay():
    m = SyntheticMarket(bars=400, seed=1)
    t = int(m.data["BTC/EUR"].timestamp.iloc[350])
    m.now_ms = t
    svc = MarketDataService(m, clock=lambda: t + 60_000)
    df, rep = svc.candles("BTC/EUR", "1h", 300, min_rows=200)
    assert rep.dropped_incomplete and int(df.timestamp.iloc[-1]) == t - H
    tk = svc.ticker("BTC/EUR")
    assert tk["spread_pct"] == pytest.approx(0.06, rel=1e-3)


def test_replay_never_reveals_future_prices():
    m = SyntheticMarket(bars=300, seed=2)
    df = m.data["BTC/EUR"]
    t = int(df.timestamp.iloc[200])
    m.now_ms = t
    rows = m.fetch_ohlcv("BTC/EUR", "1h", 500)
    assert rows[-1][0] == t
    assert rows[-1][1] == rows[-1][2] == rows[-1][3] == rows[-1][4] == df.open.iloc[200]
    assert m.fetch_ticker("BTC/EUR")["last"] == df.open.iloc[200]
    assert rows[-2][4] == df.close.iloc[199]


def test_analyzer_refetches_only_when_a_new_candle_closes():
    from atlas.engine.analyzer import Analyzer

    m = SyntheticMarket({"BTC/EUR": 60000.0}, bars=1200, seed=4)
    ts = m.data["BTC/EUR"].timestamp.tolist()
    clock = {"ms": 0}
    an = Analyzer(MarketDataService(m, clock=lambda: clock["ms"]), "1h", "4h", 720, 4.0)
    m.now_ms = ts[1000]
    for minute in (1, 6, 30, 59):                      # 4 cicli nella stessa ora
        clock["ms"] = ts[1000] + minute * 60_000
        snap, _, _ = an.snapshot("BTC/EUR", "1h")
    assert an.fetches == 1 and snap.timestamp == ts[999]
    m.now_ms = ts[1001]; clock["ms"] = ts[1001] + 60_000  # nuova candela chiusa
    snap, _, _ = an.snapshot("BTC/EUR", "1h")
    assert an.fetches == 2 and snap.timestamp == ts[1000]


def test_repository_research_data_is_valid():
    """I dati reali salvati nel repository sono leggibili, completi e coerenti."""
    from pathlib import Path

    files = sorted(Path(__file__).parents[1].glob("research/data/*_EUR_1h_*.csv.gz"))
    assert len(files) == 3
    for f in files:
        df, rep = clean_and_validate(load_csv(f), "1h")
        assert len(df) == 8755 and rep.gaps <= 1
