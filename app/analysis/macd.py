import pandas as pd


class MACDAnalyzer:
    """Calcola MACD, signal line e istogramma."""

    def calculate(
        self,
        closes: pd.Series,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> dict:
        closes = pd.Series(closes, dtype="float64")

        if len(closes) < slow_period + signal_period:
            raise ValueError(
                "Dati insufficienti per calcolare il MACD."
            )

        fast_ema = closes.ewm(
            span=fast_period,
            adjust=False,
        ).mean()

        slow_ema = closes.ewm(
            span=slow_period,
            adjust=False,
        ).mean()

        macd_line = fast_ema - slow_ema

        signal_line = macd_line.ewm(
            span=signal_period,
            adjust=False,
        ).mean()

        histogram = macd_line - signal_line

        macd_value = float(macd_line.iloc[-1])
        signal_value = float(signal_line.iloc[-1])
        histogram_value = float(histogram.iloc[-1])

        return {
            "macd": round(macd_value, 4),
            "macd_signal": round(signal_value, 4),
            "macd_histogram": round(histogram_value, 4),
            "macd_status": self.get_status(
                macd_value,
                signal_value,
            ),
        }

    def get_status(
        self,
        macd_value: float,
        signal_value: float,
    ) -> str:
        if macd_value > signal_value:
            return "Positivo"

        if macd_value < signal_value:
            return "Negativo"

        return "Neutrale"