from app.services.paper_trading_service import (
    PaperTradingService,
)


def main() -> None:
    paper_trading = PaperTradingService()

    open_trades = paper_trading.get_open_trades()

    if not open_trades:
        print("Nessun trade aperto da chiudere.")
        return

    trade = open_trades[0]

    closed_trade = paper_trading.close_trade(
        trade_id=trade["id"],
        exit_price=55780,
        result="win",
    )

    print("=== TRADE CHIUSO ===")
    print(closed_trade)


if __name__ == "__main__":
    main()