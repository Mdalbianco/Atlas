import pandas as pd

from app.backtesting.historical_market_data_service import (
    HistoricalMarketDataService,
)


def build_dataframe(rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100 + i for i in range(rows)],
            "high": [101 + i for i in range(rows)],
            "low": [99 + i for i in range(rows)],
            "close": [100.5 + i for i in range(rows)],
            "volume": [10 + i for i in range(rows)],
        }
    )


def test_returns_only_past_candles() -> None:
    lower_data = build_dataframe(20)
    higher_data = build_dataframe(10)

    service = HistoricalMarketDataService(
        lower_timeframe_data=lower_data,
        higher_timeframe_data=higher_data,
    )

    service.set_current_index(
        lower_index=10,
        higher_index=5,
    )

    candles = service.get_candles(
        symbol="BTC",
        timeframe="1h",
        limit=5,
    )

    assert len(candles) == 5
    assert candles.iloc[-1]["close"] == lower_data.iloc[10]["close"]

    future_close = lower_data.iloc[11]["close"]

    assert future_close not in candles["close"].values


def test_respects_limit() -> None:
    lower_data = build_dataframe(20)
    higher_data = build_dataframe(10)

    service = HistoricalMarketDataService(
        lower_timeframe_data=lower_data,
        higher_timeframe_data=higher_data,
    )

    service.set_current_index(
        lower_index=15,
        higher_index=7,
    )

    candles = service.get_candles(
        symbol="BTC",
        timeframe="1h",
        limit=3,
    )

    assert len(candles) == 3


def test_higher_timeframe_uses_correct_data() -> None:
    lower_data = build_dataframe(20)
    higher_data = build_dataframe(10)

    service = HistoricalMarketDataService(
        lower_timeframe_data=lower_data,
        higher_timeframe_data=higher_data,
    )

    service.set_current_index(
        lower_index=10,
        higher_index=4,
    )

    candles = service.get_candles(
        symbol="BTC",
        timeframe="4h",
        limit=3,
    )

    assert len(candles) == 3
    assert candles.iloc[-1]["close"] == higher_data.iloc[4]["close"]


def test_rejects_unsupported_timeframe() -> None:
    lower_data = build_dataframe(20)
    higher_data = build_dataframe(10)

    service = HistoricalMarketDataService(
        lower_timeframe_data=lower_data,
        higher_timeframe_data=higher_data,
    )

    service.set_current_index(
        lower_index=10,
        higher_index=5,
    )

    try:
        service.get_candles(
            symbol="BTC",
            timeframe="15m",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Il servizio avrebbe dovuto rifiutare il timeframe non supportato."
        )