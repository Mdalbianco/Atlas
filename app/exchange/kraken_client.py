import os

import ccxt
from dotenv import load_dotenv


class KrakenClient:
    """Gestisce la connessione a Kraken."""

    def __init__(self):

        load_dotenv()

        self.exchange = ccxt.kraken({
            "apiKey": os.getenv("KRAKEN_API_KEY"),
            "secret": os.getenv("KRAKEN_API_SECRET"),
        })

    def get_balance(self):
        """Restituisce il saldo dell'account."""

        return self.exchange.fetch_balance()