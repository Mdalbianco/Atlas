from app.services.notification_service import NotificationService
from app.analysis.analysis_manager import AnalysisManager
from app.services.paper_trading_service import PaperTradingService
from app.risk.risk_manager import RiskManager
from app.services.wallet_service import WalletService

class AutoTradeService:
    """Analizza il mercato e apre automaticamente trade simulati validi."""

    def __init__(self) -> None:
        self.analysis_manager = AnalysisManager()
        self.paper_trading_service = PaperTradingService()
        self.notification_service = NotificationService()
        self.risk_manager = RiskManager()
        self.wallet_service = WalletService()

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
        
        account_balance = self.wallet_service.get_balance()

        position_size = self.risk_manager.calculate_position_size(
         account_balance=account_balance,
         entry_price=analysis["entry_price"],
         stop_loss=analysis["stop_loss"],
         risk_percentage=2.0,
        )

        trade = self.paper_trading_service.open_trade(
            symbol=symbol.upper(),
            direction=analysis["trade_direction"],
            entry_price=analysis["entry_price"],
            stop_loss=analysis["stop_loss"],
            take_profit=analysis["take_profit"],
            position_size=position_size,
        )
        self.notification_service.send_sync(
         f"""
         🟢 NUOVO TRADE

         Crypto: {symbol}
         Direzione: {analysis['trade_direction']}
         Capitale impiegato: {position_size:.2f} €\n\n"

         Entrata:
         {analysis['entry_price']:.2f} €

         Stop Loss:
         {analysis['stop_loss']:.2f} €

         Take Profit:
         {analysis['take_profit']:.2f} €

         Risk Reward:
        {analysis['risk_reward_ratio']}
         """
        )
        return {
            "trade_opened": True,
            "trade": trade,
            "analysis": analysis,
        }