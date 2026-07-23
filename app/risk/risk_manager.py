class RiskManager:
    """Calcola ingresso, stop loss e take profit usando l'ATR."""

    def calculate_trade_levels(
        self,
        current_price: float,
        atr: float,
        action: str,
        stop_atr_multiplier: float = 1.5,
        risk_reward_ratio: float = 2.0,
    ) -> dict:
        if current_price <= 0:
            raise ValueError("Il prezzo corrente deve essere maggiore di zero.")

        if atr <= 0:
            raise ValueError("L'ATR deve essere maggiore di zero.")

        entry_price = current_price
        stop_distance = atr * stop_atr_multiplier
        take_profit_distance = stop_distance * risk_reward_ratio

        normalized_action = action.strip().lower()

        if normalized_action in {
         "comprare",
         "compra",
         "buy",
         "possibile acquisto",
        }:
            stop_loss = entry_price - stop_distance
            take_profit = entry_price + take_profit_distance
            trade_direction = "Long"

        elif normalized_action in {
         "vendere",
         "vendi",
         "sell",
         "possibile vendita",
        }:
            stop_loss = entry_price + stop_distance
            take_profit = entry_price - take_profit_distance
            trade_direction = "Short"

        else:
            return {
                "trade_available": False,
                "trade_direction": None,
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "risk_reward_ratio": None,
            }

        return {
            "trade_available": True,
            "trade_direction": trade_direction,
            "entry_price": round(entry_price, 4),
            "stop_loss": round(stop_loss, 4),
            "take_profit": round(take_profit, 4),
            "risk_reward_ratio": risk_reward_ratio,
        }

    def calculate_position_size(
       self,
       account_balance: float,
       entry_price: float,
       stop_loss: float,
       risk_percentage: float = 2.0,
    ) -> float:
     """
     Calcola il capitale da impiegare affinché,
     se viene colpito lo Stop Loss, la perdita
     massima sia pari alla percentuale di rischio scelta.
     """

     if account_balance <= 0:
        return 0.0

     if entry_price <= 0:
        return 0.0

     stop_distance = abs(entry_price - stop_loss)

     if stop_distance <= 0:
        return 0.0

     risk_amount = (
        account_balance
        * risk_percentage
        / 100
    )

     stop_distance_percentage = (
        stop_distance
        / entry_price
    )

     position_size = (
        risk_amount
        / stop_distance_percentage
    )

     position_size = min(
        position_size,
        account_balance,
    )

     return round(position_size, 2)