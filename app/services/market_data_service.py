import pandas as pd

from app.exchange.exchange_manager import ExchangeManager


class MarketDataService:
    """Recupera e prepara i dati di mercato usati dagli analizzatori."""

    def __init__(self) -> None:
        self.exchange_manager = ExchangeManager()

    def get_candles(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> pd.DataFrame:
        market_symbol = (
            symbol.upper()
            if "/" in symbol
            else f"{symbol.upper()}/EUR"
        )

        candles = self.exchange_manager.get_candles(
            symbol=market_symbol,
            timeframe=timeframe,
            limit=limit,
        )

        if not candles:
            raise ValueError(
                f"Nessuna candela disponibile per {market_symbol}."
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

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        dataframe[numeric_columns] = dataframe[numeric_columns].apply(
            pd.to_numeric,
            errors="coerce",
        )

        dataframe = dataframe.dropna(
            subset=numeric_columns
        ).reset_index(drop=True)

        return dataframe