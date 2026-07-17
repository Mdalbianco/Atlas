from app.risk.risk_manager import RiskManager


def main() -> None:
    risk_manager = RiskManager()

    long_result = risk_manager.calculate_trade_levels(
        current_price=55000,
        atr=260,
        action="Comprare",
    )

    wait_result = risk_manager.calculate_trade_levels(
        current_price=55000,
        atr=260,
        action="Attendere",
    )

    print("=== TEST OPERAZIONE LONG ===")
    print(long_result)

    print("\n=== TEST NESSUNA OPERAZIONE ===")
    print(wait_result)


if __name__ == "__main__":
    main()