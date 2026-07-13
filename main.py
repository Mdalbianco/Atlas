from app.services.startup import startup
from config.settings import (
    APP_NAME,
    INITIAL_CAPITAL,
    PAPER_TRADING,
    VERSION,
)


def banner() -> None:
    """Mostra le informazioni principali di Atlas."""

    print("=" * 45)
    print(f"🚀 {APP_NAME}")
    print(f"Versione {VERSION}")
    print("=" * 45)
    print(f"Paper Trading : {PAPER_TRADING}")
    print(f"Capitale      : {INITIAL_CAPITAL} €")
    print("=" * 45)


def main() -> None:
    """Punto di ingresso principale di Atlas."""

    banner()
    startup()


if __name__ == "__main__":
    main()