from app.services.paper_trading_service import PaperTradingService
from app.services.trade_monitor_service import TradeMonitorService


paper_service = PaperTradingService()
monitor_service = TradeMonitorService()


trade = paper_service.open_trade(
    symbol="BTC",
    direction="Long",
    entry_price=50000,
    stop_loss=49000,
    take_profit=51000,
)

print("Trade prima del monitoraggio:")
print(trade)

closed_trades = monitor_service.check_once()

print("\nTrade chiusi dal monitor:")
print(closed_trades)