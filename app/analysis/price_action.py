import pandas as pd


class PriceActionAnalyzer:
    """
    Analizza le ultime candele per individuare
    semplici pattern di price action.
    """

    def analyze(self, dataframe: pd.DataFrame) -> dict:

        if dataframe is None or len(dataframe) < 2:
            return {
                "price_action_pattern": "Nessuno",
                "price_action_signal": "Neutrale",
                "price_action_factors": [],
            }

        previous = dataframe.iloc[-2]
        current = dataframe.iloc[-1]

        prev_open = float(previous["open"])
        prev_close = float(previous["close"])

        current_open = float(current["open"])
        current_high = float(current["high"])
        current_low = float(current["low"])
        current_close = float(current["close"])

        body = abs(current_close - current_open)
        candle_range = current_high - current_low

        upper_wick = current_high - max(
            current_open,
            current_close,
        )

        lower_wick = min(
            current_open,
            current_close,
        ) - current_low

        # Evita divisioni problematiche
        if candle_range <= 0:
            return {
                "price_action_pattern": "Nessuno",
                "price_action_signal": "Neutrale",
                "price_action_factors": [],
            }

        body_ratio = body / candle_range

        # -------------------------
        # BULLISH ENGULFING
        # -------------------------

        previous_bearish = prev_close < prev_open
        current_bullish = current_close > current_open

        if (
            previous_bearish
            and current_bullish
            and current_open <= prev_close
            and current_close >= prev_open
        ):
            return {
                "price_action_pattern": "Bullish Engulfing",
                "price_action_signal": "Rialzista",
                "price_action_factors": [
                    "Bullish Engulfing rilevata"
                ],
            }

        # -------------------------
        # BEARISH ENGULFING
        # -------------------------

        previous_bullish = prev_close > prev_open
        current_bearish = current_close < current_open

        if (
            previous_bullish
            and current_bearish
            and current_open >= prev_close
            and current_close <= prev_open
        ):
            return {
                "price_action_pattern": "Bearish Engulfing",
                "price_action_signal": "Ribassista",
                "price_action_factors": [
                    "Bearish Engulfing rilevata"
                ],
            }

        # -------------------------
        # HAMMER
        # -------------------------

        if (
            lower_wick >= body * 2
            and upper_wick <= body
        ):
            return {
                "price_action_pattern": "Hammer",
                "price_action_signal": "Rialzista",
                "price_action_factors": [
                    "Hammer rilevato: possibile pressione rialzista"
                ],
            }

        # -------------------------
        # SHOOTING STAR
        # -------------------------

        if (
            upper_wick >= body * 2
            and lower_wick <= body
        ):
            return {
                "price_action_pattern": "Shooting Star",
                "price_action_signal": "Ribassista",
                "price_action_factors": [
                    "Shooting Star rilevata: possibile pressione ribassista"
                ],
            }

        # -------------------------
        # DOJI
        # -------------------------
        # Viene controllata DOPO Hammer e Shooting Star,
        # perché anche queste candele possono avere
        # un corpo molto piccolo.

        if body_ratio <= 0.10:
            return {
                "price_action_pattern": "Doji",
                "price_action_signal": "Neutrale",
                "price_action_factors": [
                    "Doji rilevata: possibile indecisione del mercato"
                ],
            }

        # -------------------------
        # NESSUN PATTERN
        # -------------------------

        return {
            "price_action_pattern": "Nessuno",
            "price_action_signal": "Neutrale",
            "price_action_factors": [],
        }