from app.exchange.exchange_manager import ExchangeManager


def main() -> None:
    exchange_manager = ExchangeManager()

    price = exchange_manager.get_market_price("BTC/EUR")

    print(price)


if __name__ == "__main__":
    main()