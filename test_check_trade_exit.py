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

print("\nControllo con prezzo 50500...")
result = service.check_trade_exit(trade, 50500)
print(result)

print("\nControllo con prezzo 51100...")
result = service.check_trade_exit(trade, 51100)
print(result)