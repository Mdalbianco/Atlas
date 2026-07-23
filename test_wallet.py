from app.services.paper_trading_service import PaperTradingService
from app.services.wallet_service import WalletService


paper_trading = PaperTradingService()
wallet = WalletService()

print("=== SALDO INIZIALE ===")
print(wallet.get_wallet())

trade = paper_trading.open_trade(
    symbol="BTC",
    direction="Long",
    entry_price=100.0,
    stop_loss=95.0,
    take_profit=105.0,
    position_size=20.0,
)

print("\n=== TRADE APERTO ===")
print(trade)

closed_trades = paper_trading.check_open_trades(
    price_provider=lambda symbol: 105.0
)

print("\n=== TRADE CHIUSO ===")
print(closed_trades)

print("\n=== SALDO FINALE ===")
print(wallet.get_wallet())