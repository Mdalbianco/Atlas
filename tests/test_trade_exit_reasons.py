from pathlib import Path

from app.services.paper_trading_service import PaperTradingService


def make_service(tmp_path: Path) -> PaperTradingService:
    return PaperTradingService(
        file_path=str(tmp_path / "paper_trades_test.json")
    )


def save_trade(
    service: PaperTradingService,
    *,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    trailing_stop_active: bool = False,
) -> dict:
    trade = {
        "id": "test-trade",
        "symbol": "BTC",
        "direction": direction,
        "entry_price": entry_price,
        "position_size": 20.0,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "status": "open",
        "opened_at": "2026-08-22T10:00:00+00:00",
        "closed_at": None,
        "exit_price": None,
        "result": None,
        "trailing_stop_active": trailing_stop_active,
    }

    service._save_trades([trade])

    return trade


def test_long_normal_stop_loss(tmp_path):
    service = make_service(tmp_path)

    trade = save_trade(
        service,
        direction="Long",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
    )

    closed = service.check_trade_exit(
        trade=trade,
        current_price=95.0,
    )

    assert closed is not None
    assert closed["result"] == "loss"
    assert closed["close_reason"] == "stop_loss"


def test_long_trailing_stop_profit(tmp_path):
    service = make_service(tmp_path)

    trade = save_trade(
        service,
        direction="Long",
        entry_price=100.0,
        stop_loss=105.0,
        take_profit=115.0,
        trailing_stop_active=True,
    )

    closed = service.check_trade_exit(
        trade=trade,
        current_price=105.0,
    )

    assert closed is not None
    assert closed["result"] == "win"
    assert closed["close_reason"] == "trailing_stop"


def test_long_take_profit(tmp_path):
    service = make_service(tmp_path)

    trade = save_trade(
        service,
        direction="Long",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
    )

    closed = service.check_trade_exit(
        trade=trade,
        current_price=110.0,
    )

    assert closed is not None
    assert closed["result"] == "win"
    assert closed["close_reason"] == "take_profit"


def test_short_normal_stop_loss(tmp_path):
    service = make_service(tmp_path)

    trade = save_trade(
        service,
        direction="Short",
        entry_price=100.0,
        stop_loss=105.0,
        take_profit=90.0,
    )

    closed = service.check_trade_exit(
        trade=trade,
        current_price=105.0,
    )

    assert closed is not None
    assert closed["result"] == "loss"
    assert closed["close_reason"] == "stop_loss"


def test_short_trailing_stop_profit(tmp_path):
    service = make_service(tmp_path)

    trade = save_trade(
        service,
        direction="Short",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=85.0,
        trailing_stop_active=True,
    )

    closed = service.check_trade_exit(
        trade=trade,
        current_price=95.0,
    )

    assert closed is not None
    assert closed["result"] == "win"
    assert closed["close_reason"] == "trailing_stop"


def test_short_take_profit(tmp_path):
    service = make_service(tmp_path)

    trade = save_trade(
        service,
        direction="Short",
        entry_price=100.0,
        stop_loss=105.0,
        take_profit=90.0,
    )

    closed = service.check_trade_exit(
        trade=trade,
        current_price=90.0,
    )

    assert closed is not None
    assert closed["result"] == "win"
    assert closed["close_reason"] == "take_profit"