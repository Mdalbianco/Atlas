from app.bot.telegram_bot import run_telegram_bot
from app.utils.logger import log
from app.utils.system_check import check_system


def startup() -> None:
    """Avvia i componenti principali di Atlas."""

    log("Avvio Atlas...")

    check_system()

    log("Startup completato.")
    log("Avvio del servizio Telegram...")

    run_telegram_bot()