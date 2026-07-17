from app.services.paper_trading_service import (
    PaperTradingService,
)


def main() -> None:
    paper_trading = PaperTradingService()

    trades = paper_trading.get_open_trades()

    print("=== TRADE APERTI ===")

    for trade in trades:
        print(trade)


if __name__ == "__main__":
    main()