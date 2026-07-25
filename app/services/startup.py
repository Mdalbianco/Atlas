import threading

from app.bot.telegram_bot import run_telegram_bot
from app.services.scheduler_service import SchedulerService
from app.utils.logger import log
from app.utils.system_check import check_system


def _run_scheduler() -> None:
    """Avvia lo scheduler automatico di Atlas."""

    scheduler = SchedulerService(
        interval_seconds=60
    )

    scheduler.run_forever()


def startup() -> None:
    """Avvia i componenti principali di Atlas."""

    log("Avvio Atlas...")

    check_system()

    log("Avvio dello scheduler automatico...")

    scheduler_thread = threading.Thread(
        target=_run_scheduler,
        name="atlas-scheduler",
        daemon=True,
    )

    scheduler_thread.start()

    log("Scheduler avviato in background.")
    log("Startup completato.")
    log("Avvio del servizio Telegram...")

    run_telegram_bot()