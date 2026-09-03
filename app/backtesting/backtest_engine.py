from typing import Callable

import pandas as pd


class BacktestEngine:
    """Motore base per eseguire backtest su dati storici."""

    def __init__(
        self,
        initial_balance: float = 100.0,
    ) -> None:
        if initial_balance <= 0:
            raise ValueError("Il capitale iniziale deve essere maggiore di zero.")

        self.initial_balance = float(initial_balance)
        self.current_balance = float(initial_balance)
        self.trades: list[dict] = []

    def _simulate_trade(
        self,
        dataframe: pd.DataFrame,
        entry_index: int,
        signal: dict,
    ) -> dict | None:
        direction = signal.get("trade_direction")
        entry_price = signal.get("entry_price")
        stop_loss = signal.get("stop_loss")
        take_profit = signal.get("take_profit")

        if direction not in {"Long", "Short"}:
            return None

        if entry_price is None or stop_loss is None or take_profit is None:
            return None

        for index in range(entry_index + 1, len(dataframe)):
            candle = dataframe.iloc[index]
 
            high = float(candle["high"])
            low = float(candle["low"])

            if direction == "Long":
                if low <= stop_loss:
                    return {
                        "result": "loss",
                        "exit_price": float(stop_loss),
                        "exit_index": index,
                        "close_reason": "stop_loss",
                    }

                if high >= take_profit:
                    return {
                        "result": "win",
                        "exit_price": float(take_profit),
                        "exit_index": index,
                        "close_reason": "take_profit",
                    }

            if direction == "Short":
                if high >= stop_loss:
                    return {
                        "result": "loss",
                        "exit_price": float(stop_loss),
                        "exit_index": index,
                        "close_reason": "stop_loss",
                    }

                if low <= take_profit:
                    return {
                        "result": "win",
                        "exit_price": float(take_profit),
                        "exit_index": index,
                        "close_reason": "take_profit",
                    }

        return None

    def run(
        self,
        dataframe: pd.DataFrame,
        strategy: Callable[[pd.DataFrame], dict],
        warmup_candles: int = 50,
    ) -> dict:
        """
        Scorre il dataset storico e chiama la strategia
        su ogni finestra disponibile.
        """

        if dataframe.empty:
            raise ValueError("Il dataframe storico è vuoto.")

        if warmup_candles <= 0:
            raise ValueError("warmup_candles deve essere maggiore di zero.")

        if len(dataframe) <= warmup_candles:
            raise ValueError(
                "Il dataset non contiene abbastanza candele "
                "per eseguire il backtest."
            )

        self.current_balance = self.initial_balance
        self.trades = []

        signals = []
        last_exit_index = -1

        for current_index in range(
            warmup_candles,
            len(dataframe),
        ):
            # Evita di aprire nuovi trade mentre il precedente
            # sarebbe ancora stato aperto.
            if current_index <= last_exit_index:
                continue

            historical_window = (
                dataframe
                .iloc[: current_index + 1]
                .copy()
                .reset_index(drop=True)
            )

            signal = strategy(historical_window)

            if signal is None:
                continue

            signals.append(
                {
                    "index": current_index,
                    "signal": signal,
                }
            )

            simulated_trade = self._simulate_trade(
                dataframe=dataframe,
                entry_index=current_index,
                signal=signal,
            )

            if simulated_trade is None:
                continue

            entry_price = float(signal["entry_price"])
            exit_price = float(simulated_trade["exit_price"])
            direction = signal["trade_direction"]

            if direction == "Long":
                performance_percentage = (
                    (exit_price - entry_price)
                    / entry_price
                ) * 100

            elif direction == "Short":
                performance_percentage = (
                    (entry_price - exit_price)
                    / entry_price
                ) * 100

            else:
                continue

            balance_before = self.current_balance

            position_size = float(
                signal.get(
                    "position_size",
                    self.current_balance,
               )
            )

            position_size = min(
                position_size,
                self.current_balance,
            )

            profit_loss = (
                position_size
                * performance_percentage
                / 100
            )

            self.current_balance += profit_loss

            trade = {
                "entry_index": current_index,
                "exit_index": simulated_trade["exit_index"],
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "stop_loss": float(signal["stop_loss"]),
                "take_profit": float(signal["take_profit"]),
                "result": simulated_trade["result"],
                "close_reason": simulated_trade["close_reason"],
                "performance_percentage": round(
                    performance_percentage,
                    4,
                ),
                "position_size": round(position_size, 4),
                "profit_loss": round(profit_loss, 4),
                "balance_before": round(balance_before, 4),
                "balance_after": round(
                    self.current_balance,
                    4,
                ),
            }

            self.trades.append(trade)

            last_exit_index = simulated_trade["exit_index"]

        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.current_balance,
            "signals_generated": len(signals),
            "signals": signals,
            "trades": self.trades.copy(),
        }