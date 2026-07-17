from app.analysis.rsi import RSIAnalyzer


def main():
    closes = [
        100, 102, 101, 103, 105,
        104, 106, 108, 107, 109,
        111, 110, 112, 114, 113,
        115, 117, 116, 118, 120,
    ]

    analyzer = RSIAnalyzer()

    rsi = analyzer.calculate(closes)
    signal = analyzer.get_signal(rsi)

    print("=== TEST RSI ===")
    print(f"RSI: {rsi}")
    print(f"Segnale: {signal}")


if __name__ == "__main__":
    main()