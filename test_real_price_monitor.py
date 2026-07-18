from app.services.paper_trading_service import PaperTradingService
from app.services.market_data_service import MarketDataService


paper_service = PaperTradingService()
market_service = MarketDataService()


trade = paper_service.open_trade(
    symbol="BTC",
    direction="Long",
    entry_price=50000,
    stop_loss=49000,
    take_profit=51000,
)

print("Trade aperto:")
print(trade)

print("\nPrezzo attuale:")

current_price = market_service.get_current_price("BTC")

print(current_price)

closed_trades = paper_service.check_open_trades(
    market_service.get_current_price
)

print("\nTrade chiusi:")
print(closed_trades)