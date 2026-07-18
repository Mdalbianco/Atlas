from app.services.paper_trading_service import PaperTradingService
from app.services.scheduler_service import SchedulerService


paper_service = PaperTradingService()
scheduler = SchedulerService(interval_seconds=5)


trade = paper_service.open_trade(
    symbol="BTC",
    direction="Long",
    entry_price=50000,
    stop_loss=49000,
    take_profit=51000,
)

print("Trade prima dello scheduler:")
print(trade)

closed_trades = scheduler.run_once()

print("\nTrade chiusi dallo scheduler:")
print(closed_trades)