from app.services.statistics_service import StatisticsService


service = StatisticsService()
statistics_service = StatisticsService()
stats = statistics_service.calculate()

print("\n===== STATISTICHE ATLAS =====\n")

print(f"Trade totali: {stats['total_trades']}")
print(f"WIN: {stats['wins']}")
print(f"LOSS: {stats['losses']}")
print(f"Win rate: {stats['win_rate']:.2f}%")

print()

print(f"Performance media: {stats['average_performance']:.2f}%")
print(f"Miglior trade: {stats['best_trade']:.2f}%")
print(f"Peggior trade: {stats['worst_trade']:.2f}%")