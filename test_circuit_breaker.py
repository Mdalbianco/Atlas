from datetime import datetime, timezone

from app.risk.circuit_breaker import CircuitBreaker


def make_trade(
    result: str,
    profit_loss: float,
    wallet_balance: float,
    closed_at: str | None = None,
) -> dict:
    if closed_at is None:
        closed_at = datetime.now(timezone.utc).isoformat()

    return {
        "status": "closed",
        "result": result,
        "profit_loss": profit_loss,
        "wallet_balance": wallet_balance,
        "closed_at": closed_at,
    }


def test_allows_normal_conditions() -> None:
    breaker = CircuitBreaker()

    trades = [
        make_trade("win", 2.0, 102.0),
        make_trade("loss", -1.0, 101.0),
    ]

    result = breaker.evaluate(
        trades=trades,
        current_balance=101.0,
        peak_balance=102.0,
    )

    assert result["allowed"] is True
    assert result["reason"] is None


def test_blocks_after_three_consecutive_losses() -> None:
    breaker = CircuitBreaker(
        max_consecutive_losses=3,
    )

    trades = [
        make_trade("win", 2.0, 102.0),
        make_trade("loss", -1.0, 101.0),
        make_trade("loss", -1.0, 100.0),
        make_trade("loss", -1.0, 99.0),
    ]

    result = breaker.evaluate(
        trades=trades,
        current_balance=99.0,
        peak_balance=102.0,
    )

    assert result["allowed"] is False
    assert result["reason"] == "max_consecutive_losses"
    assert result["value"] == 3


def test_blocks_daily_loss_limit() -> None:
    breaker = CircuitBreaker(
        max_daily_loss_percentage=3.0,
        max_consecutive_losses=10,
    )

    trades = [
        make_trade("loss", -2.0, 98.0),
        make_trade("loss", -2.0, 96.0),
    ]

    result = breaker.evaluate(
        trades=trades,
        current_balance=96.0,
        peak_balance=100.0,
    )

    assert result["allowed"] is False
    assert result["reason"] == "max_daily_loss"
    assert result["value"] >= 3.0


def test_blocks_max_drawdown() -> None:
    breaker = CircuitBreaker(
        max_drawdown_percentage=10.0,
        max_consecutive_losses=10,
        max_daily_loss_percentage=100.0,
    )

    result = breaker.evaluate(
        trades=[],
        current_balance=89.0,
        peak_balance=100.0,
    )

    assert result["allowed"] is False
    assert result["reason"] == "max_drawdown"
    assert result["value"] == 11.0


def test_does_not_block_below_drawdown_limit() -> None:
    breaker = CircuitBreaker(
        max_drawdown_percentage=10.0,
    )

    result = breaker.evaluate(
        trades=[],
        current_balance=91.0,
        peak_balance=100.0,
    )

    assert result["allowed"] is True


if __name__ == "__main__":
    test_allows_normal_conditions()
    test_blocks_after_three_consecutive_losses()
    test_blocks_daily_loss_limit()
    test_blocks_max_drawdown()
    test_does_not_block_below_drawdown_limit()

    print("✅ Tutti i test del circuit breaker sono passati.")