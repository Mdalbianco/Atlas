import pandas as pd


class RSIAnalyzer:
    def calculate(self, closes, period=14):
        closes = pd.Series(closes)

        delta = closes.diff()

        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()

        rs = avg_gain / avg_loss

        rsi = 100 - (100 / (1 + rs))

        return round(rsi.iloc[-1], 2)

    def get_signal(self, rsi):
        if rsi >= 70:
            return "Ipercomprato"

        if rsi <= 30:
            return "Ipervenduto"

        return "Neutrale"