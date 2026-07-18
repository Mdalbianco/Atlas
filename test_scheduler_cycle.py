from app.services.scheduler_service import SchedulerService


scheduler = SchedulerService(interval_seconds=5)

print("\n===== PRIMO CICLO =====\n")

first_result = scheduler.run_once(
    symbols=["BTC"]
)

print(first_result)


print("\n===== SECONDO CICLO =====\n")

second_result = scheduler.run_once(
    symbols=["BTC"]
)

print(second_result)