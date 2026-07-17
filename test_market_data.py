from app.services.market_data_service import MarketDataService


def main():
    service = MarketDataService()

    dataframe = service.get_candles("BTC")

    print(dataframe.tail())


if __name__ == "__main__":
    main()