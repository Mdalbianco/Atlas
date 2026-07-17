from app.analysis.macd import MACDAnalyzer


def main() -> None:
    closes = [
        100, 101, 102, 103, 104,
        105, 106, 107, 108, 109,
        110, 111, 112, 113, 114,
        115, 116, 117, 118, 119,
        120, 121, 122, 123, 124,
        125, 126, 127, 128, 129,
        130, 131, 132, 133, 134,
        135, 136, 137, 138, 139,
    ]

    analyzer = MACDAnalyzer()
    result = analyzer.calculate(closes)

    print("=== TEST MACD ===")
    print(result)


if __name__ == "__main__":
    main()