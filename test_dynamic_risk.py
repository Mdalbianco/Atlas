from app.risk.risk_manager import RiskManager


def test_dynamic_risk_percentage_levels() -> None:
    manager = RiskManager()

    assert manager.calculate_dynamic_risk_percentage(
        score=95,
        confidence=95,
    ) == 2.0

    assert manager.calculate_dynamic_risk_percentage(
        score=85,
        confidence=85,
    ) == 1.5

    assert manager.calculate_dynamic_risk_percentage(
        score=75,
        confidence=75,
    ) == 1.0

    assert manager.calculate_dynamic_risk_percentage(
        score=60,
        confidence=60,
    ) == 0.5


def test_better_setup_gets_larger_position() -> None:
    manager = RiskManager()

    account_balance = 1000.0
    entry_price = 100.0
    stop_loss = 98.0

    low_risk = manager.calculate_dynamic_risk_percentage(
        score=70,
        confidence=70,
    )

    high_risk = manager.calculate_dynamic_risk_percentage(
        score=90,
        confidence=90,
    )

    low_position = manager.calculate_position_size(
        account_balance=account_balance,
        entry_price=entry_price,
        stop_loss=stop_loss,
        risk_percentage=low_risk,
    )

    high_position = manager.calculate_position_size(
        account_balance=account_balance,
        entry_price=entry_price,
        stop_loss=stop_loss,
        risk_percentage=high_risk,
    )

    assert high_risk > low_risk
    assert high_position > low_position


def test_position_size_never_exceeds_balance() -> None:
    manager = RiskManager()

    position_size = manager.calculate_position_size(
        account_balance=1000.0,
        entry_price=100.0,
        stop_loss=99.9,
        risk_percentage=2.0,
    )

    assert position_size <= 1000.0


if __name__ == "__main__":
    test_dynamic_risk_percentage_levels()
    test_better_setup_gets_larger_position()
    test_position_size_never_exceeds_balance()

    print("✅ Tutti i test del rischio dinamico sono passati.")