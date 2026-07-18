from app.analysis.analysis_manager import AnalysisManager
from app.services.paper_trading_service import PaperTradingService


class AutoTradeService:
    """Analizza il mercato e apre automaticamente trade simulati validi."""

    def __init__(self) -> None:
        self.analysis_manager = AnalysisManager()
        self.paper_trading_service = PaperTradingService()

    def analyze_and_open(self, symbol: str) -> dict:
        """
        Analizza una crypto e apre un trade simulato
        solo quando è disponibile un piano operativo.
        """

        analysis = self.analysis_manager.analyze(symbol)

        if not analysis["trade_available"]:
            return {
                "trade_opened": False,
                "reason": "Nessun piano operativo disponibile.",
                "analysis": analysis,
            }

        trade = self.paper_trading_service.open_trade(
            symbol=symbol.upper(),
            direction=analysis["trade_direction"],
            entry_price=analysis["entry_price"],
            stop_loss=analysis["stop_loss"],
            take_profit=analysis["take_profit"],
        )

        return {
            "trade_opened": True,
            "trade": trade,
            "analysis": analysis,
        }