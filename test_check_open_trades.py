from app.services.paper_trading_service import PaperTradingService


service = PaperTradingService()

trade = service.open_trade(
    symbol="BTC",
    direction="Long",
    entry_price=50000,
    stop_loss=49000,
    take_profit=51000,
)

print("Trade aperto:")
print(trade)


def fake_price_provider(symbol: str) -> float:
    print(f"\nRecupero prezzo per {symbol}...")
    return 51100


closed_trades = service.check_open_trades(fake_price_provider)

print("\nTrade chiusi:")
print(closed_trades)