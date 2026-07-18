from app.services.market_data_service import MarketDataService
from app.services.paper_trading_service import PaperTradingService


class TradeMonitorService:
    """Controlla i trade aperti usando i prezzi reali di mercato."""

    def __init__(self) -> None:
        self.paper_trading_service = PaperTradingService()
        self.market_data_service = MarketDataService()

    def check_once(self) -> list[dict]:
        """
        Esegue un singolo controllo di tutti i trade aperti.

        Restituisce la lista dei trade chiusi durante il controllo.
        """

        return self.paper_trading_service.check_open_trades(
            self.market_data_service.get_current_price
        )