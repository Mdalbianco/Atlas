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

from app.risk.risk_manager import RiskManager


risk_manager = RiskManager()

position_size = risk_manager.calculate_position_size(
    account_balance=102.0,
    entry_price=100.0,
    stop_loss=95.0,
    risk_percentage=2.0,
)

print("\n=== POSITION SIZING ===")
print(f"Saldo: 102.00 €")
print(f"Rischio massimo: 2.04 €")
print(f"Dimensione posizione: {position_size:.2f} €")