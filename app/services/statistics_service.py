from app.services.paper_trading_service import PaperTradingService


class StatisticsService:
    """Calcola le statistiche dei paper trade di Atlas."""

    def __init__(self) -> None:
        self.paper_trading_service = PaperTradingService()

    def calculate(self) -> dict:
        trades = self.paper_trading_service._load_trades()

        closed_trades = [
            trade
            for trade in trades
            if trade.get("status") == "closed"
            and trade.get("result") in {"win", "loss"}
        ]

        total_trades = len(closed_trades)
        wins = sum(
            1
            for trade in closed_trades
            if trade.get("result") == "win"
        )
        losses = sum(
            1
            for trade in closed_trades
            if trade.get("result") == "loss"
        )

        win_rate = (
            (wins / total_trades) * 100
            if total_trades > 0
            else 0.0
        )

        performances = []

        for trade in closed_trades:
             entry_price = trade["entry_price"]
             exit_price = trade["exit_price"]
             direction = trade["direction"]
             
             if direction == "Long":
                 performance = (
                 (exit_price - entry_price) / entry_price
                ) * 100
             else:
                 performance = (
                 (entry_price - exit_price) / entry_price
                ) * 100

             performances.append(performance)

        average_performance = (
         sum(performances) / len(performances)
         if performances
         else 0.0
        )

        best_trade = max(performances) if performances else 0.0
        worst_trade = min(performances) if performances else 0.0

        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "average_performance": average_performance,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
        }