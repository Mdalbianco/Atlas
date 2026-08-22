from unittest.mock import patch

from app.services.auto_trade_service import AutoTradeService


def build_service() -> AutoTradeService:
    return AutoTradeService(
        max_open_trades=2,
        max_committed_percentage=70.0,
        min_position_size=10.0,
    )


def test_rejects_low_confidence() -> None:
    service = build_service()

    fake_analysis = {
        "score": 75,
        "score_acceptable": True,
        "score_classification": "Buono",
        "confidence": 50,
        "trade_available": True,
    }

    with patch.object(
        service.analysis_manager,
        "analyze",
        return_value=fake_analysis,
    ):
        result = service.analyze_and_open("BTC")

    assert result["trade_opened"] is False
    assert result["status"] == "confidence_below_minimum"

def test_rejects_unaligned_timeframes() -> None:
    service = build_service()

    fake_analysis = {
        "score": 80,
        "score_acceptable": True,
        "score_classification": "Ottimo",
        "confidence": 85,
        "trade_available": True,
        "timeframe_aligned": False,
        "lower_timeframe_trend": "Rialzista",
        "higher_timeframe_trend": "Ribassista",
    }

    with patch.object(
        service.analysis_manager,
        "analyze",
        return_value=fake_analysis,
    ):
        result = service.analyze_and_open("BTC")

    assert result["trade_opened"] is False
    assert result["status"] == "timeframe_not_aligned"
    assert "1H Rialzista" in result["reason"]
    assert "4H Ribassista" in result["reason"]

def test_rejects_extended_candle() -> None:
    service = build_service()

    fake_analysis = {
        "score": 80,
        "score_acceptable": True,
        "score_classification": "Ottimo",
        "confidence": 85,
        "trade_available": True,
        "timeframe_aligned": True,
        "lower_timeframe_trend": "Rialzista",
        "higher_timeframe_trend": "Rialzista",
        "market_regime": "Trend rialzista",
        "extended_candle": True,
    }

    with (
        patch.object(
            service.analysis_manager,
            "analyze",
            return_value=fake_analysis,
        ),
        patch.object(
            service.paper_trading_service,
            "open_trade",
        ) as mock_open_trade,
    ):
        result = service.analyze_and_open("BTC")

    assert result["trade_opened"] is False
    assert result["status"] == "extended_candle"
    assert "candela troppo estesa" in result["reason"]
    mock_open_trade.assert_not_called()

def test_opens_valid_trade() -> None:
    service = build_service()

    fake_analysis = {
        "score": 80,
        "score_acceptable": True,
        "score_classification": "Ottimo",
        "confidence": 85,
        "trade_available": True,
        "timeframe_aligned": True,
        "lower_timeframe_trend": "Rialzista",
        "higher_timeframe_trend": "Rialzista",
        "entry_price": 100.0,
        "stop_loss": 98.0,
        "take_profit": 104.0,
        "trade_direction": "Long",
        "risk_reward_ratio": 2.0,
    }

    fake_trade = {
        "id": "test-trade",
        "symbol": "BTC",
        "direction": "Long",
        "entry_price": 100.0,
        "stop_loss": 98.0,
        "take_profit": 104.0,
        "position_size": 20.0,
        "status": "open",
    }

    with (
        patch.object(
            service.analysis_manager,
            "analyze",
            return_value=fake_analysis,
        ),
        patch.object(
            service.paper_trading_service,
            "get_open_trades",
            return_value=[],
        ),
        patch.object(
            service.wallet_service,
            "get_balance",
            return_value=100.0,
        ),
        patch.object(
            service.risk_manager,
            "calculate_position_size",
            return_value=20.0,
        ),
        patch.object(
            service.paper_trading_service,
            "open_trade",
            return_value=fake_trade,
        ),
        patch.object(
            service.notification_service,
            "send_sync",
            return_value=None,
        ),
    ):
        result = service.analyze_and_open("BTC")

    assert result["trade_opened"] is True
    assert result["trade"]["symbol"] == "BTC"
    assert result["trade"]["direction"] == "Long"
    assert result["trade"]["position_size"] == 20.0
    assert result["trade"]["status"] == "open"


if __name__ == "__main__":
    test_rejects_low_confidence()
    test_rejects_unaligned_timeframes()
    test_rejects_extended_candle()
    test_opens_valid_trade()

    print("✅ Tutti i test dei filtri auto-trade sono passati.")