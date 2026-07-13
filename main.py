from config.settings import APP_NAME

from config.settings import VERSION

from config.settings import PAPER_TRADING

from config.settings import INITIAL_CAPITAL

from app.utils.logger import log

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

    log("Sistema Atlas avviato")

if __name__ == "__main__":

    main()