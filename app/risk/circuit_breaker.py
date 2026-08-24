from datetime import datetime, timezone
from typing import Optional


class CircuitBreaker:
    """
    Protezione globale di Atlas.

    Blocca l'apertura di nuovi trade quando vengono superati
    determinati limiti di rischio. Non interferisce con la gestione
    dei trade già aperti.
    """

    def __init__(
        self,
        max_daily_loss_percentage: float = 3.0,
        max_consecutive_losses: int = 3,
        max_drawdown_percentage: float = 10.0,
    ):
        self.max_daily_loss_percentage = max_daily_loss_percentage
        self.max_consecutive_losses = max_consecutive_losses
        self.max_drawdown_percentage = max_drawdown_percentage

    @staticmethod
    def _parse_datetime(value: Optional[str]):
        if not value:
            return None

        try:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            return None

    def _get_today_closed_trades(self, trades: list[dict]) -> list[dict]:
        today = datetime.now(timezone.utc).date()

        result = []

        for trade in trades:
            if trade.get("status") != "closed":
                continue

            closed_at = self._parse_datetime(trade.get("closed_at"))

            if closed_at is None:
                continue

            if closed_at.astimezone(timezone.utc).date() == today:
                result.append(trade)

        return result

    def _calculate_consecutive_losses(self, trades: list[dict]) -> int:
        closed_trades = [
            trade
            for trade in trades
            if trade.get("status") == "closed"
        ]

        closed_trades.sort(
            key=lambda trade: trade.get("closed_at", "")
        )

        consecutive_losses = 0

        for trade in reversed(closed_trades):
            if trade.get("result") == "loss":
                consecutive_losses += 1
            else:
                break

        return consecutive_losses

    def evaluate(
        self,
        trades: list[dict],
        current_balance: float,
        peak_balance: float,
    ) -> dict:

        # 1. Loss consecutive
        consecutive_losses = self._calculate_consecutive_losses(trades)

        if consecutive_losses >= self.max_consecutive_losses:
            return {
                "allowed": False,
                "reason": "max_consecutive_losses",
                "value": consecutive_losses,
            }

        # 2. Perdita giornaliera
        today_trades = self._get_today_closed_trades(trades)

        daily_profit_loss = sum(
            float(trade.get("profit_loss", 0.0))
            for trade in today_trades
        )

        if today_trades:
            first_balance = float(
                today_trades[0].get("wallet_balance", current_balance)
            )

            starting_balance = first_balance - float(
                today_trades[0].get("profit_loss", 0.0)
            )

            if starting_balance > 0:
                daily_loss_percentage = (
                    min(daily_profit_loss, 0.0)
                    / starting_balance
                    * 100
                )

                if abs(daily_loss_percentage) >= self.max_daily_loss_percentage:
                    return {
                        "allowed": False,
                        "reason": "max_daily_loss",
                        "value": round(abs(daily_loss_percentage), 2),
                    }

        # 3. Drawdown globale
        if peak_balance > 0:
            drawdown_percentage = (
                (peak_balance - current_balance)
                / peak_balance
                * 100
            )

            if drawdown_percentage >= self.max_drawdown_percentage:
                return {
                    "allowed": False,
                    "reason": "max_drawdown",
                    "value": round(drawdown_percentage, 2),
                }

        return {
            "allowed": True,
            "reason": None,
            "value": None,
        }