import os

import ccxt
from dotenv import load_dotenv


class KrakenClient:
    """Gestisce la connessione a Kraken."""

    def __init__(self) -> None:
        load_dotenv()

        api_key = os.getenv("KRAKEN_API_KEY")
        api_secret = os.getenv("KRAKEN_API_SECRET")

        if not api_key or not api_secret:
            raise ValueError(
                "Credenziali Kraken mancanti nel file .env."
            )

        self.exchange = ccxt.kraken(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
            }
        )

    def get_balance(self) -> dict:
        """Restituisce il saldo dell'account."""

        return self.exchange.fetch_balance()

    def get_ticker(self, symbol: str) -> dict:
        """Restituisce i dati di mercato della coppia indicata."""

        return self.exchange.fetch_ticker(symbol)