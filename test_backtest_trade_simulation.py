import pandas as pd

from app.backtesting.backtest_engine import BacktestEngine


def test_long_trade_hits_take_profit() -> None:
    engine = BacktestEngine()

    dataframe = pd.DataFrame(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 103, "low": 99, "close": 102},
            {"open": 102, "high": 106, "low": 101, "close": 105},
        ]
    )

    signal = {
        "trade_direction": "Long",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 105.0,
    }

    result = engine._simulate_trade(
        dataframe=dataframe,
        entry_index=0,
        signal=signal,
    )

    assert result is not None
    assert result["result"] == "win"
    assert result["close_reason"] == "take_profit"
    assert result["exit_price"] == 105.0
    assert result["exit_index"] == 2


def test_long_trade_hits_stop_loss() -> None:
    engine = BacktestEngine()

    dataframe = pd.DataFrame(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 101, "low": 94, "close": 95},
        ]
    )

    signal = {
        "trade_direction": "Long",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 105.0,
    }

    result = engine._simulate_trade(
        dataframe=dataframe,
        entry_index=0,
        signal=signal,
    )

    assert result is not None
    assert result["result"] == "loss"
    assert result["close_reason"] == "stop_loss"
    assert result["exit_price"] == 95.0
    assert result["exit_index"] == 1


def test_short_trade_hits_take_profit() -> None:
    engine = BacktestEngine()

    dataframe = pd.DataFrame(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 101, "low": 94, "close": 95},
        ]
    )

    signal = {
        "trade_direction": "Short",
        "entry_price": 100.0,
        "stop_loss": 105.0,
        "take_profit": 95.0,
    }

    result = engine._simulate_trade(
        dataframe=dataframe,
        entry_index=0,
        signal=signal,
    )

    assert result is not None
    assert result["result"] == "win"
    assert result["close_reason"] == "take_profit"
    assert result["exit_price"] == 95.0
    assert result["exit_index"] == 1


def test_short_trade_hits_stop_loss() -> None:
    engine = BacktestEngine()

    dataframe = pd.DataFrame(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 106, "low": 99, "close": 105},
        ]
    )

    signal = {
        "trade_direction": "Short",
        "entry_price": 100.0,
        "stop_loss": 105.0,
        "take_profit": 95.0,
    }

    result = engine._simulate_trade(
        dataframe=dataframe,
        entry_index=0,
        signal=signal,
    )

    assert result is not None
    assert result["result"] == "loss"
    assert result["close_reason"] == "stop_loss"
    assert result["exit_price"] == 105.0
    assert result["exit_index"] == 1

def test_backtest_uses_position_size_for_profit_loss() -> None:
    dataframe = pd.DataFrame(
        [
            {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0},
            {"open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0},
        ]
    )

    engine = BacktestEngine(initial_balance=100.0)

    signal = {
        "trade_direction": "Long",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 105.0,
        "position_size": 20.0,
    }

    result = engine._simulate_trade(
        dataframe=dataframe,
        entry_index=0,
        signal=signal,
    )

    assert result is not None
    assert result["result"] == "win"

    performance_percentage = (
        (result["exit_price"] - signal["entry_price"])
        / signal["entry_price"]
        * 100
    )

    profit_loss = (
        signal["position_size"]
        * performance_percentage
        / 100
    )

    assert round(profit_loss, 2) == 1.00