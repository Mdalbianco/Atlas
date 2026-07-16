from app.exchange.kraken_client import KrakenClient


class ExchangeManager:

    def __init__(self):

        self.kraken = KrakenClient()

    def get_balance(self):

        return self.kraken.get_balance()