from app.services.auto_trade_service import AutoTradeService


service = AutoTradeService()

result = service.analyze_and_open("BTC")

print("\nRisultato:\n")
print(result)