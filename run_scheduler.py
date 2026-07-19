from app.services.scheduler_service import SchedulerService


scheduler = SchedulerService(
    interval_seconds=10
)

scheduler.run_forever()