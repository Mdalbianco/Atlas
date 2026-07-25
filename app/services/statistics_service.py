from app.services.paper_trading_service import PaperTradingService
from app.services.wallet_service import WalletService


class StatisticsService:
    """Calcola le statistiche dei paper trade di Atlas."""

    def __init__(self) -> None:
        self.paper_trading_service = PaperTradingService()
        self.wallet_service = WalletService()

    def calculate(self) -> dict:
        trades = self.paper_trading_service._load_trades()

        closed_trades = [
            trade
            for trade in trades
            if trade.get("status") == "closed"
            and trade.get("result") in {"win", "loss"}
        ]

        closed_trades.sort(
            key=lambda trade: trade.get("closed_at", "")
        )

        total_trades = len(closed_trades)

        wins = [
            trade
            for trade in closed_trades
            if trade.get("result") == "win"
        ]

        losses = [
            trade
            for trade in closed_trades
            if trade.get("result") == "loss"
        ]

        win_count = len(wins)
        loss_count = len(losses)

        win_rate = (
            (win_count / total_trades) * 100
            if total_trades > 0
            else 0.0
        )

        performances = [
            self._get_trade_performance(trade)
            for trade in closed_trades
        ]

        winning_performances = [
            self._get_trade_performance(trade)
            for trade in wins
        ]

        losing_performances = [
            self._get_trade_performance(trade)
            for trade in losses
        ]

        average_performance = self._average(
            performances
        )

        average_win = self._average(
            winning_performances
        )

        average_loss = self._average(
            losing_performances
        )

        best_trade = (
            max(performances)
            if performances
            else 0.0
        )

        worst_trade = (
            min(performances)
            if performances
            else 0.0
        )

        gross_profit = sum(
            performance
            for performance in winning_performances
            if performance > 0
        )

        gross_loss = abs(
            sum(
                performance
                for performance in losing_performances
                if performance < 0
            )
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else None
        )

        loss_rate = (
            100.0 - win_rate
            if total_trades > 0
            else 0.0
        )

        expectancy = (
            (win_rate / 100) * average_win
            + (loss_rate / 100) * average_loss
        )

        durations = [
            float(trade["duration_seconds"])
            for trade in closed_trades
            if isinstance(
                trade.get("duration_seconds"),
                (int, float),
            )
        ]

        average_duration_seconds = int(
            self._average(durations)
        )

        long_stats = self._calculate_direction_stats(
            closed_trades,
            "Long",
        )

        short_stats = self._calculate_direction_stats(
            closed_trades,
            "Short",
        )

        equity_curve = self._build_equity_curve(
            closed_trades
        )

        max_drawdown = self._calculate_max_drawdown(
            equity_curve
        )

        wallet = self.wallet_service.get_wallet()

        initial_balance = float(
            wallet.get("initial_balance", 0.0)
        )

        current_balance = float(
            wallet.get("current_balance", 0.0)
        )

        net_profit = current_balance - initial_balance

        roi = (
            (net_profit / initial_balance) * 100
            if initial_balance > 0
            else 0.0
        )

        return {
            "total_trades": total_trades,
            "wins": win_count,
            "losses": loss_count,
            "win_rate": round(win_rate, 2),
            "average_performance": round(
                average_performance,
                2,
            ),
            "average_win": round(
                average_win,
                2,
            ),
            "average_loss": round(
                average_loss,
                2,
            ),
            "best_trade": round(
                best_trade,
                2,
            ),
            "worst_trade": round(
                worst_trade,
                2,
            ),
            "gross_profit": round(
                gross_profit,
                2,
            ),
            "gross_loss": round(
                gross_loss,
                2,
            ),
            "profit_factor": (
                round(profit_factor, 2)
                if profit_factor is not None
                else None
            ),
            "expectancy": round(
                expectancy,
                2,
            ),
            "average_duration_seconds": (
                average_duration_seconds
            ),
            "average_duration": self._format_duration(
                average_duration_seconds
            ),
            "initial_balance": round(
                initial_balance,
                2,
            ),
            "current_balance": round(
                current_balance,
                2,
            ),
            "net_profit": round(
                net_profit,
                2,
            ),
            "roi": round(
                roi,
                2,
            ),
            "max_drawdown": round(
                max_drawdown,
                2,
            ),
            "equity_curve": equity_curve,
            "long": long_stats,
            "short": short_stats,
        }

    def _get_trade_performance(
        self,
        trade: dict,
    ) -> float:
        saved_performance = trade.get(
            "profit_percentage"
        )

        if isinstance(
            saved_performance,
            (int, float),
        ):
            return float(saved_performance)

        entry_price = float(
            trade["entry_price"]
        )

        exit_price = float(
            trade["exit_price"]
        )

        direction = trade["direction"]

        if entry_price == 0:
            return 0.0

        if direction == "Long":
            return (
                (exit_price - entry_price)
                / entry_price
            ) * 100

        return (
            (entry_price - exit_price)
            / entry_price
        ) * 100

    def _calculate_direction_stats(
        self,
        trades: list[dict],
        direction: str,
    ) -> dict:
        direction_trades = [
            trade
            for trade in trades
            if trade.get("direction") == direction
        ]

        total = len(direction_trades)

        wins = sum(
            1
            for trade in direction_trades
            if trade.get("result") == "win"
        )

        losses = sum(
            1
            for trade in direction_trades
            if trade.get("result") == "loss"
        )

        win_rate = (
            (wins / total) * 100
            if total > 0
            else 0.0
        )

        performances = [
            self._get_trade_performance(trade)
            for trade in direction_trades
        ]

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(
                win_rate,
                2,
            ),
            "average_performance": round(
                self._average(performances),
                2,
            ),
        }

    def _build_equity_curve(
        self,
        closed_trades: list[dict],
    ) -> list[float]:
        wallet = self.wallet_service.get_wallet()

        initial_balance = float(
            wallet.get("initial_balance", 0.0)
        )

        equity_curve = [
            round(initial_balance, 2)
        ]

        running_balance = initial_balance

        for trade in closed_trades:
            wallet_balance = trade.get(
                "wallet_balance"
            )

            if isinstance(
                wallet_balance,
                (int, float),
            ):
                running_balance = float(
                    wallet_balance
                )
            else:
                profit_loss = trade.get(
                    "profit_loss",
                    0.0,
                )

                if isinstance(
                    profit_loss,
                    (int, float),
                ):
                    running_balance += float(
                        profit_loss
                    )

            equity_curve.append(
                round(running_balance, 2)
            )

        return equity_curve

    def _calculate_max_drawdown(
        self,
        equity_curve: list[float],
    ) -> float:
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_drawdown = 0.0

        for balance in equity_curve:
            if balance > peak:
                peak = balance

            if peak <= 0:
                continue

            drawdown = (
                (peak - balance) / peak
            ) * 100

            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return max_drawdown

    def _average(
        self,
        values: list[float],
    ) -> float:
        if not values:
            return 0.0

        return sum(values) / len(values)

    def _format_duration(
        self,
        duration_seconds: int,
    ) -> str:
        hours = duration_seconds // 3600

        minutes = (
            duration_seconds % 3600
        ) // 60

        seconds = duration_seconds % 60

        return (
            f"{hours}h "
            f"{minutes}m "
            f"{seconds}s"
        )