import pandas as pd


class HistoricalMarketDataService:
    """
    Fornisce ad Atlas solo i dati storici disponibili
    fino a un determinato punto del backtest.
    """

    def __init__(
        self,
        lower_timeframe_data: pd.DataFrame,
        higher_timeframe_data: pd.DataFrame,
    ) -> None:
        self.lower_timeframe_data = lower_timeframe_data.copy()
        self.higher_timeframe_data = higher_timeframe_data.copy()

        self.current_lower_index: int | None = None
        self.current_higher_index: int | None = None

    def set_current_index(
        self,
        lower_index: int,
        higher_index: int,
    ) -> None:
        self.current_lower_index = lower_index
        self.current_higher_index = higher_index

    def get_candles(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> pd.DataFrame:

        if timeframe == "1h":
            dataframe = self.lower_timeframe_data
            current_index = self.current_lower_index

        elif timeframe == "4h":
            dataframe = self.higher_timeframe_data
            current_index = self.current_higher_index

        else:
            raise ValueError(
                f"Timeframe non supportato nel backtest: {timeframe}"
            )

        if current_index is None:
            raise RuntimeError(
                "Il punto temporale del backtest non è stato impostato."
            )

        start_index = max(
            0,
            current_index - limit + 1,
        )

        return (
            dataframe
            .iloc[start_index:current_index + 1]
            .copy()
            .reset_index(drop=True)
        )