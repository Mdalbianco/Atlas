from app.exchange.kraken_client import KrakenClient


class ExchangeManager:
    """Gestisce le operazioni con l'exchange configurato."""

    def __init__(self) -> None:
        self.kraken = KrakenClient()

    def get_balance(self) -> dict:
        """Restituisce il saldo completo dell'account Kraken."""

        return self.kraken.get_balance()

    def get_non_zero_balances(self) -> dict[str, float]:
        """Restituisce soltanto le valute con saldo maggiore di zero."""

        balance = self.get_balance()
        totals = balance.get("total", {})

        return {
            currency: amount
            for currency, amount in totals.items()
            if amount is not None and amount > 0
        }

    def get_market_price(self, symbol: str) -> dict:
        """Restituisce i dati essenziali della coppia richiesta."""

        ticker = self.kraken.get_ticker(symbol)

        return {
            "symbol": symbol,
            "last": ticker.get("last"),
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "high": ticker.get("high"),
            "low": ticker.get("low"),
            "percentage": ticker.get("percentage"),
        }