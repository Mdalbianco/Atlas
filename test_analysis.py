from pprint import pprint

from app.analysis.analysis_manager import AnalysisManager


def main() -> None:
    analysis_manager = AnalysisManager()

    result = analysis_manager.analyze("BTC")

    pprint(result)


if __name__ == "__main__":
    main()