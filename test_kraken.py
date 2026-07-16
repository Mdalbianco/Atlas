from app.exchange.exchange_manager import ExchangeManager


def main():

    exchange = ExchangeManager()

    balance = exchange.get_balance()

    print(balance)


if __name__ == "__main__":
    main()