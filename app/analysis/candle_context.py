import pandas as pd


class CandleContextAnalyzer:
    """
    Analizza l'ultima candela e individua movimenti
    eccessivamente estesi rispetto all'ATR.
    """

    def analyze(
        self,
        dataframe: pd.DataFrame,
        atr: float,
        extended_multiplier: float = 1.5,
    ) -> dict:
        self._validate_inputs(
            dataframe=dataframe,
            atr=atr,
            extended_multiplier=extended_multiplier,
        )

        last_candle = dataframe.iloc[-1]

        open_price = float(last_candle["open"])
        high_price = float(last_candle["high"])
        low_price = float(last_candle["low"])
        close_price = float(last_candle["close"])

        body_size = abs(close_price - open_price)
        candle_range = high_price - low_price

        body_atr_ratio = body_size / atr
        range_atr_ratio = candle_range / atr

        if close_price > open_price:
            candle_direction = "Rialzista"
        elif close_price < open_price:
            candle_direction = "Ribassista"
        else:
            candle_direction = "Neutrale"

        extended_candle = (
            body_atr_ratio >= extended_multiplier
            or range_atr_ratio >= extended_multiplier * 1.5
        )

        factors = []

        if extended_candle:
            factors.append(
                "Ultima candela eccessivamente estesa rispetto all'ATR"
            )
        else:
            factors.append(
                "Ampiezza dell'ultima candela nella norma"
            )

        if candle_direction == "Rialzista":
            factors.append("Ultima candela rialzista")
        elif candle_direction == "Ribassista":
            factors.append("Ultima candela ribassista")
        else:
            factors.append("Ultima candela neutrale")

        return {
            "last_candle_open": round(open_price, 8),
            "last_candle_high": round(high_price, 8),
            "last_candle_low": round(low_price, 8),
            "last_candle_close": round(close_price, 8),
            "last_candle_direction": candle_direction,
            "last_candle_body": round(body_size, 8),
            "last_candle_range": round(candle_range, 8),
            "last_candle_body_atr_ratio": round(body_atr_ratio, 2),
            "last_candle_range_atr_ratio": round(range_atr_ratio, 2),
            "extended_candle": extended_candle,
            "candle_context_factors": factors,
        }

    def _validate_inputs(
        self,
        dataframe: pd.DataFrame,
        atr: float,
        extended_multiplier: float,
    ) -> None:
        required_columns = {
            "open",
            "high",
            "low",
            "close",
        }

        missing_columns = required_columns - set(dataframe.columns)

        if missing_columns:
            raise ValueError(
                "Colonne mancanti nel dataframe: "
                f"{sorted(missing_columns)}"
            )

        if dataframe.empty:
            raise ValueError(
                "Il dataframe non può essere vuoto."
            )

        if atr <= 0:
            raise ValueError(
                "L'ATR deve essere maggiore di zero."
            )

        if extended_multiplier <= 0:
            raise ValueError(
                "Il moltiplicatore deve essere maggiore di zero."
            )