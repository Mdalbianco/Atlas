import pandas as pd


class ATRAnalyzer:
    """Calcola l'Average True Range per misurare la volatilità."""

    def calculate(
        self,
        dataframe: pd.DataFrame,
        period: int = 14,
    ) -> dict:
        if len(dataframe) < period + 1:
            raise ValueError(
                "Dati insufficienti per calcolare l'ATR."
            )

        data = dataframe.copy()

        previous_close = data["close"].shift(1)

        high_low = data["high"] - data["low"]

        high_previous_close = (
            data["high"] - previous_close
        ).abs()

        low_previous_close = (
            data["low"] - previous_close
        ).abs()

        true_range = pd.concat(
            [
                high_low,
                high_previous_close,
                low_previous_close,
            ],
            axis=1,
        ).max(axis=1)

        atr_series = true_range.rolling(
            window=period
        ).mean()

        atr_value = float(atr_series.iloc[-1])
        current_price = float(data["close"].iloc[-1])

        atr_percentage = (
            atr_value / current_price
        ) * 100

        return {
            "atr": round(atr_value, 4),
            "atr_percentage": round(atr_percentage, 2),
            "volatility": self.get_volatility(
                atr_percentage
            ),
        }

    def get_volatility(
        self,
        atr_percentage: float,
    ) -> str:
        if atr_percentage < 1:
            return "Bassa"

        if atr_percentage < 2.5:
            return "Media"

        return "Alta"