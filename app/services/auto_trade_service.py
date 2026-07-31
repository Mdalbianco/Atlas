from app.services.notification_service import NotificationService
from app.analysis.analysis_manager import AnalysisManager
from app.services.paper_trading_service import PaperTradingService
from app.risk.risk_manager import RiskManager
from app.services.wallet_service import WalletService

class AutoTradeService:
    """Analizza il mercato e apre automaticamente trade simulati validi."""

    def __init__(
       self,
       max_open_trades: int = 2,
       max_committed_percentage: float = 70.0,
       min_position_size: float = 10.0,
    ) -> None:
       self.analysis_manager = AnalysisManager()
       self.paper_trading_service = PaperTradingService()
       self.notification_service = NotificationService()
       self.risk_manager = RiskManager()
       self.wallet_service = WalletService()
       self.max_open_trades = max_open_trades
       self.max_committed_percentage = max_committed_percentage
       self.min_position_size = min_position_size

    def analyze_and_open(self, symbol: str) -> dict:
        """
        Analizza una crypto e apre un trade simulato
        solo quando è disponibile un piano operativo.
        """

        analysis = self.analysis_manager.analyze(symbol)

        minimum_confidence = 65

        if not analysis.get("score_acceptable", False):
            return {
            "trade_opened": False,
            "status": "score_below_minimum",
            "reason": (
                "Qualità del setup insufficiente: "
                f"{analysis.get('score', 0)}/100."
            ),
            "analysis": analysis,
        }

        if analysis.get("confidence", 0) < minimum_confidence:
            return {
                "trade_opened": False,
                "status": "confidence_below_minimum",
                "reason": (
                    "Confidenza insufficiente: "
                    f"{analysis.get('confidence', 0)}/100. "
                    f"Minimo richiesto: {minimum_confidence}/100."
                ),
                "analysis": analysis,
            }

        if not analysis.get("trade_available", False):
            return {
                "trade_opened": False,
                "status": "no_trade_plan",
                "reason": "Nessun piano operativo disponibile.",
                "analysis": analysis,
            }

        open_trades = self.paper_trading_service.get_open_trades()

        if len(open_trades) >= self.max_open_trades:
         return {
            "trade_opened": False,
            "status": "max_open_trades_reached",
            "reason": (
               "Limite massimo di trade aperti raggiunto: "
               f"{self.max_open_trades}."
            ),
            "analysis": analysis,
        }
        
        account_balance = self.wallet_service.get_balance()

        committed_capital = sum(
           float(trade.get("position_size", 0.0))
           for trade in open_trades
        )

        max_committed_capital = (
           account_balance
           * self.max_committed_percentage
        ) / 100

        position_size = self.risk_manager.calculate_position_size(
         account_balance=account_balance,
         entry_price=analysis["entry_price"],
         stop_loss=analysis["stop_loss"],
         risk_percentage=2.0,
        )

        remaining_committed_capital = (
         max_committed_capital - committed_capital
        )

        if remaining_committed_capital <= 0:
          return {
             "trade_opened": False,
             "status": "max_committed_capital_reached",
             "reason": (
                 "Limite di capitale impegnato raggiunto: "
                 f"{self.max_committed_percentage:.0f}%."
            ),
            "analysis": analysis,
        }

        position_size = min(
         position_size,
         remaining_committed_capital,
        )

        if position_size < self.min_position_size:
            return {
             "trade_opened": False,
             "status": "position_size_below_minimum",
             "reason": (
                "Dimensione della posizione inferiore "
                f"al minimo consentito di {self.min_position_size:.2f} €."
            ),
            "analysis": analysis,
            "position_size": round(position_size, 2),
            }

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