from app.services.market_data_service import MarketDataService
from app.services.paper_trading_service import PaperTradingService
from app.services.wallet_service import WalletService


class WalletDashboardService:
    """Calcola lo stato operativo del paper wallet di Atlas."""

    def __init__(self) -> None:
        self.wallet_service = WalletService()
        self.paper_trading_service = PaperTradingService()
        self.market_data_service = MarketDataService()

    def calculate(self) -> dict:
        """Restituisce saldo, posizioni aperte e profitto flottante."""

        wallet = self.wallet_service.get_wallet()
        open_trades = self.paper_trading_service.get_open_trades()

        current_balance = float(
            wallet.get("current_balance", 0.0)
        )

        committed_capital = sum(
            float(trade.get("position_size", 0.0))
            for trade in open_trades
        )

        positions = []
        total_unrealized_profit_loss = 0.0

        for trade in open_trades:
            position = self._calculate_position(trade)

            positions.append(position)

            total_unrealized_profit_loss += position[
                "unrealized_profit_loss"
            ]

        available_balance = max(
            current_balance - committed_capital,
            0.0,
        )

        return {
            "current_balance": round(
                current_balance,
                2,
            ),
            "available_balance": round(
                available_balance,
                2,
            ),
            "open_positions": len(open_trades),
            "committed_capital": round(
                committed_capital,
                2,
            ),
            "unrealized_profit_loss": round(
                total_unrealized_profit_loss,
                2,
            ),
            "positions": positions,
        }

    def _calculate_position(
        self,
        trade: dict,
    ) -> dict:
        """Calcola la performance corrente di una posizione aperta."""

        symbol = str(
            trade.get("symbol", "")
        ).upper().replace("/EUR", "")

        entry_price = float(
            trade.get("entry_price", 0.0)
        )

        position_size = float(
            trade.get("position_size", 0.0)
        )

        direction = str(
            trade.get("direction", "")
        )

        current_price = self._get_current_price(
            symbol
        )

        if entry_price <= 0:
            performance_percentage = 0.0
        elif direction == "Long":
            performance_percentage = (
                (current_price - entry_price)
                / entry_price
            ) * 100
        else:
            performance_percentage = (
                (entry_price - current_price)
                / entry_price
            ) * 100

        unrealized_profit_loss = (
            position_size
            * performance_percentage
        ) / 100

        return {
            "id": trade.get("id"),
            "symbol": symbol,
            "direction": direction,
            "entry_price": round(
                entry_price,
                2,
            ),
            "current_price": round(
                current_price,
                2,
            ),
            "position_size": round(
                position_size,
                2,
            ),
            "performance_percentage": round(
                performance_percentage,
                2,
            ),
            "unrealized_profit_loss": round(
                unrealized_profit_loss,
                2,
            ),
        }

    def _get_current_price(
        self,
        symbol: str,
    ) -> float:
        """Recupera il prezzo corrente della criptovaluta."""

        market_data = self.market_data_service.get_market_price(
            symbol
        )

        if isinstance(market_data, dict):
            price = market_data.get("last")

            if price is None:
                raise ValueError(
                    f"Prezzo non disponibile per {symbol}"
                )

            return float(price)

        return float(market_data)