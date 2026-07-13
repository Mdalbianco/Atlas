from config.settings import APP_NAME
from config.settings import VERSION
from config.settings import PAPER_TRADING
from config.settings import INITIAL_CAPITAL

from app.bot.telegram_bot import run_telegram_bot
from app.utils.logger import log
from app.utils.system_check import check_system


def banner():
    print("=" * 45)
    print(f"🚀 {APP_NAME}")
    print(f"Versione {VERSION}")
    print("=" * 45)
    print(f"Paper Trading : {PAPER_TRADING}")
    print(f"Capitale      : {INITIAL_CAPITAL} €")
    print("=" * 45)


def main():
    banner()
    check_system()
    log("Sistema Atlas avviato")

    run_telegram_bot()


if __name__ == "__main__":
    main()