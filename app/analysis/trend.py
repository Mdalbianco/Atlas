import pandas as pd

from app.exchange.exchange_manager import ExchangeManager


class TrendAnalyzer:
    """Analizza il trend tramite EMA 20 ed EMA 50."""

    def __init__(self) -> None:
        self.exchange_manager = ExchangeManager()

    def analyze(self, symbol: str) -> dict:
        """Restituisce direzione, forza ed EMA del mercato."""

        market_symbol = (
            symbol
            if "/" in symbol
            else f"{symbol.upper()}/EUR"
        )

        candles = self.exchange_manager.get_candles(
            symbol=market_symbol,
            timeframe="1h",
            limit=100,
        )

        if len(candles) < 50:
            raise ValueError(
                "Dati insufficienti per calcolare il trend."
            )

        dataframe = pd.DataFrame(
            candles,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
        )

        dataframe["ema_20"] = (
            dataframe["close"]
            .ewm(span=20, adjust=False)
            .mean()
        )

        dataframe["ema_50"] = (
            dataframe["close"]
            .ewm(span=50, adjust=False)
            .mean()
        )

        last_row = dataframe.iloc[-1]

        current_price = float(last_row["close"])
        ema_20 = float(last_row["ema_20"])
        ema_50 = float(last_row["ema_50"])

        difference_percentage = (
            abs(ema_20 - ema_50) / ema_50
        ) * 100

        if ema_20 > ema_50:
            trend = "Rialzista"
        elif ema_20 < ema_50:
            trend = "Ribassista"
        else:
            trend = "Neutrale"

        strength = min(
            round(difference_percentage * 20),
            100,
        )

        return {
            "symbol": market_symbol,
            "trend": trend,
            "strength": strength,
            "current_price": current_price,
            "ema_20": ema_20,
            "ema_50": ema_50,
        }