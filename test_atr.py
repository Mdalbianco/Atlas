from app.analysis.atr import ATRAnalyzer
from app.services.market_data_service import MarketDataService


def main() -> None:
    market_data_service = MarketDataService()
    atr_analyzer = ATRAnalyzer()

    dataframe = market_data_service.get_candles(
        symbol="BTC",
        timeframe="1h",
        limit=100,
    )

    result = atr_analyzer.calculate(dataframe)

    print("=== TEST ATR ===")
    print(result)


if __name__ == "__main__":
    main()