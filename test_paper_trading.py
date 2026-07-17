from app.services.paper_trading_service import PaperTradingService


def main() -> None:
    paper_trading = PaperTradingService()

    trade = paper_trading.open_trade(
        symbol="BTC",
        direction="Long",
        entry_price=55000,
        stop_loss=54610,
        take_profit=55780,
    )

    print("=== PAPER TRADE APERTO ===")
    print(trade)


if __name__ == "__main__":
    main()